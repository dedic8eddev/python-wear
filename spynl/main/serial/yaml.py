"""Handle YAML content"""

import re

import yaml

from spynl.main.serial.exceptions import MalformedRequestException

EXPRESSION = re.compile(r'^\s*\-')


def sniff(body):
    """Sniff body content, return True if YAML detected"""
    return bool(re.match(EXPRESSION, body))


def dumps(body, pretty=False):
    """return YAML body as string"""
    return yaml.dump(body, indent=4) if pretty else yaml.dump(body)


def loads(body, headers=None, **kwargs):
    """return body as YAML"""
    try:
        return yaml.load(body)
    except ValueError as err:
        raise MalformedRequestException('application/x-yaml', error_cause=str(err))
