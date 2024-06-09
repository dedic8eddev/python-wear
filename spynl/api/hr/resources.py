"""This module has the necessary resources for HR."""

import uuid

from bson import ObjectId
from pyramid.authorization import DENY_ALL, Allow, Authenticated

from spynl.main.routing import Resource

from spynl.api.auth import AdminResource
from spynl.api.mongo import MongoResource


class OrderTerms(AdminResource):
    """Order terms."""

    paths = ['order-terms']

    collection = 'order_terms'

    __acl__ = [
        ('Allow', 'role:sales-user', 'read'),
        ('Allow', 'role:sales-admin', ('read', 'edit', 'delete')),
        ('Allow', 'role:owner', ('read', 'edit', 'delete')),
        ('Allow', 'role:sw-consultant', ('read', 'edit', 'delete')),
        ('Allow', 'role:sw-admin', ('read', 'edit', 'delete')),
        DENY_ALL,
    ]


class Settings(AdminResource):
    """
    User or tenant settings,
    not directly backed by one Mongo collection.
    """

    paths = ['settings']

    __acl__ = [
        (Allow, 'role:account-admin', ('read', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'edit')),
        (Allow, 'role:sw-finance', ('read', 'edit')),
        (Allow, 'role:owner', ('read', 'edit')),
        (Allow, 'role:sales-user', ('read', 'edit')),
        (Allow, 'role:sales-admin', ('read', 'edit')),
        (Allow, Authenticated, 'read'),  # e.g for getting the logo
        DENY_ALL,
    ]


class Cashiers(MongoResource):
    """Cashiers."""

    paths = ['cashiers']

    __acl__ = [
        (Allow, 'role:account-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read', 'add', 'edit')),
        (Allow, 'role:owner', ('read', 'add', 'edit')),
        (Allow, 'role:pos-device', 'read'),
        DENY_ALL,
    ]


class RetailCustomers(MongoResource):
    """Our customer's customers"""

    collection = 'customers'
    is_large_collection = True
    paths = ['customers']

    # The customer ID is a UUID, we might get metadata with user IDs as Objects
    id_class = [uuid.UUID, ObjectId]

    __acl__ = [
        (Allow, 'role:secondscreen-user', ('read', 'add', 'edit')),
        (Allow, 'role:secondscreen-admin', ('read', 'add', 'edit')),
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit', 'delete')),
        (Allow, 'role:sw-servicedesk', ('read',)),
        (Allow, 'role:token-webshop-admin', ('read', 'add', 'edit')),
    ]


class WholesaleCustomers(MongoResource):
    """Resource regarding wholesaler's customers."""

    # wholesale-customer is a necessary and temporary endpoint.
    # therefore is the name convention violated here.
    paths = ['wholesale-customers', 'wholesale-customer']
    collection = 'wholesale_customers'
    is_large_collection = False

    __acl__ = [
        (Allow, 'role:sales-user', ('read', 'edit')),
        (Allow, 'role:sales-admin', ('read', 'edit')),
        (Allow, 'role:token-webshop-admin', ('read', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read',)),
    ]


class Tokens(AdminResource):
    """
    Resource for API token management.
    """

    paths = ['tokens']

    __acl__ = [
        (Allow, 'role:owner', ('add', 'edit', 'read', 'delete')),
        (Allow, 'role:sw-admin', ('add', 'read', 'delete')),
        (Allow, 'role:sw-servicedesk', ('add', 'read', 'delete')),
    ]


class DeveloperTools(Resource):
    """
    Resource for endpoints that make life easier for developers.
    """

    paths = ['developer-tools']

    __acl__ = [(Allow, 'role:sw-developer', ('read', 'add', 'edit', 'delete'))]


class AccountResource(Resource):
    """
    Resource specifically for owners to give access to a subset of the tenant document.

    Sw roles should use the Tenant resource.
    """

    paths = ['account']
    collection = 'tenants'
    __acl__ = [(Allow, 'role:owner', ('read', 'edit'))]


class AccountProvisioning(Resource):
    """
    Resource for account provisioning
    """

    paths = ['account-provisioning']

    __acl__ = [(Allow, 'role:sw-account_manager', ('add'))]


class AccountManager(AdminResource):
    """
    Resource for endpoints that can only be used by an account manager.
    """

    paths = ['account-manager']

    __acl__ = [(Allow, 'role:sw-account_manager', ('read', 'edit')), DENY_ALL]
