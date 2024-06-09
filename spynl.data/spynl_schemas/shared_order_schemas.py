import datetime
import uuid

from babel import Locale, UnknownLocaleError, numbers
from marshmallow import fields, post_load, pre_load, validate, validates

from spynl_schemas.fields import LabelField, LenientDateTimeField, Nested
from spynl_schemas.foxpro_serialize import format_fp_date, resolve, serialize
from spynl_schemas.shared_schemas import BaseSchema, Currency, ProductSchema, Schema
from spynl_schemas.utils import lookup


class LenientAddressSchema(Schema):
    address = fields.String()
    zipcode = fields.String()
    city = fields.String()
    country = fields.String()
    telephone = fields.String()


class AddressSchema(Schema):
    address = fields.String(required=True)
    zipcode = fields.String(required=True)
    city = fields.String(required=True)
    country = fields.String(required=True)
    telephone = fields.String()


class WholesaleCustomerSchema(Schema):
    name = fields.String()
    email = fields.String()
    legalName = fields.String()
    id = fields.String(metadata={'description': 'refers to cust_id (fox pro)'})
    _id = fields.UUID(required=True, metadata={'description': 'refers to _id'})
    vatNumber = fields.String()
    cocNumber = fields.String()
    bankNumber = fields.String()
    clientNumber = fields.String()
    credit = fields.Int()
    currency = Nested(Currency, exclude=['purchaseFactor', 'cbs', 'description'])
    language = fields.String()
    address = Nested(LenientAddressSchema)
    deliveryAddress = Nested(LenientAddressSchema)
    preSaleDiscount = fields.Float()
    paymentTerms = fields.String(
        metadata={
            'description': 'Identification string of the payment terms that apply for '
            'this customer.'
        }
    )
    region = fields.String()

    @validates('email')
    def validate_email(self, value):
        # We only validate in case it's not an empty string.
        if value:
            fields.Email()._validate(value)

    @pre_load()
    def currency_backwards_compatibility(self, data, **kwargs):
        if 'currency' in data and isinstance(data['currency'], str):
            data['currency'] = {'label': data['currency']}
        return data


class OrderProductSchema(ProductSchema):
    localizedPrice = fields.Float(
        required=True,
        metadata={
            'description': "Price in the buyer's currency, including presale discounts"
        },
    )
    localizedBasePrice = fields.Float(
        metadata={
            'description': "Price in the buyer's currency, before any presale discounts"
        }
    )
    localizedSuggestedRetailPrice = fields.Float(
        required=True,
        metadata={'description': "Suggested retail price in the buyer's currency"},
    )
    directDelivery = fields.String(
        validate=validate.OneOf(['on', 'off', 'unavailable']),
        load_default='unavailable',
        metadata={
            'description': 'Direct delivery is used for products that are already '
            "available. If the products are available, the value is 'unavailable'. "
            "When the product is available, direct delivery can be either 'on' or "
            "'off' depending on when the products should be delivered."
        },
    )
    deliveryPeriod = fields.String(load_default='')

    class Meta(ProductSchema.Meta):
        exclude = ('skus.purchaseOrder',)


class BaseOrderSchema(BaseSchema):
    _id = fields.UUID(load_default=uuid.uuid4)
    orderNumber = fields.String()
    docNumber = fields.UUID(load_default=uuid.uuid4)
    customReference = fields.String(
        validate=validate.Length(max=32),
        metadata={
            'description': 'A reference field that can be freely used by the agent. '
            'E.g. for a customer reference or a recurring order reference.'
        },
    )
    remarks = fields.String()
    deliveryPeriodLabel = LabelField(
        metadata={'description': 'The delivery period label'}
    )
    fixDate = LenientDateTimeField(
        metadata={
            'description': 'The last date items should be '
            'shipped to the customer. This is an ISO date/time object. This property '
            'should be communicated to the backend in the local time of the user.'
        }
    )
    reservationDate = LenientDateTimeField(
        metadata={
            'description': 'The first available date items should be shipped to the '
            'customer. This is an ISO date/time object. This property should be '
            'communicated to the backend in the local time of the user.'
        }
    )
    customer = Nested(WholesaleCustomerSchema, required=True)
    shippingCarrier = fields.String()
    type = fields.String(
        load_default='sales-order',
        validate=validate.OneOf(choices=['sales-order', 'packing-list']),
    )

    def set_date_fields(self, data):
        for k in ('reservationDate', 'fixDate'):
            if k in data and isinstance(data[k], datetime.datetime):
                data[k] = str(
                    datetime.datetime(
                        data[k].year, data[k].month, data[k].day
                    ).isoformat()
                )

    @post_load
    def postprocess(self, data, **kwargs):
        # if a product has no skus, remove it.
        data['products'] = [p for p in data['products'] if p['skus']]
        self.set_date_fields(data)
        return data

    @staticmethod
    def format_ordernr(order, order_nr):
        if order['type'] == 'packing-list':
            prefix = 'PL'
        elif order['type'] == 'sales-order':
            prefix = 'SO'
        else:
            return
        order['orderNumber'] = '%s-%s' % (prefix, order_nr)

    @staticmethod
    def generate_fpqueries(data, *common):
        datefmt = '%d-%m-%Y'
        fixdate = ''
        if data.get('fixDate'):
            fixdate = format_fp_date(
                datetime.datetime.fromisoformat(data['fixDate']), datefmt
            )

        reservationdate = ''
        if data.get('reservationDate'):
            reservationdate = format_fp_date(
                datetime.datetime.fromisoformat(data['reservationDate']), datefmt
            )

        sendorder = [
            *common,
            ('refid', resolve(data, 'docNumber')),
            ('ordernumber', resolve(data, 'orderNumber')),
            ('uuid', resolve(data, 'customer._id')),
            ('nettterm', resolve(data, 'nettTerm')),
            ('reservationdate', reservationdate),
            ('fixdate', fixdate),
            ('discperc1', resolve(data, 'discountPercentage1')),
            ('discterm1', resolve(data, 'discountTerm1')),
            ('discperc2', resolve(data, 'discountPercentage2')),
            ('discterm2', resolve(data, 'discountTerm2')),
            ('remarks', resolve(data, 'remarks')),
            ('customreference', resolve(data, 'customReference')),
            ('carrier', resolve(data, 'shippingCarrier')),
            ('deliveryPeriod', resolve(data, 'deliveryPeriodLabel')),
        ]

        if data['type'] == 'packing-list':
            action = 'pakbon'
        elif data.get('directDelivery'):
            action = 'order'
        else:
            action = 'ordero'
        sendorder.append(('action', action))

        for product in data['products']:
            for sku in product['skus']:
                barcode = resolve(sku, 'barcode')

                if 'remarks' in sku:
                    barcode += ':' + resolve(sku, 'remarks')

                sendorder.extend(
                    [
                        ('barcode', barcode),
                        ('qty', resolve(sku, 'qty')),
                        # NOTE we send price in cents
                        ('price', product['localizedPrice'] * 100),
                    ]
                )
                if data['type'] == 'packing-list':
                    sendorder.append(('picked', resolve(sku, 'picked')))

        return serialize(
            [('sendOrder', sendorder)],
            whitelist=[('sendOrder', 'fixdate'), ('sendOrder', 'reservationdate')],
        )

    @classmethod
    def prepare_for_pdf(cls, order, *args, **kwargs):
        try:
            if 'language' in order['customer']:
                Locale(order['customer']['language'])
        except UnknownLocaleError:
            order['customer'].pop('language')
        cls.clean_up_currency(order['customer'])

        def get_row_color(sku):
            return sku.get('colorCode', '') + sku.get('colorDescription', '')

        for product in order.get('products', []):
            ProductSchema.generate_sku_table(
                product, price_key='localizedPrice', row_color_definition=get_row_color
            )
            ProductSchema.convert_properties_to_dict(product)

            for size in lookup(product, 'skuTable.available_sizes', []):
                # There is space for about 30 characters for the sizes in the header
                if len(size) > 30 / len(product['skuTable']['available_sizes']):
                    product['skuTable']['use_small_header_font'] = True
                    break

        cls.calculate_totals(order)
        cls.convert_datetimes_to_dates(order)
        return order

    @classmethod
    def clean_up_currency(cls, data):
        """
        With the new dict format, code should always be an iso code, this
        cleanup is for old data
        """
        if 'currency' in data and isinstance(data['currency'], str):
            data['currency'] = {'code': data['currency']}
            foxpro_to_real = {'DDK': 'DKK', 'EURO': 'EUR'}
            label = data['currency']['code']
            label = foxpro_to_real.get(label, label)

            if not numbers.is_currency(label):
                label = ''
            data['currency']['code'] = label

    @classmethod
    def calculate_totals(cls, data):
        """
        totalQuantity: the total number of items in this order
        totalLocalizedPrice: total of the order using the localized price.
        """
        data['totalQuantity'] = 0
        data['totalLocalizedPrice'] = 0
        for product in data.get('products', []):
            data['totalQuantity'] += product.get('skuTable', {}).get('totalQuantity', 0)
            data['totalLocalizedPrice'] += product.get('skuTable', {}).get(
                'totalPrice', 0
            )

    @classmethod
    def convert_datetimes_to_dates(cls, data):
        for field in ('reservationDate', 'fixDate', 'signatureDate'):
            if data.get(field):
                if data.get(field) and isinstance(data.get(field), str):
                    data[field] = datetime.datetime.fromisoformat(data[field]).date()

    @classmethod
    def get_order_terms_for_draft(cls, data, db=None, tenant_id=None):
        """
        If an order is a draft, it's stored without order terms. These are
        needed for the pdf, so they are loaded from the database here.
        """
        if not db or not tenant_id:
            return
        order_terms = db.order_terms.find_one(
            {
                'tenant_id': tenant_id,
                '$or': [
                    {
                        'language': data['customer'].get('language'),
                        'country': data['customer'].get('address', {}).get('country'),
                    },
                    {'language': 'default', 'country': 'default'},
                ],
            }
        )
        if order_terms:
            data['orderTerms'] = order_terms
