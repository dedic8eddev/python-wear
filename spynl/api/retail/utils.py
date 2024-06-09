"""reporting exceptions"""
import numbers

import bson
from marshmallow import EXCLUDE, Schema, fields, post_load, validate

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction

from spynl.api.auth.utils import is_sales_admin
from spynl.api.mongo.query_schemas import FilterSchema

PAYMENT_METHODS = [
    'webshop',
    'storecredit',
    'pin',
    'cash',
    'creditcard',
    'creditreceipt',
    'withdrawel',
    'consignment',
]


def limit_wholesale_queries(data, context):
    request = context['request']
    if not is_sales_admin(request):
        if context.get('region'):
            # Match prefix, DE would find DE1 DE2.
            data['region'] = {
                '$regex': bson.regex.Regex('^' + context['region']),
                '$options': 'i',
            }
        else:
            data['agentId'] = context['user_id']
    return data


def check_warehouse(db, warehouse_id):
    """check if the warehouse exists (compare warehouses.wh)"""
    wh = db.warehouses.find_one({'wh': warehouse_id})
    if not wh:
        raise IllegalAction(
            _(
                'non-existent-warehouse',
                'The warehouse with Id ${warehouse} does not exist.',
                mapping={'warehouse': warehouse_id},
            )
        )


class SortSchema(Schema):
    """
    Sort schema for aggregation endpoints. For get endpoints, please use the
    sort schema in mongo.query_schemas.
    """

    field = fields.String(required=True)
    direction = fields.Int(validate=validate.OneOf([-1, 1]), load_default=1)

    class Meta:
        unknown = EXCLUDE
        ordered = True


class TransactionFilterSchema(FilterSchema):
    type = fields.Int(validate=validate.OneOf([2, 3, 9]))
    warehouseId = fields.String(
        metadata={
            'description': 'Filter sales transactions by location/shop identifier. If '
            'type is 3, it looks for the warehouseId in both shop.id and '
            'transit.transitPeer.'
        }
    )
    shopName = fields.String()
    customerId = fields.String()
    customerLoyaltyNr = fields.String()
    customerEmail = fields.String()
    fiscal_receipt_nr = fields.String(allow_none=True)
    nr = fields.String()
    receiptNr = fields.Int(
        metadata={'description': 'Locate a sale transaction by receipt number.'}
    )
    paymentMethod = fields.List(
        fields.String, validate=validate.ContainsOnly(PAYMENT_METHODS)
    )

    @post_load
    def handle_warehouse(self, data, **kwargs):
        if 'warehouseId' in data:
            if data.get('type') == 3:
                warehouse_id = data.pop('warehouseId')
                data['$or'] = [
                    {'shop.id': warehouse_id},
                    {'transit.transitPeer': warehouse_id},
                ]
            else:
                data['shop.id'] = data.pop('warehouseId')
        return data

    @post_load
    def handle_mapped_fields(self, data, **kwargs):
        mapping = {
            'shopName': 'shop.name',
            'customerId': 'customer.id',
            'customerLoyaltyNr': 'customer.loyaltynr',
            'customerEmail': 'customer.email',
        }
        for key in mapping:
            if key in data:
                data[mapping[key]] = data.pop(key)
        return data

    @post_load
    def handle_payment_types(self, data, **kwargs):
        if len(data.get('paymentMethod', [])) == 1:
            data['payments.{}'.format(data['paymentMethod'][0])] = {'$ne': 0}
            data.pop('paymentMethod')
        elif len(data.get('paymentMethod', [])) > 1:
            payment_filter = []
            for method in data.pop('paymentMethod', []):
                payment_filter.append({f'payments.{method}': {'$ne': 0}})
            data['$or'] = payment_filter

        return data

    @post_load
    def set_type(self, data, **kwargs):
        if 'type' not in data:
            data['type'] = {'$in': [2, 3, 9]}
        return data


def round_results(data, decimals=2):
    """
    Rounds all numeric fields to 2 decimals.

    Modifies the data in place
    """
    for row in data:
        for key, value in row.items():
            if isinstance(value, numbers.Number):
                row[key] = round(value, decimals)


def flatten_result(result):
    """
    Flatten a list of results.

    All nested keys in a result move to top level.
    """

    def f(d, prefix=''):
        flat = {}
        for key, val in d.items():
            if prefix:
                key = '%s%s' % (prefix, key.capitalize())
            if isinstance(val, dict):
                flat.update(f(val, prefix=key))
            else:
                flat[key] = val
        return flat

    return [f(i) for i in result]


def prepare_for_export(result):
    flat = flatten_result(result)
    header = list(flat[0].keys()) if flat else []
    return flat, header
