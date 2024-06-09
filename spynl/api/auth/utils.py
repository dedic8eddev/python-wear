"""
Helper functions for spynl.auth.

Current user:
get_user_info(request, purpose=None): current user

Any user / Any tenant:
get_tenant_roles(user, tenant_id, restrict=False): any user, any tenant
get_default_application(user, tenant_id): any user, any tenant
lookup_tenant(tid): any tenant
find_user(username, search_email=False): any user
find_tenants(tenand_ids): any list of tenantids

Misc:
audit_log(message=None, request_args=None):
validate_email(email): any email
app_url(request, application):
validate_password(string)
"""

import copy
import os
import re
from functools import wraps
from inspect import getfullargspec

import dns.resolver
from pyramid.httpexceptions import HTTPForbidden

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import now
from spynl.main.exceptions import IllegalAction, SpynlException
from spynl.main.utils import get_user_ip

from spynl.api.auth.apps_and_roles import APPLICATIONS, ROLES
from spynl.api.auth.exceptions import (
    CannotRetrieveUser,
    SpynlPasswordRequirementsException,
    TenantDoesNotExist,
    UserNotActive,
)

MASTER_TENANT_ID = 'master'


def get_user_region(user):
    return user.get('settings', {}).get('sales', {}).get('region')


def is_sales_admin(request):
    user_roles = get_tenant_roles(
        request.db, request.cached_user, request.requested_tenant_id
    )
    return 'sales-admin' in user_roles or request.current_tenant_id == MASTER_TENANT_ID


def check_agent_access(agent_id, request):
    """Check if the logged in user has access to the agentdata."""
    if agent_id != request.authenticated_userid and not is_sales_admin(request):
        exc = IllegalAction(_('illegal-filter'))
        exc.http_escalate_as = HTTPForbidden
        raise exc


def find_tenants(db, tenant_ids):
    """List dicts of tenants in the same order of the tenant_ids."""

    tenants = db.tenants.pymongo_find({'_id': {'$in': tenant_ids}})
    return sorted(tenants, key=lambda t: tenant_ids.index(t['_id']))


def lookup_tenant(db, tenant_id):
    """
    Look up a tenant by ID.

    Raise Exceptions when the tenant doesn't exist.
    """
    tenant = db.tenants.pymongo_find_one({'_id': tenant_id})
    if not tenant:
        raise TenantDoesNotExist(tenant_id)
    return tenant


def get_tenant_applications(tenant):
    """
    Get the applications of the tenant from the database, and add the default
    applications
    """
    db_apps = tenant.get('applications', [])
    apps = []
    for app_id, app in APPLICATIONS.items():
        if app.get('default', False) or (app_id in db_apps):
            apps.append(app_id)

    return apps


def audit_log(message=None, request_args=None):
    """
    Call the decorator and pass a message and possible format arguments.

    Save a possible message to the audit log when calling the decorator.
    If theres the need to format the message with {} and pass a list of
    arguments, the request_args is for that.
    """

    def outer_wrapper(func):
        """The actual decorator."""

        @wraps(func)
        def inner_wrapper(*args):
            """Save to database important information about user action."""
            request = args[-1]  # request always comes after ctx
            doc = {
                'remote_ip': request.remote_addr,
                'action': request.view_name,
                'date': now(),
            }

            # message
            if isinstance(message, str):
                msg = message
                if request_args is not None and isinstance(request_args, list):
                    msg = message.format(
                        *[request.args.get(arg) for arg in request_args]
                    )
                doc.update(message=msg)

            # tenant
            if request.current_tenant_id is not None:
                doc['current_tenant_id'] = request.current_tenant_id
            if request.requested_tenant_id != request.current_tenant_id:
                doc['requested_tenant_id'] = request.requested_tenant_id

            # user
            current_user = get_user_info(request)
            if current_user.get('username', None) and current_user.get('_id', None):
                doc['auth_user'] = {
                    'username': current_user['username'],
                    'id': str(current_user['_id']),
                }
            request.db.spynl_audit_log.insert_one(doc)

            if len(getfullargspec(func).args) == 1:
                return func(request)
            else:
                return func(*args)

        return inner_wrapper

    return outer_wrapper


def get_tenant_roles(db, user, tenant_id, restrict=False):
    """
    return tenant roles for a user for a specific tenant_id

    Returns [] if tenant_id is None or roles are not set.
    Only returns the role that are in ROLES
    If restrict=True, it restricts the roles returned to those
    that are of the form: <appID>-<function>, in which appID is one of the
    tenant's apps.
    It will add the owner role if the user is an owner of the tenant.
    """
    roles = []

    if tenant_id is None:
        return roles

    tenant_roles = user.get('roles', {}).get(tenant_id, {})
    roles = tenant_roles.get('tenant', [])

    if isinstance(roles, str):
        roles = [roles]

    # Only return known roles:
    roles = [
        role for role in roles if role in ROLES and ROLES[role]['type'] == 'tenant'
    ]

    # Because Spynl.main does not contain Softwear roles, we add the
    # spynl-developer role that is used in Spynl.main for each user
    # with the sw-developer role:
    if 'sw-developer' in roles:
        roles.append('spynl-developer')

    tenant = lookup_tenant(db, tenant_id)
    # only allow roles that correspond to the t0enant's apps:
    if restrict:
        tenant_apps = get_tenant_applications(tenant)
        roles = [role for role in roles if role.split('-')[0] in tenant_apps]

    if user['_id'] in tenant.get('owners', []):
        roles.append('owner')

    return roles


def get_default_application(db, user, tenant_id):
    """
    return the default application id for a user for the set tenant

    returns 'dashboard' if tenant_id is None or no default_application is set.
    """
    def_app = None
    if tenant_id is not None:
        if user.get('default_application') is not None:
            default_application = user.get('default_application')
            if default_application.get(tenant_id) is not None:
                def_app = default_application.get(tenant_id)
    # check if tenant still has access to the app
    tenant = db.tenants.pymongo_find_one({'_id': tenant_id})
    tenant_apps = get_tenant_applications(tenant)
    if def_app not in tenant_apps:
        def_app = None

    return def_app


def get_user_info(request, purpose=None):
    """
    Function to get user information as a dictionary. The amount of data
    that is returned depends on the purpose.

    purpose=fresh_user: return a fresh copy of the database entry for the user
                        this copy is not cached.
    purpose=cached_user: return a copy of the database entry for the user
                        this is a cached copy and the database will only be
                        accessed once per request.
    purpose=stamp:      return a stamp that contains the userid and username
    purpose=error_view: return copy with only _id, username, email and
                        ipaddress added
    purpose=None        return a copy of the database entry using a whitelist
                        to remove sensitive data and adds the ipaddress

    This function is defined as the user_info_function in plugger.py, and will
    overwrite the user_info_function in spynl.main.
    """
    userid = request.authenticated_userid

    if userid is None:
        return {'ipaddress': get_user_ip(request)}

    if purpose == 'stamp':
        user = {'user': {'_id': userid}}
        if hasattr(request, 'session') and 'username' in request.session:
            user['user']['username'] = request.session['username']

    elif purpose == 'fresh_user':
        user = request.db.users.find_one({'_id': userid})
        if not user:
            raise CannotRetrieveUser()
    else:
        # If we're in an error view, we do not want to reraise any errors:
        if purpose == 'error_view':
            try:
                user = copy.deepcopy(request.cached_user) or {}
            except (UserNotActive, CannotRetrieveUser):
                user = {}
        else:
            # Prevent mutating the cached user, so use deepcopy
            user = copy.deepcopy(request.cached_user) or {}

        whitelist = None

        if purpose == 'error_view':
            whitelist = ['ipaddress', '_id', 'username', 'email']
        elif purpose is None:
            whitelist = [
                'ipaddress',
                '_id',
                'username',
                'fullname',
                'email',
                'tz',
                'active',
                'tenant_id',
                'type',
            ]

        if purpose != 'cached_user':
            user.update({'ipaddress': get_user_ip(request)})

        if whitelist:
            user = {k: v for k, v in user.items() if k in whitelist}

    return user


def find_user(db, username, search_email=False):
    """
    return the database entry for a user, raise an exception if there is
    no user with that username. If check_email is true the function will check
    if the username corresponds to an email address if no user with the username
    is found.
    """
    if not username:
        raise CannotRetrieveUser(
            developer_message='Username cannot be None or an empty string.'
        )
    filter_ = {'username': username}
    if search_email:
        filter_ = {'$or': [filter_, {'email': username}]}
    user = db.users.find_one(filter_)
    if not user:
        raise CannotRetrieveUser()

    return user


def validate_email(email):
    """
    Validate an email address.

    Check an email address for general form and for existence of the host.
    """
    # check general form: a valid local name + @ + some host
    # (for local name, see
    # http://en.wikipedia.org/wiki/Email_address#Local_part)
    if not re.match(r'[A-Za-z0-9\-\_\.\+\$\%\#\&\*\/\=\?\{\}\|\~]+@[^@]+', email):
        raise SpynlException('The email address does not seem to be valid.')

    # if we are running tests skip host check
    if os.environ.get('RUNNING_TESTS') == 'true':
        return

    # check host
    host = re.findall('[^@]+', email)[1]
    try:
        # dns.resolver throws an exception when it can't find a mail (MX)
        # host. The point at the end makes it not try to append domains
        dns.resolver.query('{}.'.format(host), 'MX')
    except Exception:
        raise SpynlException(
            'The host {} is not known in the DNS system as a '
            'mail server. Is it spelled correctly?'.format(host)
        )


def app_url(request, application):
    """
    Return the url where this Spynl instance runs on, with 'spynl' replaced by
    the application name. Also considers dev instances we have where we
    put the version in the URL, e.g. "spynl-v534".
    """
    pattern = re.compile(r'//([A-Za-z0-9]+)[^\.]*')
    domain = pattern.sub("//www", request.application_url, count=1)
    application = 'www' if application == 'spynl' else application
    return "{}/{}.html#".format(domain, application)


def validate_password(password):
    """Check if the password conforms with our requirements."""
    min_length = 10
    max_length = 128
    if len(password) < min_length:
        raise SpynlPasswordRequirementsException(
            _(
                'password-does-not-meet-requirements-min-length',
                mapping={'min_length': min_length},
            )
        )
    elif len(password) > max_length:
        raise SpynlPasswordRequirementsException(
            _(
                'password-does-not-meet-requirements-max-length',
                mapping={'max_length': max_length},
            )
        )


def check_key(d, key):
    """Return True or False if key is present in dict, recursively."""
    if isinstance(d, dict):
        return key in d or any(  # base case
            check_key(v, key) for v in d.values()
        )  # recursive call on values

    if isinstance(d, list):
        # recursively call on each list item
        return any(check_key(i, key) for i in d)
