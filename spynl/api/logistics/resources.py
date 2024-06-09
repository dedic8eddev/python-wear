"""
Resources for Logistics
"""

from pyramid.authorization import DENY_ALL, Allow

from spynl.api.auth import AdminResource
from spynl.api.mongo import MongoResource


class Locations(MongoResource):
    """The locations resource. This is the new style warehouses resource."""

    paths = ['locations']

    collection = 'warehouses'

    # NOTE: do not allow anyone else to add without checking the logic of the
    # add endpoint.
    __acl__ = [
        (Allow, 'role:pos-device', 'read'),
        (Allow, 'role:dashboard-user', 'read'),
        (Allow, 'role:dashboard-report_user', 'read'),
        (Allow, 'role:account-admin', ('read', 'edit')),
        (Allow, 'role:sw-account_manager', ('read', 'edit', 'add')),
        (Allow, 'role:sw-finance', ('read', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'edit')),
        (Allow, 'role:inventory-user', 'read'),
        (Allow, 'role:logistics-receivings_user', 'read'),
        (Allow, 'role:logistics-inventory_user', 'read'),
        (Allow, 'role:owner', ('read', 'edit')),
    ]


class Labels(AdminResource):

    """The resource class for labels"""

    paths = ['labels']

    collection = 'labels'

    __acl__ = [
        (Allow, 'role:owner', ('read', 'edit', 'add')),
        (Allow, 'role:account-admin', ('read', 'edit', 'add')),
        (Allow, 'role:logistics-receivings_user', 'read'),
        (Allow, 'role:sw-servicedesk', ('read', 'edit', 'add')),
        (Allow, 'role:sw-admin', ('read', 'edit', 'add')),
        DENY_ALL,
    ]


class PackingLists(AdminResource):
    paths = ['packing-lists']

    collection = 'sales_orders'

    # The delete permission is used for cancelling packing lists
    __acl__ = [
        (Allow, 'role:picking-admin', ('read', 'edit', 'delete')),
        (Allow, 'role:picking-user', ('read', 'edit')),
        (Allow, 'role:sw-admin', 'read', 'delete'),
        (Allow, 'role:sw-consultant', 'read', 'delete'),
        (Allow, 'role:sw-servicedesk', 'read', 'delete'),
    ]


class SalesOrders(AdminResource):
    paths = ['sales-orders']

    collection = 'sales_orders'

    __acl__ = [
        (Allow, 'role:sales-admin', ('read', 'delete', 'edit')),
        (Allow, 'role:sales-user', ('read', 'delete', 'edit')),
        (Allow, 'role:sw-admin', 'read'),
        (Allow, 'role:sw-consultant', 'read'),
        (Allow, 'role:sw-servicedesk', 'read'),
        (Allow, 'role:token-webshop-admin', ('read', 'delete', 'edit')),
    ]
