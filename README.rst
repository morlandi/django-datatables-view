
Django Datatables Server-Side
=============================

This package provides an easy way to process Datatables queries in the server-side mode.

Adapted from:

https://github.com/monnierj/django-datatables-server-side_


Installation
------------

Install the package by running:

.. code:: bash

    pip install git+https://github.com/morlandi/django-datatables-view

Add 'datatables_view' to your INSTALLED_APPS:

INSTALLED_APPS = [
    ...
    'datatables_view',
]


Pre-requisites
--------------

Your base template should include what required by `datatables.net`, plus:

- /static/datatables_view/css/style.css
- /static/datatables_view/js/datatables_utils.js

Example:

.. code:: html

    {% block extrastyle %}

        <link href="{% static 'datatables_view/css/style.css' %}" rel="stylesheet" />

        <link rel='stylesheet' href="{% static 'datatables.net-bs/css/dataTables.bootstrap.min.css' %}"></script>
        <link rel='stylesheet' href="{% static 'datatables.net-buttons-bs/css/buttons.bootstrap.min.css' %}"></script>

    {% endblock extrastyle %}

    {% block extrajs %}

        <script type="text/javascript" src="{% static 'datatables_view/js/datatables_utils.js' %}"></script>

        <script src="{% static 'datatables.net/js/jquery.dataTables.min.js' %}"></script>
        <script src="{% static 'datatables.net-bs/js/dataTables.bootstrap.min.js' %}"></script>
        <script src="{% static 'datatables.net-buttons/js/dataTables.buttons.min.js' %}"></script>
        <script src="{% static 'datatables.net-buttons/js/buttons.print.min.js' %}"></script>
        <script src="{% static 'datatables.net-buttons/js/buttons.html5.min.js' %}"></script>
        <script src="{% static 'datatables.net-buttons-bs/js/buttons.bootstrap.min.js' %}"></script>
        <script src="{% static 'jszip/dist/jszip.min.js' %}"></script>
        <script src="{% static 'pdfmake/build/pdfmake.min.js' %}"></script>
        <script src="{% static 'pdfmake/build/vfs_fonts.js' %}"></script>

    {% endcompress %}



DatatablesView-derived views
----------------------------

To provide server-side rendering of a Django Model, we need a specific
view which will be called via Ajax by the frontend.

At the very minimum, we shoud specify a suitable `column_defs` list.

Example:

`urls.py`

.. code:: python

    from django.urls import path
    from . import datatables_views

    app_name = 'frontend'

    urlpatterns = [
        ...
        path('datatable/program/', datatables_views.ProgramDatatablesView.as_view(), name="datatable_program"),
    ]


`datatables_views.py`

.. code:: python

    from django.contrib.auth.decorators import login_required
    from django.utils.decorators import method_decorator

    from datatables_view.views import DatatablesView
    from backend.models import Program


    @method_decorator(login_required, name='dispatch')
    class ProgramDatatablesView(DatatablesView):

        model = Program
        title = 'Programs'

        column_defs = [
            DatatablesView.render_row_tools_column_def(),
        {
            'name': 'id',
            'visible': True,
        }, {
            'name': 'start_datetime',
        }, {
            'name': 'end_datetime',
        }, {
            'name': 'favourite',
        }]



DATATABLES_VIEW_ENABLE_TRACING = True











# Django Datatables Server-Side
--------------
This package provides an easy way to process Datatables queries in the server-side mode.

All you have to do is to create a new view, configure which model has to be used
and which columns have to be displayed, and you're all set!

Supported features are pagination, column ordering and global search (not restricted to a specific column).
The searching function can find values in any string-convertible field, and also searched with choice
descriptions of predefined choices fields.

Foreign key fields can be used, provided that a QuerySet-like access path (i.e. model1__model2__field)
is given in the configuration.

## How to use these views
--------------

Just create a new view that inherits **DatatablesServerSideView**.
Here is a short example of a view that gives access to a simplistic model named *Employees*:

```python
class PeopleDatatableView(DatatablesServerSideView):
   # We'll use this model as a data source.
   model = Employees

   # Columns used in the DataTables
   columns = ['name', 'age', 'manager', 'department']

   # Columns in which searching is allowed
   searchable_columns = ['name', 'manager', 'department']

   # Replacement values for foreign key fields.
   # Here, the "manager" field points toward another employee.
   foreign_fields = {'manager': 'manager__name'}

   # By default, the entire collection of objects is accessible from this view.
   # You can change this behaviour by overloading the get_initial_queryset method:
   def get_initial_queryset(self):
       qs = super(PeopleDatatableView, self).get_initial_queryset()
       return qs.filter(manager__isnull=False)

   # You can also add data within each row using this method:
   def customize_row(self, row, obj):
       # 'row' is a dictionnary representing the current row, and 'obj' is the current object.
       row['age_is_even'] = obj.age%2==0
```

The views will return HTTPResponseBadRequests if the request is not an AJAX request,
or if parameters seems to be malformed.


App settings
------------

DATATABLES_VIEW_MAX_COLUMNS

    Default: 30

DATATABLES_VIEW_ENABLE_TRACING

    When True, enables debug tracing

    Default: False


Usage
=====


    model = Client
    title = _('Machines')
    initial_order = [[7, "desc"]]
    template_name = 'frontend/tables/base_datatables.html'

    column_defs = [
        DatatablesView.render_row_tools_column_def(),
    {
        'name': 'id',
        'visible': False,
    }, {
        'name': 'code',
    }, {
        'name': 'description',
    }, {
        'name': 'ip',
        "className": 'ip',
    }, {
        'name': 'vpn_address',
    }, {
        'name': 'system',
        'foreign_field': 'system__description',
    }, {
        'name': 'last_time_connected',
    }]

    def get_initial_queryset(self, request=None):
        if not request.user.view_all_clients:
            queryset = request.user.related_clients.all()
        else:
            queryset = super().get_initial_queryset(request)
        return queryset

    def customize_row(self, row, obj):
        # 'row' is a dictionnary representing the current row, and 'obj' is the current object.
        row['code'] = '<a class="client-status client-status-%s" href="%s">%s</a>' % (obj.status, reverse('frontend:client-detail', args=(obj.id,)), obj.code)
        return

    def render_row_details(self, id, request=None):
        client = self.model.objects.get(id=id)
        client_querysets = client.collect_querysets(include_recipes=True)

        stat_queryset = ClientStatistic.objects.filter(client=client)

        counters = stat_queryset.aggregate(
            Sum('custom_recipes_counter'),
            Sum('stock_recipes_counter'),
            Sum('purge_recipes_counter'),
            Sum('pigment_usage_total'),
        )

        pigment_usage_by_year = ClientStatistic.sum_by_year(stat_queryset, 'pigment_usage_total')

        y = datetime.date.today().year
        d = dict(pigment_usage_by_year)
        pigment_usage_this_year = d.get(y, 0)
        pigment_usage_previous_year = d.get(y - 1, 0)

        return render_to_string('frontend/pages/includes/client_row_details.html', {
            'client': client,
            'client_querysets': client_querysets,
            'editable': False,
            'counters': counters,

            # chartjs helpers:
            'pigment_usage_by_year__years': [item[0] for item in pigment_usage_by_year],
            'pigment_usage_by_year__data': [item[1] for item in pigment_usage_by_year],
            'pigment_usage_gauge_value': pigment_usage_this_year,
            'pigment_usage_gauge_max': max(pigment_usage_previous_year, pigment_usage_previous_year),
        })






