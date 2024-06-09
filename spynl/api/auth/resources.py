from pyramid.authorization import DENY_ALL, Allow

from spynl.main.routing import Resource

from spynl.api.mongo import MongoResource


class AdminResource(Resource):
    """
    Any resource of this class should get tenant/**/ endpoints
    """


class B2BResource(Resource):
    """
    Only resources that are B2B resources can be accessed with a different
    requested tenant than the current tenant (except for the master tenant)
    """

    __acl__ = [(Allow, 'role:owner', ('read', 'add', 'edit')), DENY_ALL]


class SpynlSessions(MongoResource):
    """spynl_sessions collection."""

    collection = 'spynl_sessions'
    paths = ['spynl_sessions']

    __acl__ = [(Allow, 'role:sww-api', 'read'), DENY_ALL]


class User(MongoResource):
    """users collection."""

    collection = 'users'
    paths = ['users']

    # Please note that you cannot edit or add master users via this resource

    # For now we do not allow the account-admin and owner to edit/add
    # anything for the users. When we decide to allow that, we'll need to
    # think carefully about the add_tenant_roles and change_active endpoints
    __acl__ = [
        (Allow, 'role:account-admin', 'read'),
        (Allow, 'role:pos-device', 'read'),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-finance', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read', 'add', 'edit')),
        (Allow, 'role:owner', 'read'),
        DENY_ALL,
    ]


class Tenants(MongoResource):
    """tenant collection."""

    paths = ['tenants']

    # Please note that you cannot edit the master tenant via this resource

    # only allow sw personnel access to this directly
    # N.B. there are tests that use a monkeypatch to test non-sw roles,
    # but care should still be taken when adding non-sw roles.
    __acl__ = [
        (Allow, 'role:sw-finance', ('read', 'add', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-consultant', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', 'read'),
        DENY_ALL,
    ]


class Events(MongoResource):
    """The resource class for events, used by M2F."""

    collection = 'events'
    paths = ['events']

    # read access for pos is needed for diagnostic check in end of shift
    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        (Allow, 'role:products-admin', ('read', 'add', 'edit')),
        (Allow, 'role:products-user', ('read', 'add', 'edit')),
        (Allow, 'role:inventory-user', ('add', 'edit')),
        (Allow, 'role:sales-user', ('add', 'edit')),
        (Allow, 'role:sww-api', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read',)),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        DENY_ALL,
    ]
