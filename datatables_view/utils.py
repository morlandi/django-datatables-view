import pprint
from django.utils import timezone
from django.utils import formats
from .app_settings import ENABLE_TRACING


try:
    import sqlparse
except ImportError:
    class sqlparse:
        @staticmethod
        def format(text, *args, **kwargs):
            return text

def trace(message, colorize=True, prettify=True, prompt=''):

    if not ENABLE_TRACING: return
    if colorize: print('\x1b[1;33;40m', end='')
    if prompt:
        print(prompt+ ':')

    # if type(message) is list:
    #     text = ' '.join([str(item) for item in message])
    # else:
    #     text = str(message)
    # if prettify:
    #     text = pprint.pformat(text)
    # print(text)
    if prettify:
        pprint.pprint(message)
    else:
        print(message)

    if colorize: print('\x1b[0m', end='')


def prettyprint_query(query, colorize=True, prompt=''):
    if not ENABLE_TRACING: return
    trace(sqlparse.format(query, reindent=True, keyword_case='upper'))


def prettyprint_queryset(qs, colorize=True, prompt=''):
    if not ENABLE_TRACING: return
    prettyprint_query(str(qs.query), colorize=True, prompt=prompt)


def trace_func(fn):
    """
    Sample usage:

        class MyClass(object):
            ...

            @trace_func
            def myfunc(self, user, obj):
                ...
    """
    def func_wrapper(*args, **kwargs):
        if ENABLE_TRACING:
            trace('>>> %s()' % fn.__name__)
            trace('> args:')
            trace(args)
            trace('> kwargs:')
            trace(kwargs)
        ret = fn(*args, **kwargs)
        if ENABLE_TRACING:
            trace('> return value:')
            trace(ret)
            trace('<<< %s()' % fn.__name__)
        return ret
    return func_wrapper


def format_datetime(dt, include_time=True):
    """
    Here we adopt the following rule:
    1) format date according to active localization
    2) append time in military format
    """
    if dt is None:
        return ''

    dt = timezone.localtime(dt)

    text = formats.date_format(dt, use_l10n=True, format='SHORT_DATE_FORMAT')
    if include_time:
        text += dt.strftime(' %H:%M:%S')
    return text
