
from django.db.models import fields
from django.db.models import Q
from django.db import models
from .utils import parse_date


def build_column_filter(column_name, column_obj, column_spec, search_value):
    search_filter = None

    # if type(column_obj.model_field) == fields.CharField:
    #     # do something special with this field

    choices = column_spec['choices']
    if column_obj.has_choices_available:

        if choices:
            # Since we're using choices (we provided a select box)
            # just use the selected key
            values = [search_value, ]
        else:
            values = column_obj.search_in_choices(search_value)

        search_filter = Q(**{column_obj.name + '__in': values})

    elif isinstance(column_obj.model_field, (models.DateTimeField, models.DateField)):
        try:
            parsed_date = parse_date(search_value)
            date_range = [parsed_date.isoformat(), parsed_date.isoformat()]
            query_param_name = column_obj.get_field_search_path()
            if isinstance(column_obj.model_field, models.DateTimeField):
                search_filter = Q(**{query_param_name + '__date__range': date_range})
            else:
                search_filter = Q(**{query_param_name + '__range': date_range})
        except ValueError:
            pass
    else:
        query_param_name = column_obj.get_field_search_path()
        #search_filters |= Q(**{query_param_name + '__istartswith': search_value})
        search_filter = Q(**{query_param_name + '__icontains': search_value})

    return search_filter
