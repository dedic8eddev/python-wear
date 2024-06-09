import collections
import json
import os

import click
from marshmallow import Schema, fields
from marshmallow_jsonschema import JSONSchema

from cli.cli import cli
from cli.sww_schemas import (
    SWWCouponsCheckGetSchema,
    SWWCouponsGetSchema,
    SWWCouponsPostSchema,
    SWWCouponsRedeemPostSchema,
    SWWSkuGetSchema,
    SWWStockDetailGetSchema,
    SWWStockLogicalGetSchema,
    SWWStockPerLocationGetSchema,
    SWWWholesaleCustomerSalesSchema,
)

from spynl_schemas import (
    ConsignmentSchema,
    DeliveryPeriodSchema,
    EOSSchema,
    InventorySchema,
    OrderTermsSchema,
    PackingListSchema,
    ReceivingSchema,
    RetailCustomerSchema,
    SaleSchema,
    SalesOrderSchema,
    TransitSchema,
    Warehouse,
    WholesaleCustomerSchema,
)
from spynl_schemas.sale import ExternalSaleSchema, ExternalTransitSchema
from spynl_schemas.tenant import Settings as TenantSettings
from spynl_schemas.user import Settings as UserSettings

from spynl.api.auth.session_cycle import (
    LoggedInUserDocumentation,
    LoginSchema,
    TwoFactorAuthSchema,
)
from spynl.api.hr.order_terms import OrderTermsGetSchema, OrderTermsRemoveSchema
from spynl.api.hr.user_endpoints import SetTwoFactorAuthSchema
from spynl.api.hr.wholesale_customer import WholesaleCustomerGetSchema
from spynl.api.logistics.locations import LocationsGetSchema
from spynl.api.logistics.packing_lists import (
    CancelParameters,
    LabelsParameters,
    PackingListDownloadSchema,
    PackingListGetSchema,
    SetStatus,
    ShippingParameters,
)
from spynl.api.logistics.sales_orders import (
    SalesOrderDownloadSchema,
    SalesOrderGetSchema,
    SalesOrderOpenSchema,
)
from spynl.api.retail.delivery_periods import (
    DeliveryPeriodDeleteSchema,
    DeliveryPeriodGetSchema,
)
from spynl.api.retail.eos import (
    EOSGetSchema,
    EOSOverviewSchema,
    EOSRectifySchema,
    EOSResetSchema,
)
from spynl.api.retail.eos_reports import EOSReportsAggSchema
from spynl.api.retail.inventory import InventoryGetSchema
from spynl.api.retail.journal import (
    Journal,
    JournalFilterQuery,
    JournalResponseDocumentation,
)
from spynl.api.retail.logistics_transactions import LogisticsTransactionsGetSchema
from spynl.api.retail.receiving import ReceivingGetSchema
from spynl.api.retail.retail_transactions import TransactionGetSchema
from spynl.api.retail.sales import (
    ConsignmentGetSchema,
    SaleCancelSchema,
    SaleGetSchema,
    WithdrawalGetSchema,
)
from spynl.api.retail.sales_reports import (
    CustomerSalesResponse,
    CustomerSalesSchema,
    PerArticleSchema,
)
from spynl.api.retail.transit import TransitGetSchema


@cli.group()
def api():
    """Entrypoint for spynl api commands."""


folder_option = click.option(
    '-f',
    '--folder',
    help='Specify a folder for the schemas, default is spynl_swagger in cwd.'
    'Will be created if it does not exist',
    type=click.Path(),
)


# Type is set automatically, so should not show up in documentation.
# TODO: implement way of doing this from the schema itself (something like post_load for
#       documentation) (when changing this, don't forget the corresponding docstrings)
class SaleGet(SaleGetSchema):
    class Meta:
        exclude = ('filter.type',)


class SaleCancel(SaleCancelSchema):
    class Meta:
        exclude = ('filter.type',)


class ConsignmentGet(ConsignmentGetSchema):
    class Meta:
        exclude = ('filter.type',)


class WithdrawalGet(WithdrawalGetSchema):
    class Meta:
        exclude = ('filter.type',)


class TransitGet(TransitGetSchema):
    class Meta:
        exclude = ('filter.type',)


@folder_option
@api.command()
def generate_json_schemas(folder=None):
    shared_schemas(folder)
    new_style_endpoints = [
        (PackingListSchema, PackingListGetSchema, 'packing_list'),
        (ReceivingSchema, ReceivingGetSchema, 'receiving'),
        (InventorySchema, InventoryGetSchema, 'inventory'),
        (SalesOrderSchema, SalesOrderGetSchema, 'sales_order'),
        (SaleSchema, SaleGet, 'sale'),
        (ConsignmentSchema, ConsignmentGet, 'consignment'),
        (TransitSchema, TransitGet, 'transit'),
        (EOSSchema, EOSGetSchema, 'eos'),
        (Warehouse, LocationsGetSchema, 'locations'),
        (RetailCustomerSchema, None, 'retail_customers'),
        (OrderTermsSchema, OrderTermsGetSchema, 'order_terms'),
        (DeliveryPeriodSchema, DeliveryPeriodGetSchema, 'delivery_periods'),
    ]
    for endpoint in new_style_endpoints:
        generate_new_style_endpoints_schemas(folder, *endpoint)

    # response for /me:
    dump_schema_to_file(LoggedInUserDocumentation, 'logged_in_user', folder)
    # get parameters for withdrawal:
    dump_schema_to_file(WithdrawalGet, 'withdrawal_get_parameters', folder)
    # get parameters for retail transactions:
    dump_schema_to_file(TransactionGetSchema, 'retail_transactions', folder)
    # get parameters for eos overview:
    dump_schema_to_file(EOSOverviewSchema, 'eos_overview', folder)
    # get parameters for eos reset:
    dump_schema_to_file(EOSResetSchema, 'eos_reset', folder)
    # get parameters for eos rectify:
    dump_schema_to_file(EOSRectifySchema, 'eos_rectify', folder)
    # parameters for EOS aggregate:
    dump_schema_to_file(EOSReportsAggSchema, 'aggregate_eos', folder)
    # parameters for sales/per-article:
    dump_schema_to_file(PerArticleSchema, 'per_article', folder)
    # documentation for Journal:
    dump_schema_to_file(Journal, 'journal', folder)
    dump_schema_to_file(JournalResponseDocumentation, 'journal_response', folder)
    dump_schema_to_file(JournalFilterQuery, 'journal_filter', folder)
    # download excel:
    dump_schema_to_file(SalesOrderDownloadSchema, 'sales_order_excel', folder)
    # download excel:
    dump_schema_to_file(PackingListDownloadSchema, 'packing_list_download', folder)
    # open for edit:
    dump_schema_to_file(SalesOrderOpenSchema, 'sales_order_open', folder)
    # parameters for logistics transactions get schema:
    dump_schema_to_file(
        LogisticsTransactionsGetSchema, 'logistics_transactions_parameters', folder
    )
    # schema for delete order terms:
    dump_schema_to_file(DeliveryPeriodDeleteSchema, 'delivery_periods_del', folder)

    # schema for delete order terms:
    dump_schema_to_file(OrderTermsRemoveSchema, 'order_terms_del', folder)
    # schema for user settings:
    dump_schema_to_file(UserSettings, 'user_settings', folder)
    # schema for tenant settings:
    dump_schema_to_file(TenantSettings, 'tenant_settings', folder)
    # schema for packing list shipping params
    dump_schema_to_file(ShippingParameters, 'packing_list_shipping', folder)
    dump_schema_to_file(SetStatus, 'packing_list_set_status', folder)
    # schema for packing list labels params
    dump_schema_to_file(LabelsParameters, 'packing_list_labels', folder)
    # schema for packing list cancel params
    dump_schema_to_file(CancelParameters, 'packing_list_cancel', folder)

    dump_schema_to_file(SetTwoFactorAuthSchema, 'set_two_factor_auth', folder)
    dump_schema_to_file(TwoFactorAuthSchema, 'two_factor_auth', folder)
    dump_schema_to_file(LoginSchema, 'login', folder)


@folder_option
@api.command()
def generate_external_schemas(folder):
    """Generate json schemas for external documentation"""
    shared_schemas(folder)
    new_style_endpoints = [
        (ExternalSaleSchema, SaleGet, 'sale'),
        (ExternalTransitSchema, TransitGet, 'transit'),
    ]
    for endpoint in new_style_endpoints:
        generate_new_style_endpoints_schemas(folder, *endpoint, external=True)

    foxpro_sww_endpoints = [
        (SWWStockDetailGetSchema, 'swapi_stock_detail_get'),
        (SWWStockLogicalGetSchema, 'swapi_stock_logical_get'),
        (SWWStockPerLocationGetSchema, 'swapi_stock_per_location_get'),
        (SWWSkuGetSchema, 'swapi_sku_get'),
        (SWWCouponsCheckGetSchema, 'swapi_coupons_check_get'),
        (SWWCouponsRedeemPostSchema, 'swapi_coupons_redeem_post'),
        (SWWCouponsGetSchema, 'swapi_coupons_get'),
        (SWWCouponsPostSchema, 'swapi_coupons_post'),
        (SWWWholesaleCustomerSalesSchema, 'swapi_wholesale_customer_sales_get'),
    ]
    for endpoint in foxpro_sww_endpoints:
        generate_sww_schemas(folder, *endpoint)


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if callable(obj):
            return str(obj)
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, collections.abc.ValuesView):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


def dump_file(name, data, folder=None):
    """dump the data to a json file"""
    if not folder:
        folder = 'spynl_swagger'
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = os.path.join(folder, name + '.json')
    with open(filename, 'w') as outfile:
        json.dump(data, outfile, indent=2, cls=CustomEncoder)


# Generic schemas
class Response(Schema):
    status = fields.String(metadata={'description': "'ok' or 'error'"})

    class Meta:
        ordered = True


class SaveResponse(Response):
    data = fields.List(
        fields.String,
        metadata={'description': 'One item array containing the _id of the added item'},
    )


def shared_schemas(folder):
    """schemas used in both the internal and external documentation."""
    # generic add/save response that returns the string of added document id
    schema = JSONSchema().dump(SaveResponse())
    dump_file('save_response', schema, folder)
    new_style_endpoints = [
        (WholesaleCustomerSchema, WholesaleCustomerGetSchema, 'wholesale_customer')
    ]
    for endpoint in new_style_endpoints:
        generate_new_style_endpoints_schemas(folder, *endpoint, external=True)

    # cancel parameters for sale:
    dump_schema_to_file(SaleCancel, 'sale_cancel_parameters', folder)

    # schemas for customer/sales (barcodes per customer):
    dump_schema_to_file(CustomerSalesSchema, 'sales_per_barcode', folder)
    dump_schema_to_file(CustomerSalesResponse, 'sales_per_barcode_response', folder)


def generate_new_style_endpoints_schemas(
    folder, data_schema, query_schema, base_name, external=False
):
    class SaveParameters(Schema):
        data = fields.Nested(data_schema, exclude=['tenant_id'])

    class GetResponse(Response):
        data = fields.Nested(data_schema, many=True)

    context = {'external': external}
    # save/add parameters:
    dump_schema_to_file(
        SaveParameters,
        '{}_save'.format(base_name),
        folder,
        context={**context, 'method': 'dump'},
    )
    if query_schema:
        # get parameters:
        dump_schema_to_file(
            query_schema, '{}_get_parameters'.format(base_name), folder, context=context
        )
    # get response:
    dump_schema_to_file(
        GetResponse, '{}_get_response'.format(base_name), folder, context=context
    )


def generate_sww_schemas(folder, data_schema, base_name):
    dump_schema_to_file(data_schema, '{}_response'.format(base_name), folder)


def dump_schema_to_file(schema, file_name, folder, context=None):
    schema = JSONSchema(context=context).dump(schema())
    dump_file(file_name, schema, folder)
