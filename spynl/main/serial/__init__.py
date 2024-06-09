"""
The serial module handles incoming and outgoing data streams.
It performs serialisation/deserialisation of the whole stream (for several data
formats,e.g. json), as well as  some for specific data (e.g. for dates).

Our policy is as follows:
* We deal with text internally as unicode
* We expect incoming strings to be UTF-8 encoded.
* As internal representation of incoming data we use a dictionary, with values
either being text or specific objects (e.g. datetime objects).
* Everything outgoing is serialised to a unicode text, as well as the data
format allows (see e.g. the .csv part).
Here, the module can also do some pretty-printing if wanted.

The main utility functions of this module are parse_post_data and renderer,
they are added to config in main.
"""

from datetime import datetime

from pyramid.httpexceptions import HTTPBadRequest
from pyramid.settings import asbool

from spynl.locale import SpynlTranslationString

from spynl.main.serial.exceptions import (
    DeserializationUnsupportedException,
    MalformedRequestException,
    SerializationUnsupportedException,
    UndeterminedContentTypeException,
    UnsupportedContentTypeException,
)
from spynl.main.serial.objects import (
    add_decode_function,
    add_encode_function,
    decode_date,
    encode_boolean,
    encode_date,
    encode_spynl_translation_string,
)
from spynl.main.serial.typing import handlers, negotiate_response_content_type


def parse_post_data(request):
    """Parse data according to the requests content type."""
    context = None
    if hasattr(request, 'context') and request.context:
        context = request.context
    try:
        parsed_body = loads(
            request.text, request.content_type, request.headers, context
        )
    except MalformedRequestException as e:
        raise HTTPBadRequest(detail=e.message.translate(request.localizer))

    return parsed_body


def renderer(values, system):
    """
    Render data which the view created as a response.

    Spynl endpoints usually return dictionaries as responses, which
    this module renders in the content type set on the request
    (see parse_post_data).
    If spynl.pretty is set, formatting (pretty-printing) is done.
    """
    r = system['request']
    if not isinstance(system['context'], Exception):
        r.response.content_type = negotiate_response_content_type(r)

    if r.response.content_type == 'application/json' and 'status' not in values:
        values['status'] = 'ok'

    pretty = asbool(r.registry.settings.get('spynl.pretty'))
    try:
        response = dumps(values, r.response.content_type, pretty=pretty)
    except UnsupportedContentTypeException:
        raise UndeterminedContentTypeException()

    return response


# ---- high-level dumps and loads functions,
#      relay to specific dumps and loads per type


def dumps(body, content_type, pretty=False):
    """Relay to content-type specific dumping."""
    try:
        handler = handlers[content_type]
    except KeyError:
        raise UnsupportedContentTypeException(content_type)

    try:
        dump = handler['dump']
    except KeyError:
        raise SerializationUnsupportedException(content_type)

    return dump(body, pretty=pretty)


def loads(body, content_type, headers=None, context=None):
    """Relay to content-type specific load."""
    if not body:
        return {}

    try:
        handler = handlers[content_type]
    except KeyError:
        raise UnsupportedContentTypeException(content_type)

    try:
        load = handler['load']
    except (AttributeError, KeyError):
        raise DeserializationUnsupportedException(content_type)

    return load(body, headers=headers, context=context)


def main(config):
    """
    Add our main utility functions to be used in the config,
    to render output and parse post data
    Define decoding and encoding functions for objects
    """
    config.add_settings(
        {'spynl.renderer': renderer, 'spynl.post_parser': parse_post_data}
    )
    # define decode function for date fields:
    add_decode_function(config, decode_date, ['date'])
    # define encoding functions
    add_encode_function(config, encode_date, datetime)
    add_encode_function(config, encode_boolean, bool)
    add_encode_function(config, encode_spynl_translation_string, SpynlTranslationString)
