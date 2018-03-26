
Adapted from:
https://github.com/monnierj/django-datatables-server-side


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
