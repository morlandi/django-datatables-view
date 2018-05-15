# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from django.utils import six

import datetime
import json
from django.views.generic import View
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string


from .columns import Column
from .columns import ForeignColumn
from .columns import ColumnLink
from .columns import PlaceholderColumnLink
from .columns import Order
from .exceptions import ColumnOrderError
from .utils import prettyprint_queryset
from .utils import trace
from .utils import trace_func
from .app_settings import MAX_COLUMNS


class DatatablesView(View):

    columns = []
    searchable_columns = []
    foreign_fields = {}
    model = None
    template_name = 'datatables_view/datatable.html'
    initial_order = [[1, "asc"]]
    length_menu = [[10, 20, 50, 100], [10, 20, 50, 100]],
    column_defs = None

    def __init__(self, *args, **kwargs):

        if self.column_defs:
            self.parse_column_defs(self.column_defs)

        columns = kwargs.pop('columns', None)
        if columns is not None:
            self.columns = columns
        foreign_fields = kwargs.pop('foreign_fields', None)
        if foreign_fields is not None:
            self.foreign_fields = foreign_fields
        searchable_columns = kwargs.pop('searchable_columns', None)
        if searchable_columns is not None:
            self.searchable_columns = searchable_columns

        super(DatatablesView, self).__init__(*args, **kwargs)
        self._model_columns = Column.collect_model_columns(self.model, self.columns, self.foreign_fields)

    def parse_column_defs(self, column_defs):
        """
        Use column_defs to initialize internal variables

        Example:

            column_defs = [{
                'name': 'currency',
                'title': 'Currency',
                'searchable': True,
                'orderable': True,
                'visible': True,
                'foreign_field': None,  # example: 'manager__name',
                'placeholder': False,
                'className': 'css-class-currency',
            }, {
                'name': 'active',
                ...

        """

        self.columns = []
        self.searchable_columns = []
        self.foreign_fields = {}

        for column_def in column_defs:
            name = column_def['name']
            self.columns.append(name)
            if column_def.get('searchable', True if name else False):
                self.searchable_columns.append(name)
            if column_def.get('foreign_field', None):
                self.foreign_fields[name] = column_def['foreign_field']

    def list_columns(self):
        columns = []
        for c in self.column_defs:

            # name = c.get('name', '')
            # import ipdb; ipdb.set_trace()

            column = {
                #'name': '',
                'data': None,
                'title': '',
                'searchable': False,
                'orderable': False,
                'visible': True,
            }

            column.update(c)

            if c['name']:

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
                column['searchable'] = c.get('searchable', True)
                column['orderable'] = c.get('orderable', True)

            columns.append(column)

        trace(columns, prompt='list_columns()')

        return columns

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        if request.is_ajax():
            # # if settings.DEBUG:
            # #     trace(str(self.request.GET))
            # if 'export' in request.GET:
            #     return self.export_data(request)
            action = request.GET.get('action', '')

            if action == 'render':
                return JsonResponse({
                    'html': self.render_table(request),
                    'columns': self.list_columns(),
                    'order': self.initial_order,
                    'length_menu': self.length_menu,
                })
            elif action == 'details':
                return JsonResponse({
                    'html': self.render_row_details(request.GET.get('id'), request),
                })

            response = super(DatatablesView, self).dispatch(request, *args, **kwargs)
        else:
            response = HttpResponse(self.render_table(request))
        return response

    def render_row_details(self, id, request=None):
        obj = self.model.objects.get(id=id)
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
        }
        return column_def

    def render_table(self, request):

        template_name = self.template_name

        # When called via Ajax, use the "smaller" template "<template_name>_inner.html"
        if request.is_ajax():
            template_name = getattr(self, 'ajax_template_name', '')
            if not template_name:
                split = self.template_name.split('.html')
                split[-1] = '_inner'
                split.append('.html')
                template_name = ''.join(split)

        html = render_to_string(
            template_name, {
                'title': self.title,
                'columns': self.list_columns(),
                'column_details': mark_safe(json.dumps(self.list_columns())),
                'initial_order': mark_safe(json.dumps(self.initial_order)),
                'length_menu': mark_safe(json.dumps(self.length_menu)),
                'view': self,
                'show_date_filter': self.model._meta.get_latest_by is not None,
            },
            request=request
        )

        return html

    def get(self, request, *args, **kwargs):

        if not request.is_ajax():
            return HttpResponseBadRequest()

        try:
            query_dict = request.GET
            params = self.read_parameters(query_dict)
        except ValueError:
            return HttpResponseBadRequest()

        trace(query_dict, prompt='query_dict')
        trace(params, prompt='params')

        # Prepare the queryset and apply the search and order filters
        qs = self.get_initial_queryset(request)
        qs = self.prepare_queryset(params, qs)
        prettyprint_queryset(qs, prompt='queryset')

        # Slice result
        paginator = Paginator(qs, params['length'])
        response_dict = self.get_response_dict(paginator, params['draw'], params['start'])
        response_dict['total_html'] = self.total_html(qs, params)

        return HttpResponse(
            json.dumps(
                response_dict,
                cls=DjangoJSONEncoder
            ),
            content_type="application/json")

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

        while column_index < MAX_COLUMNS and\
                not has_finished:
            column_base = 'columns[%d]' % column_index

            try:
                column_name = query_dict[column_base + '[name]']
                if column_name == '':
                    column_name = query_dict[column_base + '[data]']

                if column_name != '':
                    column_links.append(
                        ColumnLink(
                            column_name,
                            self._model_columns[column_name],
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
        while order_index < len(self.columns) and not has_finished:
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

    def render_column(self, row, column):
        return self._model_columns[column].render_column(row)

    def prepare_results(self, qs):
        json_data = []

        for cur_object in qs:
            retdict = {
                #fieldname: '<div class="field-%s">%s</div>' % (fieldname, self.render_column(cur_object, fieldname))
                fieldname: self.render_column(cur_object, fieldname)
                for fieldname in self.columns
                if fieldname
            }
            self.customize_row(retdict, cur_object)
            json_data.append(retdict)
        return json_data

    def get_response_dict(self, paginator, draw_idx, start_pos):
        page_id = (start_pos // paginator.per_page) + 1
        if page_id > paginator.num_pages:
            page_id = paginator.num_pages
        elif page_id < 1:
            page_id = 1

        objects = self.prepare_results(paginator.page(page_id))

        return {"draw": draw_idx,
                "recordsTotal": paginator.count,
                "recordsFiltered": paginator.count,
                "data": objects,
                }

    def customize_row(self, row, obj):
        # 'row' is a dictionnary representing the current row, and 'obj' is the current object.
        #row['age_is_even'] = obj.age%2==0
        pass

    def prepare_queryset(self, params, qs):
        qs = self.filter_queryset(params, qs)
        qs = self.sort_queryset(params, qs)
        return qs

    def filter_queryset(self, params, qs):

        # Apply date range filters
        get_latest_by = getattr(self.model._meta, 'get_latest_by', None)
        if get_latest_by:
            date_from = params.get('date_from', None)
            if date_from:
                dt = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
                qs = qs.filter(**{get_latest_by+'__date__gte': dt})
            date_to = params.get('date_to', None)
            if date_to:
                dt = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
                qs = qs.filter(**{get_latest_by+'__date__lte': dt})

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

    def choice_field_search(self, column, search_value):
        values_dict = self.choice_fields_completion[column]
        matching_choices = [val for key, val in six.iteritems(values_dict)
                            if key.startswith(search_value)]
        return Q(**{column + '__in': matching_choices})


    def filter_queryset_all_columns(self, search_value, qs):
        search_filters = Q()
        for col in self.searchable_columns:
            model_column = self._model_columns[col]

            if model_column.has_choices_available:
                search_filters |=\
                    Q(**{col + '__in': model_column.search_in_choices(
                        search_value)})
            else:
                query_param_name = model_column.get_field_search_path()

                search_filters |=\
                    Q(**{query_param_name+'__icontains': search_value})
                    #Q(**{query_param_name+'__istartswith': search_value})

        return qs.filter(search_filters)

    def filter_queryset_by_column(self, column_name, search_value, qs):
        search_filters = Q()
        model_column = self._model_columns[column_name]

        if model_column.has_choices_available:
            search_filters |=\
                Q(**{column_name + '__in': model_column.search_in_choices(search_value)})
        else:
            query_param_name = model_column.get_field_search_path()
            search_filters |=\
                Q(**{query_param_name+'__icontains': search_value})
                #Q(**{query_param_name+'__istartswith': search_value})

        return qs.filter(search_filters)

    def total_html(self, qs, params):
        return 'Righe selezionate: %d' % qs.count()

