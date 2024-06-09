"""
plugger.py is used by spynl Plugins to say
which endspoints and resources it will use.
"""

from spynl.api.logistics import locations, packing_lists, sales_orders
from spynl.api.logistics.resources import Locations, PackingLists, SalesOrders


def includeme(config):
    """Add the function add as endpoint."""
    config.add_endpoint(locations.get, 'get', context=Locations, permission='read')
    config.add_endpoint(locations.count, 'count', context=Locations, permission='read')
    config.add_endpoint(locations.save, 'save', context=Locations, permission='edit')
    config.add_endpoint(locations.add, 'add', context=Locations, permission='add')

    config.add_endpoint(
        packing_lists.save, 'save', context=PackingLists, permission='edit'
    )
    config.add_endpoint(
        packing_lists.set_status,
        'set-status',
        context=PackingLists,
        permission='edit',
    )
    config.add_endpoint(
        packing_lists.get, 'get', context=PackingLists, permission='read'
    )
    config.add_endpoint(
        packing_lists.filters, 'filter', context=PackingLists, permission='read'
    )
    config.add_endpoint(
        packing_lists.ship, 'ship', context=PackingLists, permission='edit'
    )
    config.add_endpoint(
        packing_lists.shipping_labels,
        'shipping-labels',
        context=PackingLists,
        permission='edit',
    )
    config.add_endpoint(
        packing_lists.cancel, 'cancel', context=PackingLists, permission='delete'
    )
    config.add_endpoint(
        sales_orders.remove, 'remove', context=SalesOrders, permission='delete'
    )
    config.add_endpoint(sales_orders.get, 'get', context=SalesOrders, permission='read')
    config.add_endpoint(
        sales_orders.save, 'save', context=SalesOrders, permission='edit'
    )
    config.add_endpoint(
        sales_orders.open_for_edit,
        'open-for-edit',
        context=SalesOrders,
        permission='edit',
    )
    config.add_endpoint(
        packing_lists.download_csv,
        'download-csv',
        context=PackingLists,
        permission='read',
    )
    config.add_endpoint(
        sales_orders.download_excel,
        'download-excel',
        context=SalesOrders,
        permission='read',
    )
    config.add_endpoint(
        packing_lists.download_excel,
        'download-excel',
        context=PackingLists,
        permission='read',
    )
