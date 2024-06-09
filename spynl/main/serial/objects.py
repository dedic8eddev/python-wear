"""
Here we define more custom (de)serialisations for objects.
Here, we do text/unicode(utf-8) conversions.
Furthermore, we apply (de)serialisation which plugins can define for object
types like IDs or dates.
"""
from pyramid import threadlocal

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import (
    date_format_str,
    date_from_str,
    date_to_str,
    localize_date,
)
from spynl.main.utils import get_logger, get_settings


class SpynlDecoder(object):
    """
    (Incoming) Decodes Python objects from strings.
    It provides a function that routes to custom
    decoders for certain fields.
    """

    def __init__(self, context=None):
        """Enable the decoding functions to be context-aware."""
        self.context = context

    def __call__(self, dic):
        """
        Decode dic.
        In the setting serial_decode_functions, decoding functions are defined
        for specific fields. We use those functions for those fields.

        In the end, all keys that are still a string, are decoded as unicode.

        All the custom decode functions need to get the dic as an argument,
        so they change the dic and not a copy.
        They also get the context of the request.
        """
        settings = get_settings()
        decode_functions = settings.get('serial_decode_functions', {})
        for fieldname in dic:
            if fieldname in decode_functions:
                decode_functions[fieldname](
                    dic, fieldname=fieldname, context=self.context
                )

        # All remaining strings: we use unicode internally
        # & we expect incoming strings to be UTF-8 encoded
        for k in dic:
            if isinstance(dic[k], bytes):
                dic[k] = str(dic[k], errors='strict', encoding='utf-8')

        return dic


def encode(obj):
    """
    (Outgoing) Encodes a Python object to str.

    In serial_encode_functions, functions are defined for specific object
    types. We use those specific functions to encode those types.
    """
    # type specific casting:
    settings = get_settings()
    encode_functions = settings.get('serial_encode_functions', {})
    for obj_type in encode_functions:
        if isinstance(obj, obj_type):
            obj = encode_functions[obj_type](obj)

    return str(obj)


def add_decode_function(config, function, fields):
    """
    Add the specified function to the fields in the serial_decode_functions
    dictionary.
    example serial_decode_functions: {'_id': decode_id, 'date': decode_date}
    """
    log = get_logger('spynl.main.serial')
    settings = config.get_settings()
    decode_functions = settings.get('serial_decode_functions', {})
    for field in fields:
        if decode_functions.get(field) is not None:
            log.warning(
                'A custom decoding function for field %s is being overwritten.', field
            )
        decode_functions[field] = function
    if function.__code__.co_argcount != 3:
        log.warning('Custom decoding functions should have three arguments.')
    # line below needed if setting was not initialised before
    config.add_settings(serial_decode_functions=decode_functions)


def add_encode_function(config, function, obj_type):
    """
    Add the specified function to the types in the serial_encode_functions
    dictionary.
    example serial_decode_functions: {bool: encode_boolean, datetime:
    encode_datetime}
    """
    log = get_logger('spynl.main.serial')
    settings = config.get_settings()
    encode_functions = settings.get('serial_encode_functions', {})
    if encode_functions.get(obj_type) is not None:
        log.warning('You are replacing the encoding function for type %s', obj_type)
    encode_functions[obj_type] = function
    # line below needed if setting was not initialised before
    config.add_settings(serial_encode_functions=encode_functions)


def decode_date(dic, fieldname, context):
    """Localize date to UTC"""
    try:
        dic[fieldname] = localize_date(date_from_str(dic[fieldname]), tz='UTC')
    except Exception:
        raise ValueError(
            _(
                'date-decode-value-error',
                mapping={
                    'value': dic[fieldname],
                    'key': fieldname,
                    'format': date_format_str(),
                },
            )
        )


def encode_boolean(obj):
    """lower the case to get a json/js boolean"""
    return str(obj).lower()


def encode_date(obj):
    """localize the date and make it a string"""
    return date_to_str(localize_date(obj))


def encode_spynl_translation_string(obj):
    """determine the locale of the request and translate the string"""
    request = threadlocal.get_current_request()
    # import pdb; pdb.set_trace()
    localizer = request.localizer
    return obj.translate(localizer)
