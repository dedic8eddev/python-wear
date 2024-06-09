"""Schema for transactions regarding receivings."""
import uuid

from bson.objectid import InvalidId, ObjectId
from marshmallow import ValidationError, fields, post_load, pre_load, validate

from spynl_schemas.fields import Nested
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.shared_schemas import BaseSchema, ProductSchema, SkuSchema
from spynl_schemas.utils import BAD_CHOICE_MSG, cast_percentage


class ReceivingSchema(BaseSchema):
    """The receiving transaction."""

    _id = fields.UUID(load_default=uuid.uuid4)
    docNumber = fields.UUID(
        load_default=uuid.uuid4,
        metadata={
            'description': 'A valid UUID (version 4) that identifies the new '
            'transaction.'
        },
    )
    orderNumber = fields.String(
        metadata={
            'description': 'The human-readable incremental number which is assigned '
            'by the backend once the order is in the complete status. This order '
            'number is usually printed on the order confirmation. The order number '
            'format is <Document Slug>-<Number>. Example: RCV-100'
        }
    )
    remarks = fields.String(
        metadata={
            'description': 'A free text field for adding an additional message to an '
            'order.'
        }
    )
    warehouseId = fields.String(
        required=True,
        metadata={
            'description': 'The Mongo-id of the warehouse document from the database.'
        },
    )
    skus = Nested(
        SkuSchema,
        many=True,
        metadata={
            'description': 'A list of skus that also contains the information that is '
            'normally stored on the product level. The order of this list is the '
            'scanning order.\n'
            ' This list of skus only exists in the draft state of the receiving. The '
            'first time a receiving is saved while marked as complete or unconfirmed, '
            'the skus will be transformed into a products array. A receiving should '
            'have a skus array or a products array, never both.'
        },
    )
    products = Nested(
        ProductSchema,
        exclude=('skus.salesOrder',),
        many=True,
        metadata={
            'description': 'Array with product items. Contains the products received. '
            'This is the form used for complete and unconfirmed receivings.'
        },
    )
    totalBuyPrice = fields.Float(
        metadata={'description': 'Total of the buyPrice in the products list.'}
    )
    totalValuePrice = fields.Float(
        metadata={'description': 'Total of the valuePrice in the products list.'}
    )
    totalPrice = fields.Float(
        metadata={'description': 'Total of the price in the products list.'}
    )
    totalQty = fields.Integer(
        metadata={'description': 'Total of the qty in the products list.'}
    )
    status = fields.String(
        required=True,
        validate=validate.OneOf(
            choices=['complete', 'draft', 'unconfirmed'], error=BAD_CHOICE_MSG
        ),
        metadata={
            'description': "In the 'unconfirmed' status the document has the same "
            "structure as in the 'complete' status, but the document will not be "
            'synced to foxpro. In this state prices etc can still be changed. If the '
            "document is 'complete', it will be synced to foxpro. The status can "
            "change from 'draft' to 'unconfirmed' to 'complete', or directly from "
            "'draft' to 'complete'."
        },
    )
    supplierOrderReference = fields.List(fields.String)

    @pre_load
    def nest_skus_into_products(self, data, **kwargs):
        if data.get('status') != 'draft' and 'products' not in data:
            skus = {}
            for sku in data.pop('skus', []):
                if sku['barcode'] not in skus:
                    skus[sku['barcode']] = sku
                else:
                    skus[sku['barcode']]['qty'] += sku['qty']

            products = {}
            for sku in skus.values():
                if sku['articleCode'] not in products:
                    products[sku['articleCode']] = {**sku, 'skus': []}
                products[sku['articleCode']]['skus'].append(sku.copy())

            data['products'] = list(products.values())
        elif data.get('status') != 'draft' and 'products' in data and 'skus' in data:
            raise ValidationError(
                'A receving cannot have both products and top level skus.'
            )
        elif data.get('status') == 'draft' and 'products' in data:
            raise ValidationError('A draft cannot have products')
        return data

    @post_load
    def handle_warehouse_id(self, data, **kwargs):
        try:
            data['warehouseId'] = ObjectId(data['warehouseId'])
        except (KeyError, InvalidId):
            pass
        return data

    @post_load
    def set_sizes(self, data, **kwargs):
        if data.get('status') != 'draft':
            for product in data.get('products', []):
                if 'sizes' in product:
                    continue
                sizes = []
                if 'skus' not in product:
                    continue

                # https://stackoverflow.com/a/480227
                seen = set()
                seen_add = seen.add
                sizes = sorted(
                    (
                        (sku['sizeIndex'], sku['size'])
                        for sku in product['skus']
                        if 'sizeIndex' in sku
                        and 'size' in sku
                        and not (sku['size'] in seen or seen_add(sku['size']))
                    ),
                    key=lambda s: s[0],
                )
                product['sizes'] = [s[1] for s in sizes]
        return data

    @post_load
    def calculate_totals(self, data, **kwargs):
        """Calculate totals."""
        data.update(
            {'totalQty': 0, 'totalBuyPrice': 0, 'totalValuePrice': 0, 'totalPrice': 0}
        )

        if data['status'] == 'draft':
            for sku in data.get('skus', []):
                data['totalQty'] += sku.get('qty', 0)
                data['totalPrice'] += sku.get('price', 0) * sku.get('qty', 0)
                data['totalBuyPrice'] += sku.get('buyPrice', 0) * sku.get('qty', 0)
                data['totalValuePrice'] += sku.get('valuePrice', 0) * sku.get('qty', 0)
        else:
            for p in data.get('products', []):
                qty = 0
                for sku in p.get('skus', []):
                    qty += sku.get('qty', 0)

                data['totalQty'] += qty
                data['totalPrice'] += p.get('price', 0) * qty
                data['totalBuyPrice'] += p.get('buyPrice', 0) * qty
                data['totalValuePrice'] += p.get('valuePrice', 0) * qty

        return data

    @staticmethod
    def format_ordernr(order, order_number):
        order['orderNumber'] = 'RCV-%d' % order_number

    @staticmethod
    def generate_fpqueries(receiving, *common):
        """
        Return the needed foxpro queries for a receiving transaction.
        A foxpro event should only be generated for a complete receiving.
        """
        query = [
            *common,
            ('uuid', resolve(receiving, 'docNumber')),
            ('remark', resolve(receiving, 'remarks')),
            ('refid', resolve(receiving, 'orderNumber')),
        ]

        for supplier in receiving.get('supplierOrderReference', []):
            query.append(('reference', supplier))

        for product in receiving['products']:
            buy_price = cast_percentage(product.get('buyPrice', 0))
            sell_price = cast_percentage(product.get('price', 0))
            for sku in product['skus']:
                query.extend(
                    [
                        ('barcode', resolve(sku, 'barcode')),
                        ('qty', resolve(sku, 'qty')),
                        ('price', buy_price),
                        ('sellprice', sell_price),
                    ]
                )

        return serialize([('Receivings', query)])

    @classmethod
    def prepare_for_pdf(cls, order, db=None, tenant_id=None):
        for product in order.get('products', []):
            ProductSchema.generate_sku_table(product)
        if db and tenant_id:
            cls.lookup_warehouse_data(order, db, tenant_id)
        return order

    @classmethod
    def lookup_warehouse_data(cls, order, db, tenant_id):
        """look up the name of the warehouse"""
        warehouse = db.warehouses.find_one(
            {'_id': order['warehouseId'], 'tenant_id': tenant_id}
        )
        if warehouse:
            order['warehouseName'] = warehouse.get('name', '')
