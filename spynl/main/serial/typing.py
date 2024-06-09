"""
Deal with content types in a generic way. Negotiate incoming content types.
"""
from mimetypes import guess_type

from spynl.main.serial import csv, html, json, py, yaml
from spynl.main.serial.exceptions import (
    UndeterminedContentTypeException,
    UnsupportedContentTypeException,
)

handlers = {
    'application/json': {'dump': json.dumps, 'load': json.loads, 'sniff': json.sniff},
    'application/x-yaml': {'dump': yaml.dumps, 'load': yaml.loads, 'sniff': yaml.sniff},
    'text/csv': {'dump': csv.dumps, 'load': csv.loads, 'sniff': csv.sniff},
    'text/html': {'dump': html.dumps},
    'text/x-python': {'dump': py.dumps},
}


def negotiate_request_content_type(request):
    """
    Negotiate and return a content type for this request.
    Priorisation:
    1. Content-Type Header
    2. Body sniffing
    Throw an Exception when can't find a type (but have a body) or
    if we end up with a type we don't know
    (but the request method is POST|PUT).
    """
    content_type = request.content_type
    if not content_type or content_type not in handlers:
        for key, values in handlers.items():
            if 'sniff' in values and values['sniff'](request.text):
                return key

    if not content_type:
        if not request.body:
            return None
        raise UndeterminedContentTypeException()

    if content_type not in handlers and request.method in ('POST', 'PUT'):
        raise UnsupportedContentTypeException(content_type)

    return content_type


def negotiate_response_content_type(request):
    """
    Negotiate and return a content type to be used in the response.

    Priorisation:
    1. file extension in the URL
    2. Accept Header (only first mentioned type)
    3. Originally set Content-Type (e.g. browser default or set by a view)
    4. Spynl default (application/json)
    """
    content_type = None
    if hasattr(request, 'path_extension'):
        if request.path_extension:
            content_type = request.path_extension

    accept_type = None
    if 'Accept' in request.headers:
        accept_type = request.headers['Accept'].split(',')[0]
    # we use accept only if it is not one of the general types
    if not content_type and accept_type and accept_type not in ('text/html', '*/*'):
        content_type = accept_type

    if not content_type:
        content_type = request.response.content_type

    if not content_type:
        content_type = 'application/json'

    # make proper type description if we only have a short name (e.g. 'csv')
    if content_type and '/' not in content_type:
        content_type = guess_type('file.' + content_type)[0]

    return content_type


def supported_types():
    """Return the types supported for serialisation"""
    return list(handlers.keys())
