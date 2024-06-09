"""
Documentation endpoints:
* Helper functions and endpoint for documenting roles and acl's
* endpoint for application documentation

The document_roles function is run after all plugins have loaded, and contructs
the information about the resources and roles needed for the about/roles
endpoint at Spynl startup.
"""
import re

from pyramid.authorization import DENY_ALL, Authenticated
from pyramid.renderers import render

from spynl.main.utils import get_logger

from spynl.api.auth.apps_and_roles import APPLICATIONS, ROLES
from spynl.api.auth.utils import MASTER_TENANT_ID

# _resource_info and _role_info are constructed by document_roles at startup
# after all plugins have loaded.
# -----------------------------
# _resource_info is a dictionary of all resources with entries for
# the name, plugin, the associated paths and the ACLs of all the available
# resources.
_resource_info = {}
_resource_list = []  # list version of _resource_info for front-end use
# _role_info is a dictionary of all roles, with for each role entries for the
# name, the description, the resources the role has access to, and the ACEs for
# those resources. We start with the general roles dictionary, then add
# resource information as needed in document_roles.
_role_info = ROLES.copy()
_role_list = []  # list version of _role_info for front-end use


def document_roles(event):
    """
    construct the _resource_info and _role_info dictionaries

    This is done at startup, after all plugins have loaded (see plugger.py)
    """
    log = get_logger(__file__)
    resources = event.config.get_settings()['spynl.resources']

    # collect _resource_info:
    # We loop over all resources from the settings and collect their ACL, and
    # any applicable parent ACLs. For each resource we also store the
    # corresponding paths and the plugin it resides in.
    for resource in resources.values():
        if hasattr(resource, '__acl__'):
            if callable(getattr(resource, '__acl__')):
                # TODO: special handling for resources with dynamic acl's
                # (if a resource has dynamic acls, add a method document_acls's
                # that can be called here?)
                log.warninging('Please implement documentation of dynamic acls')
                acl = ['dynamicly generated']
            else:
                acl = resource.__acl__.copy()
        else:
            acl = []

        get_parents(resource, acl)

        # keep all permissions as tuples (TODO: could be moved to get_parents)
        for ace in [a for a in acl if isinstance(a, tuple)]:
            index = acl.index(ace)
            if not isinstance(ace[2], tuple):
                ace = list(ace)
                ace[2] = (ace[2],)
                acl[index] = tuple(ace)
            # check if there are unkown permissions:
            for permission in ace[2]:
                if permission not in ('edit', 'add', 'read', 'delete'):
                    log.warning(
                        "Unknown permission '%s' in resource '%s'.",
                        permission,
                        resource,
                    )

        _resource_info[resource.__name__] = {
            'paths': resource.paths,
            'acl': acl,
            'plugin': resource.__module__,
        }
    # collect role info:
    # We start with the ROLES dictionary (see top of file), then loop over all
    # resources to copy their ACEs into the corresponding roles.
    for resource in _resource_info:
        # loop over resource ACL:
        for index, ace in enumerate(_resource_info[resource]['acl']):
            if isinstance(ace, tuple) and len(ace) > 2:
                if ace[1] != Authenticated:
                    m = re.search('(?<=role:)[-a-zA-Z0-9_]+', ace[1])
                    role = m.group(0)
                    if role not in _role_info:
                        # remove ace from list:
                        _resource_info[resource]['acl'].pop(index)
                        log.warning(
                            'role {} is not a known role and will '
                            'be ignored during authorization'.format(role)
                        )
                    else:
                        if 'resources' not in _role_info[role]:
                            _role_info[role]['resources'] = {}
                        _role_info[role]['resources'][resource] = {'access': ace[2]}

    # Convert _role_info and _resource_info to lists of dictionaries for ease
    # of use by the frontend:
    _role_list.extend(dict_to_list(_role_info, 'role'))
    _resource_list.extend(dict_to_list(_resource_info, 'resource'))


def get_parents(resource, acl):
    """
    Get the parent ACLs of a resource, until there are no parents left, or one
    of the ACEs is DENY_ALL. Also change the ACE for deny_all to a string, for
    better readability.
    """
    for i, ace in enumerate(acl):
        if ace == DENY_ALL:
            acl[i] = 'DENY_ALL'
            return

    if hasattr(resource, '__parent__'):
        parent = resource.__parent__
        if hasattr(parent, '__acl__'):
            acl.extend(parent.__acl__)
        get_parents(parent, acl)


def dict_to_list(dictionary, label='id'):
    """
    Transform a dictionary of dictionaries to a list of dictionaries.

    The top key of the dictionary gets added to the dictionary item in the
    list as an entry with the key as specified by label.
    """
    list_of_dicts = []

    for key in dictionary:
        sub_dict = dictionary[key]
        sub_dict[label] = key
        list_of_dicts.append(sub_dict)

    return list_of_dicts


def about_roles(request):
    """
    Returns a summary of roles and acls.

    ---
    get:
      tags:
        - about
      parameters:
        - name: json
          in: query
          type: boolean
          description: Return json instead of a page
      description: >
        This endpoint gives a page with information about roles and
        what ACEs they have (what users with these roles are capable of
        w.r.t. resources), as well as what resources are served and
        what ACLs they have. The ACL returned for a resource includes
        any parent ACEs.
        The default response type is text/html, which displays two
        tables, one for a resource-centric view, one for a role-centric
        view.
        If you want a response in json, either set the json-paramater
        to true (you can try that case with the Try It Out button here)
        or send an HTTP ACCEPT header with the value application/json
        or add ".json" to the URL.

        ### Response (only if json=true or ACCEPT-header is application/json)

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | 'ok' or 'error'\n
        resources | array  | Each item is a dictionary with entries for:\n
        -         |        | 'resource': resource name\n
        -         |        | 'paths': a list of paths that use the resource\n
        -         |        | 'plugin': the plugin it belongs to\n
        -         |        | 'acl': list of ACEs (including parent ACEs).\n
        roles     | array  | Each item is a dictionary with entries for:\n
        -         |        | 'role': role name\n
        -         |        | 'description': description of the role\n
        -         |        | 'type': 'tenant' or 'token'\n
        -         |        | 'resources': a dictionary with resources as keys,
        and each resource a dictionary with an entry for 'access' (read/write
        etc), and if the ACE has a filter, an entry 'filter' for that filter\n

    """
    return_json = request.args.get('json', False)
    if (
        return_json
        or (
            'Accept' in request.headers
            and request.headers['Accept'].split(',')[0] == 'application/json'
        )
        or (hasattr(request, 'path_extension') and request.path_extension == '.json')
    ):
        return {'resources': _resource_list, 'roles': _role_list}

    request.response.content_type = 'text/html'
    result = render(
        'spynl.api.auth:about_roles.jinja2',
        {
            'resources': _resource_list,
            'roles': _role_list,
            'localizer': request.localizer,
        },
        request=request,
    )

    return result


def about_applications(request):
    """
    Returns a summary of roles and acls.

    ---
    get:
      tags:
        - about
      parameters:
        - name: json
          in: query
          type: boolean
          description: Return json instead of a page
      description: >
        This endpoint gives a page with information about applications. The bold
        entries in the table below are translated.

        ### Response (only if json=true or ACCEPT-header is application/json)

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | 'ok' or 'error'\n
        applications | array  | Each item is a dictionary with entries for:\n

        key in 'applications' | Type   | Description\n
        --------- | ------ | -----------\n
        application | string | application id\n
        *name*    | string   | application name \n
        paid      | boolean  | paid application or not\n
        category  | list  | list of categories (currently only 'retail' and/or
        'wholesale'\n
        options | object | dictionary of paid options for the appliction.
        The option id is the key of a sub dictionary that contains (translated)
        entries for the '*name*' and the '*description*' of the option.\n
    """

    if request.current_tenant_id != MASTER_TENANT_ID:
        applications = {
            app_id: app
            for app_id, app in APPLICATIONS.items()
            if not app.get('internal', False)
        }
    else:
        applications = APPLICATIONS.copy()

    return_json = (
        request.args.get('json')
        or request.headers.get('Accept', '').startswith('application/json')
        or getattr(request, 'path_extension', '') == '.json'
    )

    if return_json:
        response = {'applications': dict_to_list(applications, 'application')}
    else:
        request.response.content_type = 'text/html'
        response = render(
            'spynl.api.auth:about_applications.jinja2',
            {'applications': applications, 'localizer': request.localizer},
            request=request,
        )
    return response
