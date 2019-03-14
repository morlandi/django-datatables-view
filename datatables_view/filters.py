
from django.db.models import fields
from django.db.models import Q


def build_column_filter(column_name, column_obj, search_value):
    search_filter = None

    # if type(column_obj.model_field) == fields.CharField:
    #     # do something special with this field

    if column_obj.has_choices_available:
        search_filter = Q(**{column_obj.name + '__in': column_obj.search_in_choices(search_value)})
    else:
        query_param_name = column_obj.get_field_search_path()
        #search_filters |= Q(**{query_param_name + '__istartswith': search_value})
        search_filter = Q(**{query_param_name + '__icontains': search_value})

    return search_filter
