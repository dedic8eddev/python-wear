"""This module implements upload capabilities for spynl."""

from pyramid.authorization import DENY_ALL, Allow

from spynl.api.auth import AdminResource


class Images(AdminResource):

    """The resource class for images"""

    paths = ['images']

    __acl__ = [
        (Allow, 'role:owner', ('add', 'edit')),
        (Allow, 'role:pos-device', ('add', 'edit')),
        (Allow, 'role:account-admin', ('add', 'edit')),
        (Allow, 'role:secondscreen-admin', ('add', 'edit')),
        (Allow, 'role:sw-admin', ('add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('add', 'edit')),
        DENY_ALL,
    ]


class Logos(AdminResource):

    """The resource class for uploads"""

    paths = ['logos']

    __acl__ = [
        (Allow, 'role:owner', ('add', 'edit')),
        (Allow, 'role:account-admin', ('add', 'edit')),
        (Allow, 'role:sw-admin', ('add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('add', 'edit')),
        DENY_ALL,
    ]
