"""Map resources to endpoints that will be used."""

import json

from pyramid.authentication import SessionAuthenticationPolicy
from pyramid.authorization import Authenticated
from pyramid.security import NO_PERMISSION_REQUIRED

from spynl.main.about import AboutResource

from spynl.api.auth import AdminResource, B2BResource, session_cycle
from spynl.api.auth.authorization import (
    IAuthorizationPolicy,
    authorization_control_tenant_id,
)
from spynl.api.auth.documentation import about_applications, about_roles, document_roles
from spynl.api.auth.request_methods import (
    get_authenticated_user,
    get_current_tenant_id,
    get_requested_tenant_id,
    validate_token,
)
from spynl.api.auth.resources import Events, SpynlSessions
from spynl.api.auth.session_authentication import MongoDBSession, rolefinder
from spynl.api.auth.token_authentication import TokenAuthAuthenticationPolicy
from spynl.api.auth.utils import get_user_info
from spynl.api.mongo import MongoResource
from spynl.api.mongo.plugger import add_dbaccess_endpoints


def get_session_or_token_id(request):
    try:
        return request.headers['sid']
    except KeyError:
        return request.token_payload['_id']


def json_payload(request):
    try:
        return request.json_body
    except json.decoder.JSONDecodeError:
        return {}


def add_tenant_routes(config, route_name, resource_class, path):
    """
    Add tenant-based routes to Mongo- and AuthResources
    """
    config.add_route(
        name=route_name,
        pattern='/tenants/{tenant_id}/%s/{method}' % path,
        factory=resource_class,
    )
    config.add_route(
        name=route_name + '.nomethod',
        pattern='/tenants/{tenant_id}/%s' % path,
        factory=resource_class,
    )


def includeme(config):
    """
    Set authentication policy and challenging algorithm.

    Configure endpoints.
    """
    config.add_settings(user_info_function=get_user_info)

    # set up the function for the session factory, the rest of the set-up
    # happens in spynl.main.session
    config.add_settings(MongoDB=MongoDBSession)

    policies = [
        TokenAuthAuthenticationPolicy(),
        # We use a session-based Authentication policy and on successful login,
        # we store the user's _id as principal (returned by authenticated_userid)
        # because authenticated_userid also calls rolefinder, it is better to
        # use request.authenticated_userid and trust that authorization
        # will do the checks for you. If you need to be completely sure that
        # the userid belongs to a currently authenticated and active user, or
        # if you cannot rely in authorization for your code, then do
        # use request.authenticated_userid.
        SessionAuthenticationPolicy(callback=rolefinder),
    ]

    config.set_security_policy(IAuthorizationPolicy(policies))
    config.add_view_deriver(
        authorization_control_tenant_id, under='validate_filter_and_data'
    )

    config.add_request_method(
        get_session_or_token_id, name='session_or_token_id', reify=True
    )

    config.add_request_method(json_payload, name='json_payload', reify=True)

    config.add_request_method(validate_token, name='token_payload', reify=True)

    # The get_authenticated_user function can now be called by
    # request.cached_user the reify=True makes sure that the data is
    # cached and there is only one database call per request.
    # Use request.cached_user.copy() if you want to mutate any data,
    # otherwise the changes persist during the request. You can use
    # get_user_info(purpose='cached_user') to do the same.
    config.add_request_method(get_authenticated_user, name='cached_user', reify=True)

    # create request.current_tenant_id
    config.add_request_method(
        get_current_tenant_id, name='current_tenant_id', property=True
    )
    config.add_request_method(
        get_requested_tenant_id, name='requested_tenant_id', property=True
    )

    # make sure roles get documented after all plugins are loaded:
    config.add_subscriber(document_roles, 'spynl.main.ConfigCommited')

    # add tenant-based routes
    resource_routes_info = config.get_settings()['spynl.resource_routes_info']
    resource_routes_info['spynl.tenants.{path}'] = {
        'resources': (MongoResource, B2BResource, AdminResource),
        'route_factory': add_tenant_routes,
    }
    config.add_settings({'spynl.resource_routes_info': resource_routes_info})

    config.add_endpoint(
        about_roles, 'roles', context=AboutResource, permission=Authenticated
    )
    config.add_endpoint(
        about_applications,
        'applications',
        context=AboutResource,
        permission=Authenticated,
    )

    # add resource based endpoints:
    add_dbaccess_endpoints(config, SpynlSessions, ['get', 'count'])
    add_dbaccess_endpoints(config, Events, ['get', 'edit', 'add', 'count', 'save'])

    config.add_endpoint(session_cycle.login, 'login', permission=NO_PERMISSION_REQUIRED)
    config.add_endpoint(
        session_cycle.validate_otp, 'validate-otp', permission=NO_PERMISSION_REQUIRED
    )
    config.add_endpoint(
        session_cycle.logout, 'logout', permission=NO_PERMISSION_REQUIRED
    )
    config.add_endpoint(
        session_cycle.validate_session,
        'validate-session',
        permission=NO_PERMISSION_REQUIRED,
    )
    config.add_endpoint(
        session_cycle.set_tenant, 'set-tenant', permission=Authenticated
    )
    config.add_endpoint(session_cycle.logged_in_user, 'me', permission=Authenticated)
