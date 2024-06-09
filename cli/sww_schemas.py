""" Schemas for generating api gateway documentation """

from marshmallow import Schema, fields

from spynl_schemas.fields import Nested


class OrderedSchema(Schema):
    class Meta:
        ordered = True


class SWWStandardGetSchema(OrderedSchema):
    response = fields.String(
        metadata={'description': 'The status of the response: "ok" or "error"'}
    )


class SWWDetailStockSchema(OrderedSchema):
    maincolor = fields.String(
        metadata={'description': 'The main color code of the product.'}
    )
    maincolordescription = fields.String(
        metadata={
            'description': 'A human readable description of the main color of the '
            'product.'
        }
    )
    qty = fields.Integer(
        metadata={'description': 'How many items are available in stock.'}
    )
    size = fields.String(
        metadata={'description': 'The size of the product. Example: S, M, L'}
    )
    sizeindex = fields.Integer(
        metadata={
            'description': 'In which order the size should be displayed. Can be used '
            'for building a color/size matrix. Example: S:0, M:1, L:2'
        }
    )
    subcolor = fields.String(
        metadata={'description': 'The secondary color code of the product.'}
    )
    subcolordescription = fields.String(
        metadata={
            'description': 'A human readable description of the secondary color of the '
            'product.'
        }
    )
    variant = fields.String(
        metadata={
            'description': 'The article codes of the color and size variations of the '
            'same group of products.'
        }
    )


class SWWStockDetailGetSchema(SWWStandardGetSchema):
    stock = Nested(
        SWWDetailStockSchema,
        load_default=dict,
        metadata={
            'description': 'An array of objects with the items which are in stock.'
        },
    )
    sizes = fields.List(
        fields.String,
        metadata={'description': 'An array of strings of the available sizes.'},
    )


class SWWPerLocationStockSchema(SWWDetailStockSchema):
    shop = fields.String(
        metadata={
            'description': 'The human readable location name where the item is in stock'
        }
    )
    warehouseid = fields.String(
        metadata={
            'description': 'The location id/primary key in the Softwear database. '
            'This id should be used when referencing a location.'
        }
    )


class SWWStockPerLocationGetSchema(SWWStandardGetSchema):
    stock = Nested(
        SWWPerLocationStockSchema,
        load_default=dict,
        metadata={
            'description': 'An array of objects with the items which are in stock.'
        },
    )
    sizes = fields.List(
        fields.String,
        metadata={'description': 'An array of strings of the available sizes.'},
    )


class SWWStockLogicalGetSchema(SWWStandardGetSchema):
    stock = fields.List(
        fields.Boolean,
        metadata={
            'description': 'An array of booleans (true/false) indicating if the '
            'item(s) is available in stock or not.'
        },
    )


class SWWCareSchema(OrderedSchema):
    temperature = fields.Integer(
        metadata={'description': 'The tempature at which to wash the product.'}
    )
    bleach = fields.Integer(
        metadata={'description': 'If bleach can be used and how much is recommended.'}
    )
    iron = fields.Integer(
        metadata={'description': 'If ironing the product is recommended.'}
    )
    chemical = fields.Integer(metadata={'description': 'The formula for dry cleaning.'})
    dryer = fields.Integer(
        metadata={
            'description': 'If drying the product is recommended and at what tempature.'
        }
    )


class SWWGroupsSchema(OrderedSchema):
    name = fields.String(metadata={'description': 'The name of the property.'})
    value = fields.String(
        metadata={'description': 'The value contained in the property.'}
    )


class BaseSkuSchema(OrderedSchema):
    articlecode = fields.String(
        metadata={
            'description': 'The product/article code. This code is either provided by '
            'the client or the supplier.'
        }
    )
    articledescription = fields.String(
        metadata={'description': 'The human readable product description.'}
    )
    color = fields.String(
        metadata={
            'description': 'Color is the combination of main color and sub color code.'
        }
    )
    colorcode = fields.String(
        metadata={'description': 'The primary/main color code of the product.'}
    )
    sizelabel = fields.String(metadata={'description': 'The size of the product.'})


class SWWSkuGetSchema(BaseSkuSchema):
    supplier = fields.String(metadata={'description': 'The supplier of the product.'})
    brand = fields.String(metadata={'description': 'The brand of the product.'})
    articlegroup = fields.String(
        metadata={
            'description': 'The type or group of the product. Example: sweater, pants, '
            't-shirts'
        }
    )
    sellprice = fields.String(
        metadata={'description': 'The normal sell price of the product.'}
    )
    saleprice = fields.String(
        metadata={'description': 'The advertised sale price of the product.'}
    )
    vat = fields.String(
        metadata={'description': 'The VAT percentage applied to the product.'}
    )
    articlecodesupplier = fields.String(
        metadata={'description': 'The product code from the supplier.'}
    )
    barcode = fields.String(
        metadata={'description': 'The unique barcode of the product.'}
    )
    maincolor = fields.String(
        metadata={'description': 'The primary/main color of the product.'}
    )
    maincolorcode = fields.String(
        metadata={'description': 'The primary/main color code of the product.'}
    )
    subcolor = fields.String(
        metadata={'description': 'The secondary color of the product.'}
    )
    subcolorcode = fields.String(
        metadata={'description': 'The secondary color code of the product.'}
    )
    article_id = fields.String(
        metadata={'description': 'The unique identifier of the product.'}
    )
    storage = fields.String(
        metadata={
            'description': 'The physical location of the item in the store or '
            'warehouse.'
        }
    )
    care = Nested(
        SWWCareSchema,
        load_default=dict,
        metadata={
            'description': 'An object which provides care instructions. The numbers '
            'provided by each property coorespond to an image. Please contact '
            'Softwear for these images.'
        },
    )
    groups = Nested(
        SWWGroupsSchema,
        load_default=list,
        metadata={
            'description': 'An array of objects with additional client provided '
            'properties.'
        },
    )


class SWWGetStatusSkuSchema(BaseSkuSchema):
    timestamp = fields.String(
        metadata={'description': 'Time of the sale in the format YYYYMMDDhhmmss.'}
    )
    amount = fields.String(metadata={'description': 'The number of items sold'})
    price = fields.String(metadata={'description': 'The price of the item'})


class SWWWholesaleCustomerSalesSchema(OrderedSchema):
    response = fields.String(
        metadata={'description': 'status of the response, e.g. "ok"'}
    )
    lines = Nested(SWWGetStatusSkuSchema, many=True)


class SWWCouponsCheckGetSchema(SWWStandardGetSchema):
    coupon = fields.String(metadata={'description': 'The unique coupon id.'})
    customerUuid = fields.String(
        metadata={
            'description': 'The unique identifier of the customer. If this property is '
            'missing, the coupon can be used by any customer.'
        }
    )
    coupontype = fields.String(
        metadata={
            'description': 'The internal Softwear coupon type. Softwear supports '
            'various types of coupons.'
        }
    )
    value = fields.String(
        metadata={
            'description': 'The value of the coupon in cents. Example: a €5 coupon '
            'will be expressed as 500'
        }
    )


class SWWCouponsRedeemPostSchema(SWWStandardGetSchema):
    pass


class SWWCouponsGetSchema(OrderedSchema):
    number = fields.String(metadata={'description': 'The coupon id.'})
    date = fields.String(
        metadata={'description': 'The date provided as an ISO string.'}
    )
    type = fields.String(
        metadata={'description': 'The internal Softwear type of coupon.'}
    )
    amount = fields.String(
        metadata={'description': 'The value of the coupon presented as a decimal.'}
    )
    pcs = fields.String(metadata={'description': 'The number of coupons.'})
    status = fields.String(
        metadata={
            'description': 'The status of the coupon which can be either OPEN or '
            'REDEEMED.'
        }
    )


class SWWCouponsPostSchema(SWWStandardGetSchema):
    pass
