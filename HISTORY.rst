.. :changelog:

History
=======

v2.1.2
------
* basic support for DateField and DateTimeField filtering (exact date match)

v2.1.1
------
* choices lookup revised

v2.1.0
------
* `static/datatables_view/js/datatables_utils.js` renamed as `static/datatables_view/js/utils.js`
* js helper encapsulated in DatatablesViewUtils module
* First "almost" working column filtering - good enought for text search

v2.0.6
------
* Accept either GET or POST requests

v2.0.5
------
* Global "get_latest_by" filtering improved

v2.0.4
------
* Filter tracing (for debugging)

v2.0.0
------
* DatatablesView refactoring: columns_specs[] used as a substitute for columns[],searchable_columns[] and foreign_fields[]

v1.2.4
------
* recognize datatime.date column type

v1.2.3
------
* render_row_details() passes model_admin to the context, to permit fieldsets navigation

v1.2.2
------
* generic tables explained
* render_row_details customizable via templates

v1.2.1
------
* merged PR #1 from Thierry BOULOGNE

v1.2.0
------
* Incompatible change: postpone column initialization and pass the request to get_column_defs() for runtime table layout customization

v1.0.1
------
* fix choices lookup

v1.0.0
------
* fix search
* better distribution (make sure templates and statics are included)

v0.0.2
------
* Package version added
