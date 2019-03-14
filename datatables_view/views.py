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
from django.template import TemplateDoesNotExist
from django.template import loader, Context


from .columns import Column
from .columns import ForeignColumn
from .columns import ColumnLink
from .columns import PlaceholderColumnLink
from .columns import Order
from .exceptions import ColumnOrderError
from .utils import prettyprint_queryset
from .utils import trace
from .app_settings import MAX_COLUMNS
from .app_settings import ENABLE_QUERYSET_TRACING
from .app_settings import ENABLE_QUERYDICT_TRACING


print('\x1b[41;1m' + " UNSTABLE RELEASE: datatables_view refactoring in progress " + '\x1b[0m')


class DatatablesView(View):

    # Either override in derived class, or override self.get_column_defs()
    column_defs = []

    model = None
    template_name = 'datatables_view/datatable.html'
    initial_order = [[1, "asc"]]
    length_menu = [[10, 20, 50, 100], [10, 20, 50, 100]]

    # Set with self.initialize()
    column_specs = []
    model_columns = {}
    show_date_filters = None

    def initialize(self, request):

        # Grab column defs and initialize self.column_specs
        column_defs_ex = self.get_column_defs(request)
        self.column_specs = []
        for c in column_defs_ex:

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
                column['searchable'] = c.get('searchable', column['visible'])
                column['orderable'] = c.get('orderable', column['visible'])

            self.column_specs.append(column)

        if ENABLE_QUERYDICT_TRACING:
            trace(self.column_specs, prompt='column_specs')

        # Initialize model columns
        self.model_columns = Column.collect_model_columns(
            self.model,
            self.column_specs
        )

        # Initialize "show_date_filters"
        date_filters = self.get_show_date_filters(request)
        # If derived class sets 'show_date_filters', respect it;
        # otherwise set according to model 'get_latest_by' attribute
        if date_filters is None:
            date_filters = getattr(self.model._meta, 'get_latest_by', None) != None
        self.show_date_filters = date_filters

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

    def get_show_date_filters(self, request):
        """
        Override to customize based of request.
        Return either True, False or None.
        None = check 'get_latest_by' in model's Meta.
        """
        return self.show_date_filters

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        self.initialize(request)
        if request.is_ajax():
            action = request.GET.get('action', '')
            if action == 'initialize':
                return JsonResponse({
                    'columns': self.column_specs,
                    'order': self.get_initial_order(request),
                    'length_menu': self.get_length_menu(request),
                    'show_date_filters': self.show_date_filters,
                })
            elif action == 'details':
                return JsonResponse({
                    'html': self.render_row_details(request.GET.get('id'), request),
                })

            response = super(DatatablesView, self).dispatch(request, *args, **kwargs)
        else:
            assert False
            #response = HttpResponse(self.render_table(request))
        return response

    # def render_row_details(self, id, request=None):
    #     obj = self.model.objects.get(id=id)
    #     fields = [f.name for f in self.model._meta.get_fields() if f.concrete]
    #     html = '<table class="row-details">'
    #     for field in fields:
    #         try:
    #             value = getattr(obj, field)
    #             html += '<tr><td>%s</td><td>%s</td></tr>' % (field, value)
    #         except:
    #             pass
    #     html += '</table>'
    #     return html

    def get_model_admin(self):
        from django.contrib import admin
        if self.model in admin.site._registry:
            return admin.site._registry[self.model]
        return None

    def render_row_details(self, id, request=None):

        obj = self.model.objects.get(id=id)

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

    def get(self, request, *args, **kwargs):

        if not request.is_ajax():
            return HttpResponseBadRequest()

        try:
            query_dict = request.GET
            params = self.read_parameters(query_dict)
        except ValueError:
            return HttpResponseBadRequest()

        if ENABLE_QUERYDICT_TRACING:
            trace(query_dict, prompt='query_dict')
            trace(params, prompt='params')

        # Prepare the queryset and apply the search and order filters
        qs = self.get_initial_queryset(request)
        qs = self.prepare_queryset(params, qs)
        if ENABLE_QUERYSET_TRACING:
            prettyprint_queryset(qs)

        # Slice result
        paginator = Paginator(qs, params['length'])
        response_dict = self.get_response_dict(paginator, params['draw'], params['start'])
        response_dict['footer_callback_message'] = self.footer_callback_message(qs, params)

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
                            self.model_columns[column_name],
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

    def render_column(self, row, column):
        return self.model_columns[column].render_column(row)

    def prepare_results(self, qs):
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
        searchable_columns = [c['name'] for c in self.column_specs if c.get('searchable', True if c['name'] and c['visible'] else False)]
        for col in searchable_columns:
            model_column = self.model_columns[col]

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
        model_column = self.model_columns[column_name]

        if model_column.has_choices_available:
            search_filters |=\
                Q(**{column_name + '__in': model_column.search_in_choices(search_value)})
        else:
            query_param_name = model_column.get_field_search_path()
            search_filters |=\
                Q(**{query_param_name+'__icontains': search_value})
                #Q(**{query_param_name+'__istartswith': search_value})

        return qs.filter(search_filters)

    def footer_callback_message(self, qs, params):
        #return 'Selected rows: %d' % qs.count()
        return ''
