"""Define the endpoints for spynl.retail to use."""

from pyramid.security import NO_PERMISSION_REQUIRED

from spynl.api.mongo.db_endpoints import get_include_public_documents
from spynl.api.mongo.plugger import add_dbaccess_endpoints
from spynl.api.retail import (
    buffer,
    delivery_periods,
    eos,
    eos_reports,
    inventory,
    journal,
    logistics_transactions,
    pay_nl_exchange,
    payments,
    pos,
    receiving,
    retail_transactions,
    sales,
    sales_reports,
    transit,
)
from spynl.api.retail.resources import (
    EOS,
    POS,
    Buffer,
    Consignments,
    DeliveryPeriod,
    Devices,
    Inventory,
    LogisticsTransactions,
    PaymentMethods,
    Playlists,
    POSDiscountRules,
    POSReasons,
    POSSettings,
    Receiving,
    Reports,
    RetailTransactions,
    Sales,
    SoftwearMetadata,
    Templates,
    Transit,
    WebshopSales,
    Withdrawals,
)


def includeme(config):
    """The basic crud methods and other things offered in spynl.mongo."""

    # Data access endpoints
    add_dbaccess_endpoints(config, POSSettings, ['get', 'edit'])
    add_dbaccess_endpoints(config, POSReasons, ['get', 'save'])
    add_dbaccess_endpoints(config, PaymentMethods, ['get', 'edit', 'save'])
    add_dbaccess_endpoints(config, POSDiscountRules, ['get', 'save'])
    add_dbaccess_endpoints(config, Playlists, ['get', 'add', 'count', 'remove', 'save'])

    config.add_endpoint(
        get_include_public_documents,
        '/',
        context=Templates,
        permission='read',
        request_method='GET',
    )
    config.add_endpoint(
        get_include_public_documents, 'get', context=Templates, permission='read'
    )
    add_dbaccess_endpoints(
        config, Templates, ['edit', 'add', 'count', 'remove', 'save']
    )

    config.add_endpoint(buffer.add, 'add', context=Buffer, permission='add')
    add_dbaccess_endpoints(config, Buffer, ['get', 'edit', 'save'])

    config.add_endpoint(
        get_include_public_documents,
        '/',
        context=SoftwearMetadata,
        permission='read',
        request_method='GET',
    )
    config.add_endpoint(
        get_include_public_documents, 'get', context=SoftwearMetadata, permission='read'
    )

    config.add_endpoint(sales.sale_save, 'save', context=Sales, permission='edit')
    config.add_endpoint(sales.sale_add, 'add', context=Sales, permission='add')
    config.add_endpoint(sales.sale_get, 'get', context=Sales, permission='read')
    config.add_endpoint(
        sales.add_fiscal_receipt, 'add-fiscal-receipt', context=Sales, permission='edit'
    )

    config.add_endpoint(sales.sale_cancel, 'cancel', context=Sales, permission='add')

    config.add_endpoint(
        sales.webshop_sale_add, 'add', context=WebshopSales, permission='add'
    )

    config.add_endpoint(
        retail_transactions.get, 'get', context=RetailTransactions, permission='read'
    )

    config.add_endpoint(
        sales.withdrawal_save, 'save', context=Withdrawals, permission='edit'
    )
    config.add_endpoint(
        sales.withdrawal_add, 'add', context=Withdrawals, permission='add'
    )
    config.add_endpoint(
        sales.withdrawal_get, 'get', context=Withdrawals, permission='read'
    )

    config.add_endpoint(
        sales.consignment_save, 'save', context=Consignments, permission='edit'
    )
    config.add_endpoint(
        sales.consignment_add, 'add', context=Consignments, permission='add'
    )
    config.add_endpoint(
        sales.consignment_get, 'get', context=Consignments, permission='read'
    )

    config.add_endpoint(receiving.save, 'save', context=Receiving, permission='edit')
    config.add_endpoint(receiving.get, 'get', context=Receiving, permission='read')

    config.add_endpoint(inventory.add, 'add', context=Inventory, permission='add')
    config.add_endpoint(inventory.get, 'get', context=Inventory, permission='read')

    config.add_endpoint(
        logistics_transactions.get,
        'get',
        context=LogisticsTransactions,
        permission='read',
    )

    config.add_endpoint(transit.get, 'get', context=Transit, permission='read')
    config.add_endpoint(transit.add, 'add', context=Transit, permission='add')
    config.add_endpoint(transit.save, 'save', context=Transit, permission='edit')

    config.add_endpoint(
        delivery_periods.get, 'get', context=DeliveryPeriod, permission='read'
    )
    config.add_endpoint(
        delivery_periods.save, 'save', context=DeliveryPeriod, permission='edit'
    )
    config.add_endpoint(
        delivery_periods.delete, 'remove', context=DeliveryPeriod, permission='edit'
    )

    # TODO: either keep devices, or move this to the Tenants (or other) resource
    # moving it to a different resource is a breaking change for the frontend
    # POS business logic
    config.add_endpoint(
        pos.get_new_pos_instance_id,
        'new-pos-instance-id',
        context=Devices,
        permission='edit',
    )

    config.add_endpoint(pos.init_pos, 'init', context=POS, permission='read')

    # Reporting endpoints
    config.add_endpoint(
        payments.payment_report_json, 'payments', context=Reports, permission='read'
    )
    config.add_endpoint(
        payments.payment_report_csv, 'payments-csv', context=Reports, permission='read'
    )
    config.add_endpoint(
        payments.payment_report_excel,
        'payments-excel',
        context=Reports,
        permission='read',
    )
    config.add_endpoint(
        payments.get_payment_filters,
        'payments-filter',
        context=Reports,
        permission='read',
    )

    config.add_endpoint(
        journal.journal_json, 'journal', context=Sales, permission='read'
    )
    config.add_endpoint(
        journal.journal_csv, 'journal-csv', context=Sales, permission='read'
    )
    config.add_endpoint(
        journal.journal_excel, 'journal-excel', context=Sales, permission='read'
    )
    config.add_endpoint(
        journal.get_journal_filters, 'journal-filter', context=Sales, permission='read'
    )

    config.add_endpoint(
        sales_reports.period_json, 'period', context=Sales, permission='read'
    )

    config.add_endpoint(
        sales_reports.period_csv, 'period-csv', context=Sales, permission='read'
    )

    config.add_endpoint(
        sales_reports.period_excel, 'period-excel', context=Sales, permission='read'
    )

    config.add_endpoint(
        sales_reports.per_warehouse_json,
        'per-warehouse',
        context=Sales,
        permission='read',
    )

    config.add_endpoint(
        sales_reports.per_warehouse_csv,
        'per-warehouse-csv',
        context=Sales,
        permission='read',
    )

    config.add_endpoint(
        sales_reports.per_warehouse_excel,
        'per-warehouse-excel',
        context=Sales,
        permission='read',
    )

    config.add_endpoint(
        sales_reports.summary, 'summary', context=Sales, permission='read'
    )

    config.add_endpoint(
        sales_reports.per_article_json, 'per-article', context=Sales, permission='read'
    )

    config.add_endpoint(
        sales_reports.per_article_csv,
        'per-article-csv',
        context=Sales,
        permission='read',
    )

    config.add_endpoint(
        sales_reports.per_article_excel,
        'per-article-excel',
        context=Sales,
        permission='read',
    )

    config.add_endpoint(
        sales_reports.sold_barcodes_per_customer,
        'barcodes-per-customer',
        context=Sales,
        permission='read',
    )

    config.add_endpoint(eos.save, 'save', context=EOS, permission='edit')
    config.add_endpoint(eos.get, 'get', context=EOS, permission='read')
    config.add_endpoint(eos.reset, 'reset', context=EOS, permission='edit')
    config.add_endpoint(eos.rectify, 'rectify', context=EOS, permission='edit')
    config.add_endpoint(eos.init, 'init', context=EOS, permission='edit')
    config.add_endpoint(
        eos.get_eos_overview, 'get-overview', context=EOS, permission='read'
    )
    config.add_endpoint(
        eos_reports.aggregate_eos_json, 'report', context=EOS, permission='read'
    )
    config.add_endpoint(
        eos_reports.aggregate_eos_csv, 'report-csv', context=EOS, permission='read'
    )
    config.add_endpoint(
        eos_reports.aggregate_eos_excel, 'report-excel', context=EOS, permission='read'
    )
    config.add_endpoint(
        eos_reports.get_eos_filters, 'report-filter', context=EOS, permission='read'
    )

    config.add_endpoint(
        pay_nl_exchange.exchange, 'pay-nl-exchange', permission=NO_PERMISSION_REQUIRED
    )
