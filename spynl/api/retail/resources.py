""" Resources relevant for spynl.retail """

from pyramid.authorization import DENY_ALL, Allow

from spynl.main.routing import Resource

from spynl.api.auth import AdminResource
from spynl.api.mongo import MongoResource


class WebshopSales(Resource):
    paths = ['webshop-sales']

    is_large_collection = True
    collection = 'transactions'

    __acl__ = [(Allow, 'role:token-webshop-admin', ('read', 'add'))]


class DeliveryPeriod(AdminResource):
    paths = ['delivery-periods']

    collection = 'delivery_periods'

    __acl__ = [
        (Allow, 'role:sales-user', 'read'),
        (Allow, 'role:sales-admin', ('read', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'edit')),
        (Allow, 'role:sw-consultant', ('read', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read', 'edit')),
    ]


class POS(Resource):
    paths = ['pos']

    is_large_collection = True
    collection = 'transactions'

    __acl__ = [
        (Allow, 'role:pos-device', ('read',)),
    ]


class Sales(AdminResource):
    paths = ['sales']

    is_large_collection = True
    collection = 'transactions'

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        (Allow, 'role:sw-developer', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', 'read'),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:dashboard-user', 'read'),
        (Allow, 'role:dashboard-report_user', 'read'),
        (Allow, 'role:owner', 'read'),
        (Allow, 'role:token-webshop-admin', ('read', 'add')),
    ]


class RetailTransactions(Sales):
    paths = ['retail-transactions']


class Withdrawals(Sales):
    paths = ['withdrawals']


class Consignments(AdminResource):

    paths = ['consignments']

    is_large_collection = True
    collection = 'transactions'

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add')),
        (Allow, 'role:sw-developer', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', 'read'),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:dashboard-user', 'read'),
        (Allow, 'role:dashboard-report_user', 'read'),
        (Allow, 'role:owner', 'read'),
        (Allow, 'role:token-webshop-admin', ('read', 'add')),
    ]


class Transit(AdminResource):

    paths = ['transits']

    is_large_collection = True
    collection = 'transactions'

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add')),
        (Allow, 'role:sw-developer', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', 'read'),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:dashboard-user', 'read'),
        (Allow, 'role:dashboard-report_user', 'read'),
        (Allow, 'role:owner', 'read'),
        (Allow, 'role:token-webshop-admin', ('read', 'add')),
    ]


class Receiving(AdminResource):
    """Resource for receiving type of transactions."""

    collection = 'receivings'
    paths = ['receivings']

    __acl__ = [
        (Allow, 'role:logistics-receivings_user', ('read', 'add', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read')),
    ]


class LogisticsTransactions(Receiving):
    paths = ['logistics-transactions']

    __acl__ = [
        (Allow, 'role:logistics-inventory_user', 'read'),
        (Allow, 'role:logistics-receivings_user', 'read'),
    ]


class Inventory(Resource):
    """Resource for inventory transactions."""

    collection = 'inventory'
    paths = ['inventory']

    __acl__ = [(Allow, 'role:logistics-inventory_user', ('read', 'add', 'edit'))]


class Devices(Resource):
    """Endpoints for device specific actions."""

    paths = ['devices']

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
    ]


class EOS(MongoResource):
    """End of shift."""

    paths = ['eos']

    __parent__ = AdminResource
    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        (Allow, 'role:owner', ('read', 'add', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-reporting_admin', 'read'),
        (Allow, 'role:sw-servicedesk', ('read', 'edit')),
        DENY_ALL,
    ]


class POSSettings(MongoResource):
    """Settings for the POS."""

    collection = 'pos_settings'
    paths = ['pos_settings']

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        # for creating new accounts, should be deprecated
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
    ]


class POSReasons(MongoResource):
    """Reasons for the POS."""

    collection = 'pos_reasons'
    paths = ['pos_reasons']

    __acl__ = [
        (Allow, 'role:owner', ('read', 'add', 'edit')),
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        DENY_ALL,
    ]


class POSDiscountRules(MongoResource):
    """Discount Rules for the POS."""

    collection = 'pos_discountrules'
    paths = ['pos_discountrules']

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
    ]


class Playlists(MongoResource):
    """Second Screen Data for the new Play application."""

    collection = 'playlists'
    paths = ['playlists']
    __parent__ = AdminResource

    __acl__ = [
        (Allow, 'role:secondscreen-admin', ('read', 'add', 'edit', 'delete')),
        (Allow, 'role:secondscreen-user', 'read'),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit', 'delete')),
        (Allow, 'role:sw-servicedesk', ('read', 'add', 'edit', 'delete')),
    ]


class PaymentMethods(MongoResource):
    """Second Screen Data for the POS."""

    collection = 'payment_methods'
    paths = ['payment_methods']

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
    ]


class Buffer(MongoResource):
    """Buffer for transactions, used by POS."""

    paths = ['buffer']

    __parent__ = AdminResource
    __acl__ = [
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        (Allow, 'role:owner', ('read', 'add', 'edit')),
        (Allow, 'role:token-webshop-admin', ('read', 'add')),
        (Allow, 'role:sw-servicedesk', ('read',)),
        DENY_ALL,
    ]


class Templates(MongoResource):
    """Templates, used for PDFs for instance."""

    paths = ['templates']

    __parent__ = AdminResource
    __acl__ = [
        (Allow, 'role:pos-device', 'read'),
        (Allow, 'role:sw-developer', ('read', 'add', 'edit')),
        (Allow, 'role:sw-reporting_admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-consultant', ('read', 'add', 'edit')),
        DENY_ALL,
    ]


class Reports(MongoResource):
    """Reports."""

    paths = ['reports']

    __parent__ = AdminResource
    __acl__ = [
        (Allow, 'role:sw-reporting_admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit')),
        (Allow, 'role:sw-consultant', ('read', 'add', 'edit')),
        (Allow, 'role:dashboard-report_user', 'read'),
        (Allow, 'role:owner', 'read'),
        DENY_ALL,
    ]


class SoftwearMetadata(MongoResource):
    """Buffer for transactions, used by POS."""

    collection = 'softwear_metadata'
    paths = ['softwear_metadata']

    __acl__ = [
        (Allow, 'role:pos-device', 'read'),
        (Allow, 'role:sw-admin', 'read'),
    ]
