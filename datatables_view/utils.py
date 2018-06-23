import pprint
from django.utils import timezone
from django.conf import settings
from django.utils import formats


try:
    import sqlparse
except ImportError:
    class sqlparse:
        @staticmethod
        def format(text, *args, **kwargs):
            return text


def trace(message, prompt=''):
    print('\x1b[1;36;40m', end='')
    if prompt:
        print(prompt + ':')
    pprint.pprint(message)
    print('\x1b[0m\n', end='')


def prettyprint_queryset(qs):
    print('\x1b[1;33;40m', end='')
    message = sqlparse.format(str(qs.query), reindent=True, keyword_case='upper')
    print(message)
    print('\x1b[0m\n')


def format_datetime(dt, include_time=True):
    """
    Here we adopt the following rule:
    1) format date according to active localization
    2) append time in military format
    """
    if dt is None:
        return ''

    dt = timezone.localtime(dt)

    use_l10n = getattr(settings, 'USE_L10N', False)
    text = formats.date_format(dt, use_l10n=use_l10n, format='SHORT_DATE_FORMAT')
    if include_time:
        text += dt.strftime(' %H:%M:%S')
    return text
