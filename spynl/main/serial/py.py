"""function to dump python objects"""

from io import StringIO
from pprint import pprint


def dumps(body, pretty=False):
    """Return Python objects in body in text representation"""
    if pretty:
        stream = StringIO()
        pprint(body, stream=stream)
        return stream.getvalue()

    return repr(body)
