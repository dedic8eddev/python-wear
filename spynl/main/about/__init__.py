"""
The about plugin is used to display meta data about the application, e.g.
database connection or build information.
"""
from pyramid.authorization import DENY_ALL, Allow, Authenticated
from pyramid.security import NO_PERMISSION_REQUIRED

from spynl.main.about.endpoints import build, hello, spynl_sleep, versions
from spynl.main.routing import Resource


class AboutResource(Resource):
    """The resource class for /about."""

    paths = ['about']

    __acl__ = [(Allow, 'role:spynl-developer', 'read'), DENY_ALL]


class StaticResource(Resource):
    """
    The resource class for static assets for the about endpoints. Open only to
    developers.
    """

    __acl__ = [(Allow, 'role:spynl-developer', 'read'), DENY_ALL]


def main(config):
    """doc, get, version, build, add endpoints."""

    config.add_static_view(
        name='static_swagger',
        path='spynl.main:docs/swagger-ui/',
        factory=StaticResource,
        permission='read',
    )

    config.add_endpoint(
        hello, None, context=AboutResource, permission=NO_PERMISSION_REQUIRED
    )
    # Note: this endpoint is used for testing authorization, so please do not change the
    # permission without changing tests.
    config.add_endpoint(
        versions, 'versions', context=AboutResource, permission=Authenticated
    )
    config.add_endpoint(
        build, 'build', context=AboutResource, permission=NO_PERMISSION_REQUIRED
    )
    config.add_endpoint(spynl_sleep, 'sleep', context=AboutResource, permission='read')
