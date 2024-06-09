"""Handle JSON content."""

import json
import re
from decimal import Decimal

from spynl.main.serial import objects
from spynl.main.serial.exceptions import MalformedRequestException


def loads(body, context=None, **kwargs):
    """Return body as JSON."""
    try:
        decoder = objects.SpynlDecoder(context)
        return json.loads(body, object_hook=decoder)
    except ValueError as err:
        raise MalformedRequestException('application/json', error_cause=str(err))


def dumps(body, pretty=False):
    """Return JSON body as string."""
    indent = 4 if pretty else None

    class JSONEncoder(json.JSONEncoder):
        """Custom JSONEncoder to encode the object."""

        def default(self, obj):  # pylint: disable=method-hidden
            if isinstance(obj, Decimal):
                return float(obj)
            if isinstance(obj, set):
                return list(obj)
            return objects.encode(obj)

    return json.dumps(body, indent=indent, ensure_ascii=False, cls=JSONEncoder)


def sniff(body):
    """
    sniff to see if body is a json object.

    Body should start with any amount of whitespace and a {.
    """
    expression = re.compile(r'^\s*\{')
    return bool(re.match(expression, body))
