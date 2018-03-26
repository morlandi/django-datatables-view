from django.conf import settings

MAX_COLUMNS = getattr(settings, 'DATATABLES_VIEW_MAX_COLUMNS', 30)
ENABLE_TRACING = getattr(settings, 'DATATABLES_VIEW_ENABLE_TRACING', False)
