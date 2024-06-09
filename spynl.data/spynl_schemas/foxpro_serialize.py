from functools import partial
from urllib.parse import quote

import pytz


def escape(val):
    """Escape a value to be safely included in a foxpro querystring."""
    # No characters other than alphanumerics and periods are safe. So we
    # provide an empty string to the safe parameter and encode - and _
    # ourselves.
    return quote(str(val), safe='').replace('-', '%2D').replace('_', '%5F')


def resolve(scope, path):
    """
    Resolve a (dot seperated) path from a dict. Defaulting to an empty string.

    It does not try to be smart about casting or catching exceptions.

    >>> d = { 'one': { 'two': 'value2' } }
    >>> resolve(d, 'one.two')
    'value2'
    >>> resolve(d, 'one.three')
    ''
    >>> resolve(d, 'one.two.three')
    AttributeError: 'str' object has no attribute 'get'
    """

    # base condition. The path is not nested.
    if '.' not in path:
        val = scope.get(path, '')
        if isinstance(val, bool):
            return str(val).lower()
        elif val is None:
            return ''
        else:
            return val

    head, tail = path.split('.', 1)
    scope = scope.get(head)
    # exit early
    if scope is None:
        return ''

    return resolve(scope, tail)


def serialize(queries, whitelist=None, pass_empty=False):
    """Serialize a list of queries to a proper foxpro querystring.

    whitelist is a list of (method, key) tuples that don't need to be escaped.

    Returns a list of tupes in the form of [method, querystring].
    """

    if whitelist is None:
        whitelist = []

    serialized = []

    for method, query in queries:
        querystring = method + '/'
        pairs = []

        for key, value in query:
            value = '' if value is None else value
            value = value if (method, key) in whitelist else escape(value)
            if (not pass_empty and value != '') or pass_empty:
                pairs.append(f'{key}__{value}')

        querystring += '/'.join(pairs)
        serialized.append((method, querystring))
    return serialized


def format_fp_date(date, datefmt):
    """Convert a datetime to a date string using the Amsterdam timezone"""
    return date.astimezone(pytz.timezone('Europe/Amsterdam')).strftime(datefmt)


fp_date = partial(format_fp_date, datefmt='%Y%m%d')
fp_datetime = partial(format_fp_date, datefmt='%Y-%m-%d %H:%M:%S')
