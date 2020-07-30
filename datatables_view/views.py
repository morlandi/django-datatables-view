# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
#from django.utils import six

import datetime
import json
from django.views.generic import View
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.template import loader, Context
from django.utils.translation import ugettext_lazy as _

from .columns import Column
from .columns import ForeignColumn
from .columns import ColumnLink
from .columns import PlaceholderColumnLink
from .columns import Order
from .exceptions import ColumnOrderError
from .utils import prettyprint_queryset
from .utils import trace
from .utils import format_datetime
from .filters import build_column_filter
from .app_settings import MAX_COLUMNS
from .app_settings import ENABLE_QUERYSET_TRACING
from .app_settings import ENABLE_QUERYDICT_TRACING
from .app_settings import TEST_FILTERS
from .app_settings import DISABLE_QUERYSET_OPTIMIZATION


class DatatablesView(View):

    # Either override in derived class, or override self.get_column_defs()
    column_defs = []

    model = None
    template_name = 'datatables_view/datatable.html'
    initial_order = [[1, "asc"]]
    length_menu = [[10, 20, 50, 100], [10, 20, 50, 100]]
    table_row_id_prefix = 'row-'
    table_row_id_fieldname = 'id'

    # Set with self.initialize()
    column_specs = []  # used to keep column ording as required
    column_index = {}  # used to speedup lookups
    #column_objs_lut = {}

    #model_columns = {}
    latest_by = None
    show_date_filters = None
    show_column_filters = None

    disable_queryset_optimization = False

    def initialize(self, request):

        # Retrieve and normalize latest_by fieldname
        latest_by = self.get_latest_by(request)
        if latest_by is None:
            latest_by = getattr(self.model._meta, 'get_latest_by', None)
        if isinstance(latest_by, (list, tuple)):
            latest_by = latest_by[0] if len(latest_by) > 0 else ''
        if latest_by:
            if latest_by.startswith('-'):
                latest_by = latest_by[1:]
        self.latest_by = latest_by

        # Grab column defs and initialize self.column_specs
        column_defs_ex = self.get_column_defs(request)
        self.column_specs = []
        for c in column_defs_ex:

            column = {
                'name': '',
                'data': None,
                'title': '',
                'searchable': False,
                'orderable': False,
                'visible': True,
                'foreign_field': None,
                'placeholder': False,
                'className': None,
                'defaultContent': None,
                'width': None,
                'choices': None,
                'initialSearchValue': None,
                'autofilter': False,
                'boolean': False,
                'max_length': 0,
            }

            #valid_keys = [key for key in column.keys()][:]
            #valid_keys = column.keys().copy()
            valid_keys = list(column.keys())

            column.update(c)

            # We now accept a collable as "initialSearchValue"
            if callable(column['initialSearchValue']):
                column['initialSearchValue'] = column['initialSearchValue']()

            # TODO: do we really want to accept an empty column name ?
            # Investigate !
            if c['name']:

                # Detect unexpected keys
                for key in c.keys():
                    if not key in valid_keys:
                        raise Exception('Unexpected key "%s" for column "%s"' % (key, c['name']))

                if 'title' in c:
                    title = c['title']
                else:
                    try:
                        title = self.model._meta.get_field(c['name']).verbose_name.title()
                    except:
                        title = c['name']

                column['name'] = c['name']
                column['data'] = c['name']
                #column['title'] = c.get('title') if 'title' in c else self.model._meta.get_field(c['name']).verbose_name.title()
                column['title'] = title
                column['searchable'] = c.get('searchable', column['visible'])
                column['orderable'] = c.get('orderable', column['visible'])

            self.column_specs.append(column)

        # # build LUT for column objects
        # #
        # #    self.column_objs_lut = {
        # #        'id': <datatables_view.columns.Column object at 0x109d82850>,
        # #        'code': <datatables_view.columns.Column object at 0x109d82f10>,
        # #        ...
        # #
        # self.column_objs_lut = Column.collect_model_columns(
        #     self.model,
        #     self.column_specs
        # )

        # For each table column, we build either a Columns or ForeignColumns as required;
        # both "column spec" dictionary and the column object are saved in "column_index"
        # to speed up later lookups;
        # Finally, we elaborate "choices" list

        self.column_index = {}
        for cs in self.column_specs:

            key = cs['name']
            column = Column.column_factory(self.model, cs)
            choices = []

            #
            # Adjust choices
            # we do this here since the model field itself is finally available
            #

            # (1) None (default) or False: no choices (use text input box)
            if cs['choices'] == False:
                # Do not use choices
                cs['choices'] = None
            # (2) True: use Model's field choices;
            #     - failing that, we might use "autofilter"; that is: collect the list of distinct values from db table
            #     - BooleanFields deserve a special treatement
            elif cs['choices'] == True:

                # For boolean fields, provide (None)/Yes/No choice sequence
                if isinstance(column.model_field, models.BooleanField):
                    if column.model_field.null:
                        # UNTESTED !
                        choices = [(None, ''), ]
                    else:
                        choices = []
                    choices += [(True, _('Yes')), (False, _('No'))]
                elif cs['boolean']:
                    choices += [(True, _('Yes')), (False, _('No'))]
                else:
                    # Otherwise, retrieve field's choices, if any ...
                    choices = getattr(column.model_field, 'choices', None)
                    if choices is None:
                        choices = []
                    else:
                        #
                        # Here, we could abbreviate select's options as well;
                        # however, the caller can easily apply a 'width' css attribute to the select tag, instead
                        #
                        # max_length = cs['max_length']
                        # if max_length <= 0:
                        #     choices = [(c[0], c[1]) for c in choices]
                        # else:
                        #     choices = [(c[0], self.clip_value(c[1], max_length, False)) for c in choices]
                        #
                        choices = choices[:]

                # ... or collect distict values if 'autofilter' has been enabled
                if len(choices) <= 0 and cs['autofilter']:
                    choices = self.list_autofilter_choices(request, cs, column.model_field, cs['initialSearchValue'])
                cs['choices'] = choices if len(choices) > 0 else None
            # (3) Otherwise, just use the sequence of choices that has been supplied.


            self.column_index[key] = {
                'spec': cs,
                'column': column,
            }

        # Initialize "show_date_filters"
        show_date_filters = self.get_show_date_filters(request)
        if show_date_filters is None:
            show_date_filters = bool(self.latest_by)
        self.show_date_filters = show_date_filters

        # If global date filter is visible,
        # add class 'get_latest_by' to the column used for global date filtering
        if self.show_date_filters and self.latest_by:
            column_def = self.column_spec_by_name(self.latest_by)
            if column_def:
                if column_def['className']:
                    column_def['className'] += 'latest_by'
                else:
                    column_def['className'] = 'latest_by'

        # Initialize "show_column_filters"
        show_column_filters = self.get_show_column_filters(request)
        if show_column_filters is None:
            # By default we show the column filters if there is at least
            # one searchable and visible column
            num_searchable_columns = len([c for c in self.column_specs if c.get('searchable') and c.get('visible')])
            show_column_filters = (num_searchable_columns > 0)
        self.show_column_filters = show_column_filters

        if ENABLE_QUERYDICT_TRACING:
            trace(self.column_specs, prompt='column_specs')

    def get_column_defs(self, request):
        """
        Override to customize based of request
        """
        return self.column_defs

    def get_initial_order(self, request):
        """
        Override to customize based of request
        """
        return self.initial_order

    def get_length_menu(self, request):
        """
        Override to customize based of request
        """
        return self.length_menu

    def get_template_name(self, request):
        """
        Override to customize based of request
        """
        return self.template_name

    def get_latest_by(self, request):
        """
        Override to customize based of request.

        Provides the name of the column to be used for global date range filtering.
        Return either '', a fieldname or None.

        When None is returned, in model's Meta 'get_latest_by' attributed will be used.
        """
        return self.latest_by

    def get_show_date_filters(self, request):
        """
        Override to customize based of request.

        Defines whether to use the global date range filter.
        Return either True, False or None.

        When None is returned, will'll check whether 'latest_by' is defined
        """
        return self.show_date_filters

    def get_show_column_filters(self, request):
        """
        Override to customize based of request.

        Defines whether to use the column filters.
        Return either True, False or None.

        When None is returned, check if at least one visible column in searchable.
        """
        return self.show_column_filters

    def column_obj(self, name):
        """
        Lookup columnObj for the column_spec identified by 'name'
        """
        # assert name in self.column_objs_lut
        # return self.column_objs_lut[name]
        assert name in self.column_index
        return self.column_index[name]['column']

    def column_spec_by_name(self, name):
        """
        Lookup the column_spec identified by 'name'
        """
        if name in self.column_index:
            return self.column_index[name]['spec']
        return None

    def fix_initial_order(self, initial_order):
        """
        "initial_order" is a list of (position, direction) tuples; for example:
            [[1, 'asc'], [5, 'desc']]

        Here, we also accept positions expressed as column names,
        and convert the to the corresponding numeric position.
        """
        values = []
        keys = list(self.column_index.keys())
        for position, direction in initial_order:
            if type(position) == str:
                position = keys.index(position)
            values.append([position, direction])
        return values

    #@method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):

        if not getattr(request, 'REQUEST', None):
            request.REQUEST = request.GET if request.method=='GET' else request.POST

        self.initialize(request)
        if request.is_ajax():
            action = request.REQUEST.get('action', '')
            if action == 'initialize':

                # Sanity check for initial order
                initial_order = self.get_initial_order(request)
                initial_order = self.fix_initial_order(initial_order)

                initial_order_columns = [row[0] for row in initial_order]
                for col in initial_order_columns:
                    if col >= len(self.column_specs):
                        raise Exception('Initial order column %d does not exists' % col)
                    elif not self.column_specs[col]['orderable']:
                        raise Exception('Column %d is not orderable' % col)

                # Initial values for column filters, when supplied
                # See: https://datatables.net/reference/option/searchCols
                searchCols = [
                    {'search': cs['initialSearchValue'], }
                    for cs in self.column_specs
                ]

                return JsonResponse({
                    'columns': self.column_specs,
                    'searchCols': searchCols,
                    'order': initial_order,
                    'length_menu': self.get_length_menu(request),
                    'show_date_filters': self.show_date_filters,
                    'show_column_filters': self.show_column_filters,
                    'table_row_id_fieldname': self.table_row_id_fieldname
                })
            elif action == 'details':
                #row_id = request.REQUEST.get('id')
                row_id = request.REQUEST.get(self.table_row_id_fieldname)
                return JsonResponse({
                    'html': self.render_row_details(row_id, request),
                    'parent-row-id': row_id,
                })

            response = super(DatatablesView, self).dispatch(request, *args, **kwargs)
        else:
            assert False
            #response = HttpResponse(self.render_table(request))
        return response

    def get_model_admin(self):
        from django.contrib import admin
        if self.model in admin.site._registry:
            return admin.site._registry[self.model]
        return None

    def render_row_details(self, id, request=None):
        # Determine id name
        if self.table_row_id_fieldname:
            q = {self.table_row_id_fieldname: id}
        else:
            q = {id: id}

        obj = self.model.objects.get(**q)

        # Search a custom template for rendering, if available
        try:
            template = loader.select_template([
                'datatables_view/%s/%s/render_row_details.html' % (self.model._meta.app_label, self.model._meta.model_name),
                'datatables_view/%s/render_row_details.html' % (self.model._meta.app_label, ),
                'datatables_view/render_row_details.html',
            ])
            html = template.render({
                'model': self.model,
                'model_admin': self.get_model_admin(),
                'object': obj,
            }, request)

        # Failing that, display a simple table with field values
        except TemplateDoesNotExist:
            fields = [f.name for f in self.model._meta.get_fields() if f.concrete]
            html = '<table class="row-details">'
            for field in fields:
                try:
                    value = getattr(obj, field)
                    html += '<tr><td>%s</td><td>%s</td></tr>' % (field, value)
                except:
                    pass
            html += '</table>'
        return html

    @staticmethod
    def render_row_tools_column_def():
        column_def = {
            'name': '',
            'visible': True,
            # https://datatables.net/blog/2017-03-31
            'defaultContent': render_to_string('datatables_view/row_tools.html', {'foo': 'bar'}),
            "className": 'dataTables_row-tools',
            'width': 30,
        }
        return column_def

    # def render_table(self, request):

    #     template_name = self.get_template_name(request)

    #     # # When called via Ajax, use the "smaller" template "<template_name>_inner.html"
    #     # if request.is_ajax():
    #     #     template_name = getattr(self, 'ajax_template_name', '')
    #     #     if not template_name:
    #     #         split = self.template_name.split('.html')
    #     #         split[-1] = '_inner'
    #     #         split.append('.html')
    #     #         template_name = ''.join(split)

    #     html = render_to_string(
    #         template_name, {
    #             'title': self.title,
    #             'columns': self.list_columns(request),
    #             'column_details': mark_safe(json.dumps(self.list_columns(request))),
    #             'initial_order': mark_safe(json.dumps(self.get_initial_order(request))),
    #             'length_menu': mark_safe(json.dumps(self.get_length_menu(request))),
    #             'view': self,
    #             'show_date_filter': self.model._meta.get_latest_by is not None,
    #         },
    #         request=request
    #     )

    #     return html

    def post(self, request, *args, **kwargs):
        """
        Treat POST and GET the like
        """
        return self.get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):

        # if not getattr(request, 'REQUEST', None):
        #     request.REQUEST = request.GET if request.method=='GET' else request.POST

        t0 = datetime.datetime.now()

        if not request.is_ajax():
            return HttpResponseBadRequest()

        try:
            query_dict = request.REQUEST
            params = self.read_parameters(query_dict)
        except ValueError:
            return HttpResponseBadRequest()

        if ENABLE_QUERYDICT_TRACING:
            trace(query_dict, prompt='query_dict')
            trace(params, prompt='params')

        # Prepare the queryset and apply the search and order filters
        qs = self.get_initial_queryset(request)
        if not DISABLE_QUERYSET_OPTIMIZATION and not self.disable_queryset_optimization:
            qs = self.optimize_queryset(qs)
        qs = self.prepare_queryset(params, qs)
        if ENABLE_QUERYSET_TRACING:
            prettyprint_queryset(qs)

        # Slice result
        paginator = Paginator(qs, params['length'] if params['length'] != -1 else qs.count())
        response_dict = self.get_response_dict(request, paginator, params['draw'], params['start'])
        response_dict['footer_message'] = self.footer_message(qs, params)

        # Prepare response
        response = HttpResponse(
            json.dumps(
                response_dict,
                cls=DjangoJSONEncoder
            ),
            content_type="application/json")

        # Trace elapsed time
        if ENABLE_QUERYSET_TRACING:
            td = datetime.datetime.now() - t0
            ms = (td.seconds * 1000) + (td.microseconds / 1000.0)
            trace('%d [ms]' % ms, prompt="Table rendering time")

        return response

    def read_parameters(self, query_dict):
        """
        Converts and cleans up the GET parameters.
        """
        params = {field: int(query_dict[field]) for field in ['draw', 'start', 'length']}
        params['date_from'] = query_dict.get('date_from', None)
        params['date_to'] = query_dict.get('date_to', None)

        column_index = 0
        has_finished = False
        column_links = []

        while column_index < MAX_COLUMNS and not has_finished:
            column_base = 'columns[%d]' % column_index
            try:
                column_name = query_dict[column_base + '[name]']
                if column_name == '':
                    column_name = query_dict[column_base + '[data]']

                if column_name != '':
                    column_links.append(
                        ColumnLink(
                            column_name,
                            #self.model_columns[column_name],
                            self.column_obj(column_name),
                            query_dict.get(column_base + '[orderable]'),
                            query_dict.get(column_base + '[searchable]'),
                            query_dict.get(column_base + '[search][value]'),
                        )
                    )
                else:
                    column_links.append(PlaceholderColumnLink())
            except KeyError:
                has_finished = True

            column_index += 1

        orders = []
        order_index = 0
        has_finished = False
        columns = [c['name'] for c in self.column_specs]
        while order_index < len(columns) and not has_finished:
            try:
                order_base = 'order[%d]' % order_index
                order_column = query_dict[order_base + '[column]']
                orders.append(Order(
                    order_column,
                    query_dict[order_base + '[dir]'],
                    column_links))
            except ColumnOrderError:
                pass
            except KeyError:
                has_finished = True

            order_index += 1

        search_value = query_dict.get('search[value]')
        if search_value:
            params['search_value'] = search_value

        params.update({'column_links': column_links, 'orders': orders})

        return params

    def get_initial_queryset(self, request=None):
        return self.model.objects.all()

    def get_foreign_queryset(self, request, field):
        queryset = field.model.objects.all()
        return queryset

    def render_column(self, row, column):
        #return self.model_columns[column].render_column(row)
        value = self.column_obj(column).render_column(row)
        return value

    def render_clip_value_as_html(self, long_text, short_text, is_clipped):
        """
        Given long and shor version of text, the following html representation:
            <span title="long_text">short_text[ellipsis]</span>

        To be overridden for further customisations.
        """
        return '<span title="{long_text}">{short_text}{ellipsis}</span>'.format(
            long_text=long_text,
            short_text=short_text,
            ellipsis='&hellip;' if is_clipped else ''
        )

    def clip_value(self, text, max_length, as_html):
        """
        Given `text`, returns:
            - original `text` if it's length is less then or equal `max_length`
            - the clipped left part + ellipses otherwise
        as either plain text or html (depending on `as_html`)
        """
        is_clipped = False
        long_text = text
        if len(text) <= max_length:
            short_text = text
        else:
            short_text = text[:max_length]
            is_clipped = True
        if as_html:
            result = self.render_clip_value_as_html(long_text, short_text, is_clipped)
        else:
            result = short_text
            if is_clipped:
                result += '…'
        return result

    def clip_results(self, retdict):
        rows = [(cs['name'], cs['max_length']) for cs in  self.column_specs if cs['max_length'] > 0]
        for name, max_length in rows:
            retdict[name] = self.clip_value(str(retdict[name]), max_length, True)

    def prepare_results(self, request, qs):
        json_data = []
        columns = [c['name'] for c in self.column_specs]
        for cur_object in qs:
            retdict = {
                #fieldname: '<div class="field-%s">%s</div>' % (fieldname, self.render_column(cur_object, fieldname))
                fieldname: self.render_column(cur_object, fieldname)
                for fieldname in columns
                if fieldname
            }

            self.customize_row(retdict, cur_object)
            self.clip_results(retdict)

            row_id = self.get_table_row_id(request, cur_object)
            if row_id:
                # "Automatic addition of row ID attributes"
                # https://datatables.net/examples/server_side/ids.html
                retdict['DT_RowId'] = row_id

            json_data.append(retdict)
        return json_data

    def get_response_dict(self, request, paginator, draw_idx, start_pos):
        page_id = (start_pos // paginator.per_page) + 1
        if page_id > paginator.num_pages:
            page_id = paginator.num_pages
        elif page_id < 1:
            page_id = 1

        objects = self.prepare_results(request, paginator.page(page_id))

        return {"draw": draw_idx,
                "recordsTotal": paginator.count,
                "recordsFiltered": paginator.count,
                "data": objects,
                }

    def get_table_row_id(self, request, obj):
        """
        Provides a specific ID for the table row; default: "row-ID"
        Override to customize as required.

        Do to a limitation of datatables.net, we can only supply to table rows
        a id="row-ID" attribute, and not a data-row-id="ID" attribute
        """
        result = ''
        if self.table_row_id_fieldname:
            try:
                result = self.table_row_id_prefix + str(getattr(obj, self.table_row_id_fieldname))
            except:
                result = ''
        return result

    def customize_row(self, row, obj):
        # 'row' is a dictionnary representing the current row, and 'obj' is the current object.
        #row['age_is_even'] = obj.age%2==0
        pass

    def optimize_queryset(self, qs):

        # use sets to remove duplicates
        only = set()
        select_related = set()

        # collect values for qs optimizations
        fields = [f.name for f in self.model._meta.get_fields()]
        for column in self.column_specs:
            foreign_field = column.get('foreign_field')
            if foreign_field:

                # Examples:
                #
                #   +-----------------------------+-------------------------------+-----------------------------------+
                #   | if foreign_key is:          | add this to only[]:           | and add this to select_related[]: |
                #   +-----------------------------+-------------------------------+-----------------------------------+
                #   | 'lotto__codice'             | 'lotto__codice'               | 'lotto'                           |
                #   | 'lotto__articolo__codice'   | 'lotto__articolo__codice'     | 'lotto__articolo'                 |
                #   +-----------------------------+-------------------------------+-----------------------------------+
                #

                only.add(foreign_field)
                #select_related.add(column.get('name'))
                #select_related.add(foreign_field.split('__')[0])
                select_related.add('__'.join(foreign_field.split('__')[0:-1]))
            else:
                [f.name for f in self.model._meta.get_fields()]
                field = column.get('name')
                if field in fields:
                    only.add(field)

        # convert to lists
        only = [item for item in list(only) if item]
        select_related = list(select_related)

        # apply optimizations:

        # (1) use select_related() to reduce the number of queries
        if select_related:
            qs = qs.select_related(*select_related)

        # (2) use only() to reduce the number of columns in the resultset
        if only:
            qs = qs.only(*only)

        return qs

    def prepare_queryset(self, params, qs):
        qs = self.filter_queryset(params, qs)
        qs = self.sort_queryset(params, qs)
        return qs

    def filter_queryset(self, params, qs):

        qs = self.filter_queryset_by_date_range(params.get('date_from', None), params.get('date_to', None), qs)

        if 'search_value' in params:
            qs = self.filter_queryset_all_columns(params['search_value'], qs)

        for column_link in params['column_links']:
            if column_link.searchable and column_link.search_value:
                qs = self.filter_queryset_by_column(column_link.name, column_link.search_value, qs)

        return qs

    def sort_queryset(self, params, qs):
        if len(params['orders']):
            qs = qs.order_by(
                *[order.get_order_mode() for order in params['orders']])
        return qs

    # TODO: currently unused; in the orginal project was probably related to the
    # management of fields with choices;
    # check and refactor this
    def choice_field_search(self, column, search_value):
        values_dict = self.choice_fields_completion[column]
        # matching_choices = [
        #     val for key, val in six.iteritems(values_dict)
        #     if key.startswith(search_value)
        # ]
        matching_choices = [
            val for key, val in values_dict.items()
            if key.startswith(search_value)
        ]
        return Q(**{column + '__in': matching_choices})

    def _filter_queryset(self, column_names, search_value, qs):

        if TEST_FILTERS:
            trace(', '.join(column_names), 'Filtering "%s" over fields' % search_value)

        search_filters = Q()
        for column_name in column_names:

            column_obj = self.column_obj(column_name)
            column_spec = self.column_spec_by_name(column_name)

            column_filter = build_column_filter(column_name, column_obj, column_spec, search_value)
            if column_filter:
                search_filters |= column_filter
                if TEST_FILTERS:
                    trace(column_name, "Test filter")
                    qstest = qs.filter(column_filter)
                    trace('%d/%d records filtered' % (qstest.count(), qs.count()))

        if TEST_FILTERS:
            trace(search_filters, prompt='Search filters')

        return qs.filter(search_filters)

    def filter_queryset_all_columns(self, search_value, qs):
        searchable_columns = [c['name'] for c in self.column_specs if c['searchable']]
        return self._filter_queryset(searchable_columns, search_value, qs)

    def filter_queryset_by_column(self, column_name, search_value, qs):
        return self._filter_queryset([column_name, ], search_value, qs)

    def filter_queryset_by_date_range(self, date_from, date_to, qs):

        if self.latest_by and (date_from or date_to):

            daterange_filter = Q()
            is_datetime = isinstance(self.latest_by, models.DateTimeField)

            if date_from:
                dt = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                if is_datetime:
                    daterange_filter &= Q(**{self.latest_by+'__date__gte': dt})
                else:
                    daterange_filter &= Q(**{self.latest_by+'__gte': dt})

            if date_to:
                dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                if is_datetime:
                    daterange_filter &= Q(**{self.latest_by+'__date__lte': dt})
                else:
                    daterange_filter &= Q(**{self.latest_by+'__lte': dt})

            if TEST_FILTERS:
                n0 = qs.count()

            qs = qs.filter(daterange_filter)

            if TEST_FILTERS:
                n1 = qs.count()
                trace(daterange_filter, prompt='Daterange filter')
                trace('%d/%d records filtered' % (n1, n0))

        return qs

    def footer_message(self, qs, params):
        """
        Overriden to append a message to the bottom of the table
        """
        #return 'Selected rows: %d' % qs.count()
        return None


    def list_autofilter_choices(self, request, column_spec, field, initial_search_value):
        """
        Collects distinct values from specified field,
        and prepares a list of choices for "autofilter" selection.
        Sample result:
            [
                ('Alicia', 'Alicia'), ('Amanda', 'Amanda'), ('Amy', 'Amy'),
                ...
                ('William', 'William'), ('Yolanda', 'Yolanda'), ('Yvette', 'Yvette'),
            ]
        """
        try:
            if field.model == self.model:
                queryset = self.get_initial_queryset(request)
            else:
                queryset = self.get_foreign_queryset(request, field)
            values = list(queryset
                .values_list(field.name, flat=True)
                .distinct()
                .order_by(field.name)
            )

            # Make sure initial_search_value is available
            if initial_search_value is not None:
                if initial_search_value not in values:
                    values.append(initial_search_value)

            if isinstance(field, models.DateField):
                choices = [(item, format_datetime(item)) for item in values]
            else:
                max_length = column_spec['max_length']
                if max_length <= 0:
                    choices = [(item, item) for item in values]
                else:
                    choices = [
                        (item, self.clip_value(str(item), max_length, False))
                        for item in values
                    ]

        except Exception as e:
            # TODO: investigate what happens here with FKs
            print('ERROR: ' + str(e))
            choices = []
        return choices
