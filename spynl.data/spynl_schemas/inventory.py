"""Schema for transactions regarding inventories."""


from marshmallow import fields, post_load

from spynl_schemas.fields import Nested
from spynl_schemas.foxpro_serialize import serialize
from spynl_schemas.shared_schemas import BaseSchema, Schema


class ProductSchema(Schema):
    """An item in the product list."""

    qty = fields.Integer(
        required=True,
        metadata={
            'description': 'The quantity of items to be added (positive) or '
            'subtracted (negative) from the inventory.'
        },
    )
    barcode = fields.String(
        required=True, metadata={'description': 'The barcode of the product.'}
    )
    articleCode = fields.String(
        required=True,
        metadata={'description': 'The article code of the received product (article).'},
    )
    articleDescription = fields.String(
        metadata={'description': 'The description of the article.'}
    )
    color = fields.String(metadata={'description': 'The color of the Sku.'})
    sizeLabel = fields.String(metadata={'description': 'The size of the Sku.'})
    group = fields.String(metadata={'description': 'Article group for the Sku.'})
    brand = fields.String(metadata={'description': 'The brand name of the Sku.'})


class InventorySchema(BaseSchema):
    """The inventory transaction."""

    docNumber = fields.UUID(
        required=True,
        metadata={
            'description': 'A valid UUID (version 4) that identifies the new '
            'transaction.'
        },
    )
    remarks = fields.String(
        load_default='',
        metadata={'description': 'A free text field for adding an additional message.'},
    )
    warehouseId = fields.String(
        required=True,
        metadata={
            'description': 'The Mongo-id of the warehouse document from the database.'
        },
    )
    products = Nested(
        ProductSchema,
        load_default=list,
        many=True,
        metadata={
            'description': 'Array with product items. Contains the products that '
            'need to be updated in the inventory.'
        },
    )
    totalQty = fields.Integer(
        metadata={'description': 'Total of the qty in the products list.'}
    )

    @post_load
    def postprocess(self, data, **kwargs):
        """Make server calculations."""
        data.update(totalQty=sum([product['qty'] for product in data['products']]))
        return data

    @staticmethod
    def generate_fpqueries(inventory, *common):
        """
        Return the needed foxpro queries for a inventory transaction.

        The foxpro database expects the format "barcode;quantity" for every product
        seperated by a "|", example: 12345;2|45678;0|98989;-4
        """
        query = [*common, ('uuid', inventory['docNumber'])]
        barcode_template = '{p[barcode]};{p[qty]}'
        barcodes = [
            barcode_template.format(p=product) for product in inventory['products']
        ]
        query.append(('barcodes', '|'.join(barcodes)))

        return serialize([('sendinventory', query)])
