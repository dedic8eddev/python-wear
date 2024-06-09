"""
Module for parsing docstrings and making the .json file for swagger-ui
"""

import json
import os
import re

import yaml

from spynl.main.dateutils import SPYNL_DATE_FORMAT
from spynl.main.utils import get_logger, get_yaml_from_docstring
from spynl.main.version import __version__ as spynl_version

EXTENDED_DESCRIPTION = '''
The format spynl uses to return dates is: {}. <br/> All endpoints usually return
application/json, unless otherwise specified here or requested differently by the
request. They will have a "status" (ok|error) field and all error responses also will
have a "message" field.<br/>
Some resource-based endpoints can be prepended by "/tenants/&lt;tenant-ID&gt;/",
which allows to access a different tenant than the currently set tenant.
'''.format(
    SPYNL_DATE_FORMAT
)


swagger_doc = {
    'swagger': '2.0',
    'info': {
        'version': spynl_version,
        'title': 'Spynl Endpoints',
        'description': 'A list of all endpoints on this Spynl instance,'
        ' with a short description on how to use them.'
        ' <br/><br/><span style="color: grey;">{}<span>'.format(EXTENDED_DESCRIPTION),
    },
    'paths': {},
    'definitions': {},
}


def document_endpoint(config, function, endpoint_name, resource=None):
    """parse docstring and store in swagger_doc dict"""
    log = get_logger('Spynl Documentation')

    path = '/{}'.format(endpoint_name)
    yaml_str = get_yaml_from_docstring(function.__doc__, load_yaml=False)

    if not yaml_str:
        log.warning(
            'No YAML found in docstring of endpoint %s (resource: %s). Cannot '
            'generate entry in /about/endpoints.',
            endpoint_name,
            resource,
        )
        return
    if resource:
        # Replace $resource in the docstring with the actual resource
        yaml_str = re.sub(r'\$resource', resource, yaml_str)
    try:
        yaml_doc = yaml.load(yaml_str, Loader=yaml.FullLoader)
        # If a path has a different view for get and post, add both
        if path in swagger_doc['paths']:
            swagger_doc['paths'][path].update(yaml_doc)
        else:
            swagger_doc['paths'][path] = yaml_doc
    except yaml.YAMLError as e:
        log.error('Wrong yaml code for endpoint %s:', path)
        log.error(e)
        return

    # the 1st line of a docstring can be used for the swagger summary
    docstring = function.__doc__
    doc_lines = docstring.split("\n")
    if doc_lines:
        first_doc_line = doc_lines[1].strip()
        if first_doc_line == '---':
            first_doc_line = ''
    for method in [m for m in ('get', 'post') if m in swagger_doc['paths'][path]]:
        path_doc = swagger_doc['paths'][path][method]
        if 'summary' not in path_doc or not path_doc['summary']:
            if resource:
                path_doc['summary'] = re.sub(r'\$resource', resource, first_doc_line)
            else:
                path_doc['summary'] = first_doc_line


def make_docs(config):
    """Write swagger file."""
    log = get_logger('Spynl Documentation')

    folder = 'spynl_swagger'
    if not os.path.exists(folder):
        os.makedirs(folder)

    # turn swagger_doc into a JSON file
    swagger_file = os.path.join(folder, 'spynl.json')
    try:
        with open(swagger_file, 'w') as outfile:
            json.dump(
                swagger_doc, outfile, indent=4, separators=(',', ': '), sort_keys=True
            )
    except IOError as e:
        log.error('I/O error(%s: %s', e.errno, e.strerror)
    except (TypeError, OverflowError, ValueError) as e:
        log.error('Swagger file could not be dumped:')
        log.error(e)
