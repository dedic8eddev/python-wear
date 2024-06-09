"""
This module provides information for version, db, build and enviroment.
"""

import datetime
import json
import os
import sys
import time

from pyramid.i18n import negotiate_locale_name

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import date_to_str, now
from spynl.main.exceptions import SpynlException
from spynl.main.utils import get_settings


def hello(request):
    """
    The index for all about-endpoints.

    ---
    get:
      description: >
        The index for all about-endpoints.

        ### Response

        JSON keys | Content Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | 'ok' or 'error'\n
        message   | string | Information about the available about/*
        endpoints.\n
        spynl_version | string | The version of the spynl package in this
        instance.\n
        plugins | dict | For each installed spynl plugin, the name as key
        and the version as value.\n
        language  | string | The language (e.g. "en") served.\n
        time      | string | Time\n

      tags:
        - about
    """
    try:
        with open(os.path.join(sys.prefix, 'versions.json')) as f:
            versions = json.loads(f.read())
    except FileNotFoundError:
        raise SpynlException('Version information not found')

    return {
        'message': _('about-message'),
        'versions': versions,
        'language': negotiate_locale_name(request),
        'time': date_to_str(now()),
    }


def versions(request):
    """
    The changeset IDs of Spynl and all installed plugins.

    ---
    get:
      tags:
        - about
      description: >
        Requires 'read' permission for the 'about' resource.

        ### Response

        JSON keys | Content Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | 'ok' or 'error'\n
        spynl     | dict   | {commit: SCM commit id of the HEAD,
        version: package version, scmVersion: state of the working directory,
        will show version and commit, and dirty if the working directory
        contains uncommited changes}.\n
        plugins   | dict   | {spynl-plugin: {commit: SCM commit id of the HEAD,
        version: package version, scmVersion: state of the working directory,
        will show version and commit, and dirty if the working directory
        contains uncommited changes}} for each Spynl plugin.\n
        time      | string | time\n
    """
    try:
        with open(os.path.join(sys.prefix, 'versions.json')) as f:
            response = json.loads(f.read())
        response['time'] = date_to_str(now())
    except FileNotFoundError:
        raise SpynlException('Version information not found')
    return response


def build(request):
    """
    Information about the build of this instance.

    ---
    get:
      tags:
        - about
      description: >

        ### Response

        JSON keys | Content Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | 'ok' or 'error'\n
        build_time| string | time\n
        start_time| string | time\n
        build_number | string | The build number\n
        spynl_function| string | Which functionality this node has been spun up
        to fulfil\n
        time      | string | time in format\n
    """
    spynl_settings = get_settings()
    response = {}

    response['time'] = date_to_str(now())
    response['build_time'] = spynl_settings.get('spynl.app.build_time', None)
    response['start_time'] = spynl_settings.get('spynl.app.start_time', None)
    response['spynl_function'] = spynl_settings.get('spynl.app.function', None)
    response['build_number'] = spynl_settings.get('spynl.app.build_number', None)

    return response


def spynl_sleep(request):
    t1 = datetime.datetime.utcnow()
    time.sleep(request.json_body['sleep'])
    t2 = datetime.datetime.utcnow()
    return {'t1': t1, 't2': t2, 'delta': t2 - t1}
