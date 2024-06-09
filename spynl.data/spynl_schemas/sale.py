import math
import uuid
from collections import defaultdict

from bson.objectid import ObjectId
from marshmallow import (
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)

from spynl_schemas.fields import Nested, ObjectIdField
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.shared_schemas import BaseSchema, CashierSchema, Schema, ShopSchema
from spynl_schemas.utils import (
    BAD_CHOICE_MSG,
    cast_percentage,
    get_card_provider,
    validate_warehouse_id,
)

# NOTE frontend right now sends totalDiscount which is the sum of
# all C and [SPACE] coupons and the global receipt discount.
# We want to get this global receipt discount seperately.


SALE_TYPE = 2
TRANSIT_TYPE = 3
CONSIGNMENT_TYPE = 9


def round_to_05(n):
    # https://stackoverflow.com/a/28427814
    a = 0.05
    return round(round(n / a) * a, -int(math.floor(math.log10(a))))


def load_reason(value):
    if isinstance(value, dict):
        return ReasonSchema().load(value)
    return fields.String().deserialize(value)


class CustomerSchema(Schema):
    """Redundant data, used for printing."""

    email = fields.String(allow_none=True)
    id = fields.String(
        allow_none=True,
        metadata={'description': 'The unique identifier of the customer record.'},
    )
    custnum = fields.String(allow_none=True)
    firstname = fields.String(allow_none=True)
    middlename = fields.String(allow_none=True)
    lastname = fields.String(allow_none=True)
    loyaltynr = fields.String(allow_none=True)
    points = fields.Int(
        allow_none=True,
        metadata={
            'description': 'The amount of points the customer had before this '
            'transaction'
        },
    )
    storecredit = fields.Float(allow_none=True)
    telephone = fields.String(allow_none=True)
    title = fields.String(allow_none=True)

    # NOTE temporarily turn off email validation because we still have problems
    # with clients getting stuck on bad emails.
    # @validates('email')
    # def validate_email(self, value):
    #     """Validate email except if it has empty string or is None"""
    #     if value:
    #         validate.Email()(value)

    @post_load
    def fetch_customer_data(self, data, **kwargs):
        """If only an id is given, fill in the missing data"""
        mappings = {
            'custnum': 'cust_id',
            'firstname': 'first_name',
            'middlename': 'middle_name',
            'lastname': 'last_name',
            'loyaltynr': 'loyalty_no',
            'points': 'points',
            'title': 'title',
        }
        if data.get('id') and 'db' in self.context and 'tenant_id' in self.context:
            try:
                _id = uuid.UUID(data['id'])
            except ValueError:
                _id = data['id']

            customer = self.context['db'].customers.find_one(
                {'_id': _id, 'tenant_id': self.context['tenant_id']}
            )
            if not customer:
                raise ValidationError('This customer does not exist.', '_id')

            for key, value in mappings.items():
                data.setdefault(key, customer.get(value))
            for contact in customer.get('contacts', []):
                if contact.get('primary'):
                    phone = contact.get('telephone') or contact.get('mobile')
                    data.setdefault('email', contact.get('email'))
                    data.setdefault('telephone', phone)
        return data


class PaymentSchema(Schema):
    """Information about payments."""

    webshop = fields.Float(
        load_default=0,
        metadata={
            'description': 'Optional field. If you do not provide it it will default '
            'to the final total amount of the transaction.'
        },
    )
    storecredit = fields.Float(
        load_default=0,
        metadata={
            'description': 'Contains the amount when a customer pays with store '
            'credit. NB: paying off store credit is not registered in payments '
            'but in the totalStoreCreditPaid field.'
        },
    )
    pin = fields.Float(
        load_default=0,
        metadata={
            'description': 'Amount paid using an electronic payment such as '
            'Maestro/PIN through a coupled pin device.'
        },
    )
    cash = fields.Float(
        load_default=0,
        metadata={
            'description': 'Amount paid using cash, change not included.'
            'NB: Change is not included in the payments object at all but is kept in '
            'the change field on the document. This should be changed at some point.'
        },
    )
    creditcard = fields.Float(
        load_default=0,
        metadata={
            'description': 'Amount paid using creditcard such as Visa, Mastercard, or '
            'American Express without using a coupled pin device.'
        },
    )
    creditreceipt = fields.Float(
        load_default=0,
        metadata={
            'description': 'The value of credit receipt (KT coupon) that is handed to '
            'the customer.'
        },
    )
    couponin = fields.Float(
        load_default=0,
        metadata={
            'description': 'Amount paid by redeeming activated gift vouchers (KU '
            'coupons).'
        },
    )
    withdrawel = fields.Float(
        load_default=0,
        metadata={
            'description': 'Contains cash withdrawals and cash deposits by the '
            'retailer. Does not relate to sales.'
        },
    )
    consignment = fields.Float(
        load_default=0,
        metadata={
            'description': 'Contains the value of items given in consignment. NB: '
            'this field should not be in this object since a consignment is just '
            'lending articles to a customer without any financial obligations.'
        },
    )


class CouponSchema(Schema):
    """Information about coupons."""

    id = fields.String(required=True)
    value = fields.Float(required=True)
    type = fields.String(
        required=True, validate=validate.OneOf(choices=list('CT'), error=BAD_CHOICE_MSG)
    )


class BaseItemSchema(Schema):
    """There are multiple types of receipt. This defines the base fields."""

    category = fields.String(
        load_default='barcode',
        validate=validate.OneOf(
            choices=['barcode', 'coupon', 'storecredit'], error=BAD_CHOICE_MSG
        ),
    )
    qty = fields.Int(
        required=True,
        metadata={'description': 'The quantity of items. Can be negative for returns'},
    )
    group = fields.String(
        allow_none=True,
        load_default='',
        metadata={
            'description': 'The group of the product. For example, this can be pants, '
            'jeans, sweaters, etc.'
        },
    )
    price = fields.Float(
        required=True,
        metadata={
            'description': 'The actual price that an item was sold for, not including '
            'distributed discounts.'
        },
    )
    nettPrice = fields.Float(
        metadata={
            'description': 'The original price of an individual item. The nettPrice - '
            'price determines the discount given to an individual item. This discount '
            'is not stored anywhere and thus needs to be inferred from these two '
            'values. If this value is not provided, it is defaulted to price.'
        }
    )
    found = fields.Boolean(load_default=True)
    lineTotal = fields.Float(
        metadata={
            'description': 'Total value of the line. Positive for what was paid, '
            'negative for coupons.'
        },
    )

    @post_load
    def set_nett_price(self, data, **kwargs):
        if 'price' in data:
            data.setdefault('nettPrice', data['price'])
        return data

    class Meta(Schema.Meta):
        additional = ('reqid',)


class StoreCreditItem(BaseItemSchema):
    """
    If a customer pays off their store credit, it ends up as a store credit item in the
    receipt. If a customer pays with store credit, it ends up in the payments.
    """

    type = fields.String(required=True, validate=validate.Equal('O'))


class ReasonSchema(Schema):
    key = fields.String(required=True)
    desc = fields.String(required=True)


class BarcodeItem(BaseItemSchema):
    barcode = fields.String(
        required=True,
        validate=validate.Length(min=1, max=13),
        metadata={
            'description': 'The barcode is a unique identifier (EAN/IAN) code which is '
            'usually printed on a label for scanning by a barcode scanner.'
        },
    )
    vat = fields.Float(
        required=True,
        metadata={
            'description': "The vat percentage for this item. Example: 21, 9 or 0"
        },
    )
    reason = fields.Function(
        deserialize=load_reason,
        allow_none=True,
        metadata={
            '_jsonschema_type_mapping': {'description': 'Either a dict or a string.'}
        },
    )
    changeDisc = fields.Field(allow_none=True)
    sizeLabel = fields.String(allow_none=True)
    color = fields.String(allow_none=True)
    articleDescription = fields.String(
        load_default='',
        allow_none=True,
        metadata={
            'description': 'The article description is an additional human-friendly '
            'description of the product.'
        },
    )
    articleCode = fields.String(
        load_default='',
        metadata={
            'description': 'The article code is usually a symbolic code which is '
            'assigned by the retail/wholesale client as a unique identifier for the '
            'particular product.'
        },
    )
    brand = fields.String(
        load_default='',
        metadata={
            'description': 'The brand of the product. For example, this can be the '
            'name of the manufacturer or supplier of the product.'
        },
    )

    @pre_load()
    def pop_brand(self, data, **kwargs):
        if data.get('brand') is None:
            data.pop('brand', None)
        return data

    class Meta(BaseItemSchema.Meta):
        additional = ('$$hashkey',)


class CouponItem(BaseItemSchema, CouponSchema):
    # we load the value from value or price, this is the easiest way to make it
    # required regardless of which they send. Putting it back on the right
    # field is handled by postprocessing.
    id = fields.String()

    price = fields.Float()
    value = fields.Float()

    type = fields.String(
        required=True,
        validate=validate.OneOf(choices=list('UITAC '), error=BAD_CHOICE_MSG),
    )

    @validates_schema
    def validate_price_value(self, data, **kwargs):
        if data['type'] in ['C', ' ']:
            key = 'value'
        else:
            key = 'price'

        if key not in data:
            raise ValidationError('Missing data for required field', key)

    class Meta(BaseItemSchema.Meta, CouponSchema.Meta):
        additional = ('vat', 'couponNr', 'barcode')


class LinkSchema(Schema):
    """
    Schema for the link object that links a consignment transaction to a sales
    transaction.

    The link.id and link.comment can refer backward or forward depending on
    where in the chain they are.

    When a linked transaction is made:
    1. older document link.id is _id of newer document
    2. older document link.comment is 'closed' if older document is a consignment
    3. newer document link.id is _id of older document
    4. newer document link.comment is nr of older document

    if the newer document gets linked to an ever newer document, the
    link.comment and link.id get overwritten to point forward instead of
    backward.

    Steps 1 and 2 are skipped in the case of a return, in other words, returns
    only link backwards.
    """

    comment = fields.String(
        metadata={
            'description': "Either 'closed' (in the case of a closed consignment) "
            'or the nr of the document this transaction links to.'
        }
    )
    id = fields.String(
        required=True,
        metadata={
            'description': 'String representation of the _id of the linked document'
        },
    )
    resource = fields.String(
        load_default='transactions',
        metadata={'description': 'The collection where the linked document is stored'},
    )
    type = fields.String(
        metadata={
            'description': 'Transaction type of the linked document in the case of '
            'sale or consignment. if type is return, this refers to the transaction '
            'itself, and the linked document will be the sale.'
        },
        validate=validate.OneOf(
            choices=['consignment', 'sale', 'return'], error=BAD_CHOICE_MSG
        ),
    )

    @post_load
    def fill_in_fields(self, data, **kwargs):
        """fill in fields based on the linked document."""
        if 'db' in self.context:
            transaction = self.context['db'].transactions.find_one(
                {'_id': ObjectId(data['id'])}
            )
            data['comment'] = transaction.get('nr')
            # if it links back to a sale, this is a return
            link_type = {2: 'return', 9: 'consignment'}
            data['type'] = link_type[transaction['type']]
        return data


class VATSchema(Schema):
    """schema for the calculated totals for the vat"""

    highvalue = fields.Number(metadata={'description': 'The high vat percentage.'})
    hightotal = fields.Number(
        metadata={
            'description': 'The total amount paid for high vat items, including the '
            'high VAT.'
        }
    )
    highamount = fields.Number(
        metadata={'description': 'The actual amount of high vat paid.'}
    )
    lowvalue = fields.Number(metadata={'description': 'The low vat percentage.'})
    lowtotal = fields.Number(
        metadata={
            'description': 'The total amount paid for low vat items, including the '
            'low VAT.'
        }
    )
    lowamount = fields.Number(
        metadata={'description': 'The actual amount of low vat paid.'}
    )
    zerovalue = fields.Number(metadata={'description': 'The zero vat percentage.'})
    zerototal = fields.Number(
        metadata={
            'description': 'The total amount paid for zero vat items, including the '
            'zero VAT.'
        }
    )
    zeroamount = fields.Number(
        metadata={'description': 'The actual amount of zero vat paid.'}
    )


class SaleSchema(BaseSchema):
    """The sale model"""

    _VAT_DEFAULTS = {'zerovalue': 0.0, 'lowvalue': 9.0, 'highvalue': 21.0}
    _ROUND_DEFAULT = True

    _id = ObjectIdField(load_default=ObjectId)

    receiptEmail = fields.String(
        metadata={
            'description': 'Field used by the frontend to prepopulate the form to '
            'send an receipt by email. Should not be used anymore when the email '
            'workflow changes.'
        }
    )
    nr = fields.String(
        load_default=lambda: uuid.uuid4().hex,
        metadata={
            'description': 'The unique identifier of the sale. For sales coming from '
            'the POS this is the wh number of the location, the device id and the '
            'incremental counter, eg: "50-12-19677". The incremental counter is also '
            'stored as `receiptNr`. \n'
            'This can also be the webshop order id, or if not provided it defaults to '
            'a UUID v4.',
            'external_description': 'The unique identifier of the sale. This can be '
            'the webshop order id, or if not provided it defaults to a UUID v4.',
        },
    )
    device_id = fields.String(
        required=True,
        validate=validate.Length(max=5),
        metadata={
            'description': 'Traditionally identified the POS device that created the '
            'sale. Could for example be "WEBSH".'
        },
    )
    type = fields.Constant(
        constant=SALE_TYPE,
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'number',
                'format': 'integer',
                'default': SALE_TYPE,
                'enum': [SALE_TYPE],
                'description': 'An integer that corresponds to a specific type of '
                'transaction',
            }
        },
    )

    shop = Nested(
        ShopSchema,
        required=True,
        metadata={
            'description': 'This is the physical or virtual location linked to a sales '
            'transaction for stock keeping purposes.'
        },
    )
    cashier = Nested(
        CashierSchema,
        required=True,
        metadata={'description': 'The sales agent or cashier creating the sale.'},
    )
    payments = Nested(
        PaymentSchema,
        load_default=dict(),
        metadata={
            'description': 'The amount that was paid per payment type towards the '
            'balance of the transaction. If no amount is provided, the amount will '
            'default to 0. Negative amounts are allowed for refunds.'
        },
    )
    coupon = Nested(
        CouponSchema,
        allow_none=True,
        many=True,
        metadata={
            'description': 'A coupon that the customer gets based on this receipt '
            'that they can redeem at a later time.'
        },
    )
    customer = Nested(
        CustomerSchema,
        allow_none=True,
        metadata={
            'description': 'The customer making the sale. This will link the sale to '
            "this customer's record."
        },
    )

    link = Nested(LinkSchema)

    # NOTE This is a new field which should store the discount given
    # over the total receipt. Previously we got totalDiscount which was
    # the sum of all C and ' ' coupons and the receipt discount.
    overallReceiptDiscount = fields.Float(
        load_default=0.0,
        metadata={
            'description': 'If you wish to give a discount over the entire '
            'sale then provide the amount in this field. The Softwear backend will '
            'distribute this discount amount over all products on the sale in '
            'proportion to their relative value.'
        },
    )
    totalDiscount = fields.Float(
        # required=True,
        metadata={
            'description': "DEPRECATED: use overallReceiptDiscount.",
            'external_description': 'DEPRECATED: use overallReceiptDiscount'
            '\n\n'
            'If you wish to give a discount over the entire '
            'sale then provide the amount in this field. The Softwear backend will '
            'distribute this discount amount over all products on the sale in '
            'proportion to their relative value.',
        }
    )
    receiptNr = fields.Int(
        allow_none=True,
        metadata={
            'description': 'The last part of `nr` for sales from the POS. The highest '
            'value of this field is used in pos-init to find the highest value for a '
            'particular device, so `nr` can be incremental per device.'
        },
    )
    fiscal_receipt_nr = fields.String(
        allow_none=True,
        metadata={'description': 'Receipt ID as it was returned by the printer'},
    )
    fiscal_shift_nr = fields.String(
        allow_none=True,
        metadata={'description': 'Shift ID as it was returned by the printer'},
    )
    fiscal_date = fields.String(
        allow_none=True,
        metadata={'description': 'Receipt date as it was returned by the printer'},
    )
    fiscal_printer_id = fields.String(
        allow_none=True,
        metadata={'description': 'Fiscal printer ID'},
    )
    return_original_nr = fields.String(
        allow_none=True,
        metadata={'description': 'Field that contains original receipt nr in returns.'},
    )
    buffer_id = fields.String(allow_none=True)
    printed = fields.String(allow_none=True)
    device = fields.String(allow_none=True)
    shift = fields.String(
        allow_none=True,
        metadata={
            'description': 'The shift this sale belongs to. This corresponds to the '
            'cycleId from the EOS document.'
        },
    )
    remark = fields.String(
        load_default='', metadata={'description': 'a remark related to the transaction'}
    )
    discountreason = fields.Function(
        deserialize=load_reason,
        allow_none=True,
        metadata={
            '_jsonschema_type_mapping': {'description': 'Either a dict or a string.'}
        },
    )
    withdrawelreason = fields.String(allow_none=True)
    receipt = fields.Method(
        deserialize='load_receipt',
        required=True,
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'array',
                'items': {'type': 'object'},
                'description': 'A list of barcode, store credit and/or coupon items. '
                'Please see [sale.py](https://gitlab.com/softwearconnect/spynl.data/'
                'blob/master/spynl_schemas/sale.py) for the corresponding schemas',
            }
        },
    )
    cardType = fields.String(
        allow_none=True,
        metadata={
            'description': 'Card type, as was provide by payPlaza in appPreferredName '
            "field, for example 'Visa_Credit' or 'Maestro'. Should be added only on "
            'PIN payment done with payPlaza (v4).'
        },
    )
    cardProvider = fields.String(
        allow_none=True,
        metadata={
            'description': 'The provider of the card used for coupled pin transactions.'
            'Automatically categorized based on cardtype.'
        },
    )

    # Fields that are calculated during postprocessing, added for documentation of get
    # endpoints (so marked with dump_only):
    vat = fields.Nested(
        VATSchema,
        metadata={
            'description': 'These values are calculated when a transaction gets saved.'
        },
    )
    couponTotals = fields.Dict(
        dump_only=True,
        metadata={
            'description': 'The sum of each type of coupon used on the transaction.'
        },
    )
    totalStoreCreditPaid = fields.Float(
        dump_only=True,
        metadata={
            'description': 'The amount paid to the customer\'s store credit balance.'
        },
    )
    totalNumber = fields.Int(
        dump_only=True,
        metadata={
            'description': 'The absolute total number of barcode and storecredit '
            'items in the receipt. E.g. if two items get bought, one returned and one '
            'storecredit, this will be 4.'
        },
    )
    totalReturn = fields.Int(
        dump_only=True,
        metadata={'description': 'The absolute total number of barcode returned'},
    )
    totalPaid = fields.Float(
        dump_only=True,
        metadata={
            'description': "The total amount paid with the 'cash', 'pin', "
            "'creditcard', 'creditreceipt', 'storecredit' and 'consignment' payment "
            'methods'
        },
    )
    totalCoupon = fields.Float(
        dump_only=True,
        metadata={'description': 'Total amount paid with A/U/I/T type coupons.'},
    )
    totalDiscountCoupon = fields.Float(
        dump_only=True,
        metadata={
            'description': "Total amount paid with C/' ' type coupons. This field is "
            'wrongly used in the frontend, which is why it is always set to 0 for '
            'now. (SPAPI-573)'
        },
    )

    pinInfo = fields.String()
    pinError = fields.String()
    loyaltyPoints = fields.Int(
        metadata={
            'description': 'The number of points the customer has at including any '
            'points gained from this transaction.'
        }
    )

    @pre_load
    def check_post_sale_coupon_array(self, data, **kwargs):
        if data.get('coupon') and not isinstance(data['coupon'], list):
            data['coupon'] = [data['coupon']]
        return data

    @pre_load
    def default_webshop_values(self, data, **kwargs):
        if not self.context.get('webshop'):
            return data
        data.setdefault('device_id', 'WEBSH')
        data.setdefault('cashier', {'id': 'WEBSHOP'})
        return data

    @pre_load
    def sanitize_remark(self, sale, **kwargs):
        remark = resolve(sale, 'remark')
        if remark is not None:
            remark = remark.replace('&', '')
            remark = remark.replace('/', '')
            sale['remark'] = remark
        return sale

    @staticmethod
    def cancel(sale):
        for item in sale['receipt']:
            item['qty'] *= -1

        for k, v in sale['payments'].items():
            sale['payments'][k] *= -1

        original_id = sale.pop('_id')
        original_nr = sale.pop('nr')

        sale['nr'] = uuid.uuid4()

        sale['link'] = LinkSchema().load(
            {'id': str(original_id), 'comment': str(original_nr), 'type': 'return'}
        )
        return sale

    def load_receipt(self, value):
        """
        Load the receipt items.

        Receipt items can be of different types. So we retrieve the right
        schema for each item and load it seperately. Combining the data and the
        errors.

        In the case we cannot find a the proper receipt schema (based on
        category) we will use a schema which only loads/validates the the
        category field.
        """
        if not isinstance(value, list):
            raise ValidationError([fields.List.default_error_messages['invalid']])

        schemas = defaultdict(
            BarcodeItem, storecredit=StoreCreditItem(), coupon=CouponItem()
        )

        result = []
        validation_errors = {}

        for idx, item in enumerate(value):
            try:
                data = schemas[item.get('category')].load(item)
            except ValidationError as e:
                validation_errors[idx] = e.normalized_messages()
                continue
            result.append(data)

        if validation_errors:
            raise ValidationError(validation_errors)
        return result

    @post_load
    def postprocess(self, data, **kwargs):
        """
        Make necessary calculations.

        1. calculate the totals.
        2. calculate the vat.
        3. calculate the calculate the change and the difference.
        4. round all values.

        """
        if self.context.get('cancel'):
            data = self.cancel(data)

        if not data.get('device') and 'user_info' in self.context:
            data['device'] = str(self.context['user_info']['_id'])
        if (
            not data.get('receiptNr')
            and 'db' in self.context
            and 'tenant_id' in self.context
        ):
            data['receiptNr'] = self.get_next_receiptnr(
                self.context['db'],
                self.context['tenant_id'],
                transaction_type=data['type'],
            )

        data.update(self.calculate_totals(data))

        # If this is a webshop sale and no payments are filled in we will
        # default the webshop payment method and the totalPaid property to the
        # to total amount minus discounts.
        if self.context.get('webshop') and not any(
            v for v in data['payments'].values()
        ):
            # set the payment method and totalPaid property.
            self.calculate_total_paid(data)
            data['payments']['webshop'] = data['totalPaid']

        data.update({'change': 0, 'difference': 0})

        if not data['payments'].get('withdrawel'):
            round_setting = self.context.get('round_setting')
            if round_setting is None:
                round_setting = self._ROUND_DEFAULT
            if data['type'] != CONSIGNMENT_TYPE:
                data.update(self.calculate_change_and_difference(data, round_setting))

            if self.context.get('cancel'):
                vat_settings = {
                    k.replace('value', ''): data['vat'].get(k, self._VAT_DEFAULTS[k])
                    for k in self._VAT_DEFAULTS
                }
            else:
                vat_settings = self.context.get('vat_settings') or self._VAT_DEFAULTS
                # remove value from the key, so it's easier to make additional new
                # keys (e.g. hightotal, highamount).
                vat_settings = {
                    key.replace('value', ''): float(value)
                    for key, value in vat_settings.items()
                }

            data.update(dict(vat=self.calculate_vat(data, vat_settings)))

        data.update(self.round_calculated_fields(data))

        if data.get('cardType'):
            data['cardProvider'] = get_card_provider(data['cardType'])

        return data

    @post_load
    def close_consignment(self, data, **kwargs):
        """
        A sale or consignment transaction can link to an older consignment, in
        that case the older consignment needs to be closed (see also docstring
        of the LinkSchema)
        """
        link_type = {2: 'sale', 9: 'consignment'}
        if (
            'link' in data
            and data['link'].get('type') == 'consignment'
            and 'db' in self.context
        ):
            new_link = LinkSchema().load(
                {
                    'id': str(data['_id']),
                    'comment': 'closed',
                    'type': link_type[data['type']],
                }
            )
            self.context['db'].transactions.update_one(
                {'_id': ObjectId(data['link']['id'])},
                {'$set': {'link': new_link, 'status': 'closed'}},
            )
        return data

    @staticmethod
    def round_calculated_fields(data):
        """Round all values that need rounding."""
        top_level_keys = [
            'totalAmount',
            'totalStoreCreditPaid',
            'totalNumber',
            'totalReturn',
            'totalPaid',
            'totalCoupon',
            'totalDiscountCoupon',
            'change',
            'difference',
        ]

        new_data = {key: round(data[key], 2) for key in top_level_keys if key in data}
        if 'vat' in data:
            new_data['vat'] = {
                key: round(value, 2) for key, value in data['vat'].items()
            }

        return new_data

    @staticmethod
    def calculate_totals(data):
        """
        Calculate the totals

        totalAmount: the total amount that is to be paid.
        totalStoreCreditPaid: the total amount paid to the customer's store credit.
        totalNumber: the total number of items.
        totalReturn: the total number of items returned.
        totalPaid: total amount paid with all payment methods.
        totalCoupon: total amount paid with A/U/I/T type coupons.
        totalDiscountCoupon: total amount paid with C/' ' type coupons.
        """
        new_data = dict(
            totalAmount=0.0,
            totalStoreCreditPaid=0.0,
            totalNumber=0.0,
            totalReturn=0.0,
            totalPaid=0.0,
            totalCoupon=0.0,
            totalDiscountCoupon=0.0,
        )
        coupon_data = defaultdict(float)

        for item in data['receipt']:
            if item['category'] == 'coupon':

                if item['type'] in (' ', 'C'):
                    price_key = 'value'
                else:
                    price_key = 'price'

                coupon_data[item['type']] += item[price_key]
            else:
                new_data['totalAmount'] += item['qty'] * item['price']

                if item['qty'] > 0:
                    new_data['totalNumber'] += item['qty']

                if item['qty'] < 0:
                    new_data['totalReturn'] -= item['qty']

                if item['category'] == 'storecredit':
                    new_data['totalStoreCreditPaid'] += item['qty'] * item['price']

        # NOTE totalPaid is calculated twice in different ways!
        new_data['totalPaid'] = sum(
            data['payments'].get(key, 0)
            for key in [
                'cash',
                'pin',
                'creditcard',
                'creditreceipt',
                'storecredit',
                'consignment',
                'webshop',
            ]
        )

        # NOTE SPAPI-573 frontend makes a mistake showing discounts. Fixed by
        # not calculating totalDiscountCoupon. Will be revisited later when refactoring
        # the sale model.
        new_data['totalDiscountCoupon'] = coupon_data[' '] + coupon_data['C']
        new_data['totalCoupon'] = (
            coupon_data['A'] + coupon_data['U'] + coupon_data['T'] - coupon_data['I']
        )
        new_data['couponTotals'] = coupon_data

        # NOTE totalDiscount is deprecated
        if 'totalDiscount' in data and 'overallReceiptDiscount' not in data:
            new_data['overallReceiptDiscount'] = (
                data.pop('totalDiscount') - new_data['totalDiscountCoupon']
            )

        return new_data

    @staticmethod
    def calculate_vat(data, vat_settings):
        """
        Calculate vat paid over barcode receipt items and 'A' coupons.

        Depends on receiptDiscount and totalDiscountCoupon to calculate
        the total discount given.

        To calculate vat we take the total of the receipt item.

        >>> total = price * qty * discount (in percentage)

        Remember that the total INCLUDES VAT. So if the VAT of an item is
        21% that means the total is actually 121%. So from this total we
        calculate the VAT.

        >>> amount = total / (vat_value + 100) * vat_value

        For barcodes we add this total and amount to the high/low/zero total
        over the receipt.
        For 'A' coupons this is a discount so we substract.
        """

        new_data = {}
        for key, value in vat_settings.items():
            new_data[key + 'value'] = value
            new_data[key + 'total'] = 0.0
            new_data[key + 'amount'] = 0.0

        # invert the dict for easy lookup of the vat type by value.
        vat_types = {value: key for key, value in vat_settings.items()}

        discount_factor = 1 - SaleSchema.calculate_total_discount(data)

        for item in data['receipt']:
            if item['category'] == 'barcode':
                vat_value = float(item['vat'])
                try:
                    vat_type = vat_types[vat_value]
                    # If the item vat value is not present in the tenant
                    # settings or the defaults. Skip.
                except KeyError:
                    continue
                modifier = 1
            elif item['category'] == 'coupon' and item['type'] == 'A':
                # We calculate VAT over A coupons and they only count for high
                # VAT items.
                vat_type = 'high'
                try:
                    vat_value = vat_settings[vat_type]
                except KeyError:
                    continue
                # This iteration handles a discount so we will add a negative
                # number to high{amount,total}.
                modifier = -1
            else:
                continue

            total = discount_factor * item['price'] * item['qty']
            new_data[vat_type + 'total'] += total * modifier

            amount = total / (vat_value + 100) * vat_value
            new_data[vat_type + 'amount'] += amount * modifier

        return new_data

    @staticmethod
    def calculate_change_and_difference(data, round=False):
        """
        Calculate the change and difference.

        Substract the totalAmount from all the payments and discounts.
        To calculate what has to be returned in change. If the the round flag
        is set to True then we round this change to the nearest 5 Cents and
        store the difference.
        """
        new_data = {
            'difference': 0,
            'change': (
                data['totalPaid']
                + data['totalCoupon']  # AUIT
                # + data['totalDiscount']  # C[SPACE] + receipt discount
                + data['totalDiscountCoupon']  # C[SPACE]
                + data['overallReceiptDiscount']  # Reicept Discount
                - data['totalAmount']
            ),
        }

        if new_data['change']:
            non_cash_fields = 'pin creditcard creditreceipt storecredit'.split()
            cash_only = all([data['payments'][key] == 0 for key in non_cash_fields])

            if round and cash_only:
                rounded_change = round_to_05(new_data['change'])
                # NOTE Difference is positive when tenant gains and negative
                # when loses. This is reflected in the calculation below.
                # If the original change is 4.98 it will be rounded to 5.00
                # 4.98 - 5.00 = -0.02 which is more change for the customer
                # and thus a loss for the tenant. The inverse then follows.
                difference = new_data['change'] - rounded_change
                new_data.update(dict(change=rounded_change, difference=difference))
        return new_data

    @staticmethod
    def calculate_total_discount(sale):
        # This calculation is also done as part of calculate_top_level_discounts
        # changes here should probably also be done there.
        discountable_amount = 0
        for item in sale['receipt']:
            if item['category'] == 'barcode':
                discountable_amount += item['price'] * item['qty']

        discountable_amount = round(discountable_amount, 3)

        try:
            # return sale['totalDiscount'] / discountable_amount
            # NOTE should be the following if they will provide the
            # receiptDiscount field.
            return (
                sale['overallReceiptDiscount'] + sale['totalDiscountCoupon']
            ) / discountable_amount
        except ZeroDivisionError:
            return 0

    @staticmethod
    def generate_fpqueries(sale, *common, cancel=False):
        """
        If it is a withdrawel. Only generate a "sendorder" query for a
        withdrawel.

        Otherwise, we generate one or more of the following:
            * a single "sendorder" query for the transaction.
            * zero or one "addcoupon" query if sale['coupon'] is set and not None.
            * zero or a multiple of "paystorecredit" queries if there are
              storecredit receipt items.
            * zero or a multiple of "redeemcoupon" queries if there are coupon
              receipt items.

        If there is a link to a consignment, that consignment should be closed
        in foxpro (see explanation in LinkSchema)

        A query is in the following form: ('querytype', [('key', value), ...])
        The function returns a list of these queries.
        """
        queries = []  # our container for all the queries.

        if cancel:
            queries.append(('cancelOrder', [*common, ('refid', resolve(sale, 'nr'))]))
            return serialize(queries)

        is_withdrawel = sale.get('withdrawelreason') or (
            sale['payments']['withdrawel'] != 0
            and sale['payments']['withdrawel'] == -sale['payments']['cash']
        )
        if is_withdrawel:
            sendorder = [
                *common,
                ('warehouse', resolve(sale, 'shop.id')),
                ('posid', resolve(sale, 'device_id')),
                ('cashier', resolve(sale, 'cashier.name')),
                ('refid', resolve(sale, 'nr')),
                ('withdrawel', cast_percentage(resolve(sale, 'payments.withdrawel'))),
                ('withdrawelreason', (resolve(sale, 'withdrawelreason'))),
            ]
            if sale.get('withdrawelreason') == 'eos':
                sendorder.append(('cash', 0))
            else:
                cash = cast_percentage(resolve(sale, 'payments.cash'))
                if cash != 0:
                    sendorder.append(('cash', cash))

            queries.append(('sendorder', sendorder))
        else:
            # clean up remark if it's not None
            remark = resolve(sale, 'remark')
            if remark is not None:
                remark = remark.replace('&', '')
            try:
                discountreason = resolve(sale, 'discountreason.key')
            except AttributeError:
                discountreason = resolve(sale, 'discountreason')

            sendorder = [
                *common,
                ('warehouse', resolve(sale, 'shop.id')),
                ('refid', resolve(sale, 'nr')),
                ('remarks', remark),
                ('discountreason', discountreason),
                ('cashier', resolve(sale, 'cashier.name')),
                ('uuid', resolve(sale, 'customer.id')),
                ('change', cast_percentage(resolve(sale, 'change'))),
                ('difference', cast_percentage(resolve(sale, 'difference'))),
                (
                    'couponDiscount',
                    sum(
                        i['value']
                        for i in sale['receipt']
                        if i['category'] == 'coupon' and i['type'] in ['C', ' ']
                    ),
                ),
            ]

            # value of below fields must be != 0 in order to be added to fp
            # senderorder query to prevent screwing up foxpro tables
            for key, value in [
                ('cash', resolve(sale, 'payments.cash')),
                ('creditcard', resolve(sale, 'payments.creditcard')),
                ('withdrawel', resolve(sale, 'payments.withdrawel')),
                ('consignment', resolve(sale, 'payments.consignment')),
                ('webshop', resolve(sale, 'payments.webshop')),
                (
                    'storecredit',
                    sale['payments']['storecredit'] - sale['totalStoreCreditPaid'],
                ),
            ]:
                if value != 0:
                    sendorder.append((key, cast_percentage(value)))
            # Do not add yet, used coupons might need to be added:
            creditreceipt = resolve(sale, 'payments.creditreceipt')

            pin = resolve(sale, 'payments.pin')
            if pin:  # should be more than 0
                sendorder.append(('pin', cast_percentage(pin)))
                if sale.get('cardProvider'):
                    sendorder.append((sale['cardProvider'], cast_percentage(pin)))

            # storecreditused has a strange boolean type field 'true' or None.
            if sale['payments']['storecredit'] - sale['totalStoreCreditPaid'] == 0:
                storecreditused = 'true'
            else:
                storecreditused = None
            sendorder.append(('storecreditused', storecreditused))

            # The following data is calculated from the receipt items.
            coupons = defaultdict(float)
            scpaid = 0
            barcodes = []
            redeem_queries = []
            for item in sale['receipt']:
                if item['category'] == 'coupon':
                    if item['type'] in (' ', 'C'):
                        price_key = 'value'
                    else:
                        price_key = 'price'
                    # couponout, couponin and creditreceipts are sums. But they
                    # should only be added if they are a non 0 value.
                    amount = item[price_key] * item['qty']
                    if amount != 0:
                        if item['type'] == 'U':
                            coupons['couponin'] += amount
                        elif item['type'] == 'I':
                            coupons['couponout'] += amount
                        elif item['type'] == 'T':
                            creditreceipt += amount

                    coupon_nr = item.get('couponNr')
                    if coupon_nr and coupon_nr != 'tegoedbon':
                        redeem = [
                            *common,
                            ('warehouse', resolve(sale, 'shop.id')),
                            ('refid', resolve(sale, 'nr')),
                            ('uuid', resolve(sale, 'customer.id')),
                            ('couponid', resolve(item, 'couponNr')),
                        ]
                        redeem.append(
                            ('value', cast_percentage(resolve(item, price_key)))
                        )
                        # Append a redeemcoupon query
                        redeem_queries.append(('redeemcoupon', redeem))

                elif item['category'] == 'storecredit':
                    scpaid += item['price'] * item['qty']

                    # Append a paystore credit query.
                    queries.append(
                        (
                            'paystorecredit',
                            [
                                *common,
                                ('uuid', resolve(sale, 'customer.id')),
                                ('value', round(item['price'], 2)),
                            ],
                        )
                    )

                elif item['category'] == 'barcode':
                    price = item['price'] * (
                        1 - SaleSchema.calculate_total_discount(sale)
                    )
                    barcode = resolve(item, 'barcode')
                    if 'reason' in item:
                        try:
                            reason = resolve(item, 'reason.key')
                        except AttributeError:
                            reason = resolve(item, 'reason')
                        barcode += ':' + reason

                    barcodes.extend(
                        [
                            ('barcode', barcode),
                            ('qty', item['qty']),
                            ('price', cast_percentage(price)),
                        ]
                    )

            sendorder.append(('scpaid', cast_percentage(scpaid)))
            # extend sendorder with coupon key value pairs.
            sendorder.extend(
                [(key, cast_percentage(value)) for key, value in coupons.items()]
            )
            if creditreceipt != 0:
                sendorder.append(('creditreceipt', cast_percentage(creditreceipt)))
            # close linked consignment
            if sale.get('link', {}).get('type') == 'consignment':
                sendorder.append(('cancelcons', resolve(sale, 'link.comment')))
            # barcodes are be added at the end in the original order.
            sendorder.extend(barcodes)
            # Append the sendorder query
            queries.append(('sendorder', sendorder))
            # Append the redeem_queries (they refer to the refid of the sendorder, so
            # should be sent after the sendorder):
            queries.extend(redeem_queries)

            if sale.get('coupon'):
                for coupon in sale['coupon']:
                    coupon_type = resolve(coupon, 'type')
                    if coupon_type in ('C', 'T'):
                        uuid_ = resolve(sale, 'customer.id')
                    else:
                        uuid_ = ''

                    # Append the addcoupon query
                    queries.append(
                        (
                            'addcoupon',
                            [
                                *common,
                                ('coupontype', coupon_type),
                                ('couponid', resolve(coupon, 'id')),
                                ('uuid', uuid_),
                                ('value', cast_percentage(resolve(coupon, 'value'))),
                            ],
                        )
                    )

        return serialize(queries)

    @staticmethod
    def get_next_receiptnr(db, tenant_id, transaction_type=2):
        query = {
            'tenant_id': tenant_id,
            'type': transaction_type,
            '$or': [{'receiptNr': {'$type': 'int'}}, {'receiptNr': {'$type': 'long'}}],
        }
        result = db.transactions.find_one(
            query, {'receiptNr': 1}, sort=[('receiptNr', -1)]
        )
        if result is not None:
            next_nr = result['receiptNr'] + 1
        else:
            next_nr = 1
        return next_nr

    @classmethod
    def prepare_for_pdf(cls, sale):
        """Calculate all the values needed for the receipt pdf"""
        # New transactions all have coupon as a list, but to be able to make pdf's of
        # older transactions:
        if sale.get('coupon') and not isinstance(sale['coupon'], list):
            sale['coupon'] = [sale['coupon']]
        cls.calculate_vat_gross_totals(sale)
        cls.calculate_total_paid(sale)
        cls.calculate_totals_and_discounts(sale)
        return sale

    @staticmethod
    def calculate_vat_gross_totals(sale):
        """
        Calculate the gross total (the value the vat needs to be paid over) for each
        type of VAT.
        """
        for key in ('high', 'low', 'zero'):
            if key + 'total' in sale.get('vat', []) and key + 'amount' in sale.get(
                'vat', []
            ):
                sale['vat'][key + '_gross_total'] = (
                    sale['vat'][key + 'total'] - sale['vat'][key + 'amount']
                )

    @staticmethod
    def calculate_total_paid(sale):
        """Calculate the total as it should be shown on the receipt"""
        # NOTE totalPaid is calculated twice in different ways!
        # On the frontend totalDiscountCoupon is also substracted, but that is part
        # of totalDiscount (SPAPI-579):
        sale['totalPaid'] = (
            sale['totalAmount']
            # discounts provided by the client
            - sale.get('totalDiscountCoupon', 0)
            - sale.get('overallReceiptDiscount', 0)
            # A/U/T/I coupons. Currently not used by webshops but could
            # change in the future.
            - sale.get('totalCoupon', 0)
        )

    @classmethod
    def calculate_totals_and_discounts(cls, sale):
        """
        Calculate the discounts. The total receipt discount gets spread out over the
        items. Total_line_discount is the total of all the discounts on articles, so
        not counting the total receipt discount.
        """
        cls.calculate_top_level_discounts(sale)
        cls.calculate_receipt_discounts_and_totals(sale)
        cls.fix_rounding_discrepancy(sale)

        for key in sale.copy():
            if '_temp_' in key:
                sale.pop(key)

    @staticmethod
    def calculate_top_level_discounts(sale):
        """
        Calculate the display_discount, total_line_discount and discount factor, the
        last two which are needed for further calculations.
        """
        total_line_discount = 0
        discountable_amount = 0
        for item in sale['receipt']:
            if item['category'] == 'barcode':
                discountable_amount += item['price'] * item['qty']
                total_line_discount += item['qty'] * (item['nettPrice'] - item['price'])

        # The calculation on the frontend is:
        # total_line_discount + sale['totalDiscount'] + sale['totalDiscountCoupon']
        # but totalDiscount already includes the C and SPACE coupons. This is why we
        # need to set totalDiscountCoupon to 0 in calculate_totals (SPAPI-573)
        sale['display_discount'] = (
            total_line_discount
            + sale['totalDiscountCoupon']
            + sale['overallReceiptDiscount']
        )
        try:
            discount_factor = (
                sale['totalDiscountCoupon'] + sale['overallReceiptDiscount']
            ) / discountable_amount
        except ZeroDivisionError:
            discount_factor = 0
        sale['_temp_discount_factor'] = discount_factor

    @staticmethod
    def calculate_receipt_discounts_and_totals(sale):
        """
        Calculates the discount for each receipt item that should be shown on the
        receipt. It consists of both a possible discount on the item itself and a
        possible receipt discount that is spread over all items.

        Also calculates the total_rounded_discount, which is the total of all discounts
        *as shown on the receipt* (so rounded values). This value can be used to
        determine if there is a rounding discrepancy that needs to be taken care of.
        """
        total_rounded_discount = 0
        for item in sale.get('receipt', []):
            if item['category'] == 'barcode':
                item['discount'] = (
                    item['nettPrice']
                    - item['price']
                    + sale['_temp_discount_factor'] * item['price']
                )
                item['total'] = (item['nettPrice'] - item['discount']) * item['qty']
                total_rounded_discount += round(item['discount'] * item['qty'], 2)
            else:
                # storecredit and all coupons except SPACE and C:
                if item['type'] not in [' ', 'C']:
                    item['total'] = item['price'] * item['qty']
                if item['type'] in ['A', 'T', 'U']:
                    item['total'] *= -1
        sale['_temp_total_rounded_discount'] = total_rounded_discount

    @staticmethod
    def fix_rounding_discrepancy(sale):
        """
        Fix rounding discrepancy, if there is one, and if it is possible.
        Example: if there are two items of 10.00 (qty 1) and a receipt discount of 4.99
        is given, because of rounding, both items will show a discount of 2.50, and a
        line total of 7.50. This means both the total discount and the display total do
        not correspond to the totals at the bottom of the receipt. This function will
        fix the discount of the first item, by making it 2.49, and making the total
        7.51.
        If instead there is only one item of 10.00 on the receipt with qty 2, the
        discount will also show 2.50, but this cannot be fixed. Also in that case, the
        total shown for the line is correct, 15.01.
        """
        # Determine if there is a rounding discrepancy:
        discrepancy = round(
            sale['_temp_total_rounded_discount'] - sale['display_discount'], 2
        )

        # Depending on the discount and the number of items, this can be a couple of
        # cents. The only way this will result in something weird, is if the first item
        # is e.g. only 3 cents. This will then look weird, but it's not completely wrong
        if discrepancy:
            for item in sale['receipt']:
                # We can only do the fix if there's an item with qty 1:
                if item['category'] == 'barcode' and item['qty'] == 1:
                    item['discount'] -= discrepancy
                    item['total'] += discrepancy
                    break


class TransitWarehouse(Schema):
    transitWarehouse = fields.String(
        metadata={
            'description': 'The human readable name of the transitPeer. This field is '
            'used in the pos for printing the transit.',
            'external_description': 'The human readable name of the transitPeer.',
        }
    )
    transitPeer = fields.String(
        required=True,
        validate=validate_warehouse_id,
        metadata={
            'description': 'The id (numerical string between 33 and 254) of the peer '
            'warehouse of the transit'
        },
    )
    dir = fields.String(
        required=True,
        metadata={
            'description': 'Direction of the transit, from or to the transitPeer.'
        },
        validate=validate.OneOf(choices=['from', 'to'], error=BAD_CHOICE_MSG),
    )


class TransitSchema(SaleSchema):
    _id = ObjectIdField()
    type = fields.Constant(
        constant=TRANSIT_TYPE,
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'number',
                'format': 'integer',
                'default': TRANSIT_TYPE,
                'enum': [TRANSIT_TYPE],
                'description': 'An integer that corresponds to a specific type of '
                'transaction',
            }
        },
    )
    transit = Nested(TransitWarehouse, required=True)
    receipt = Nested(
        BarcodeItem, many=True, required=True, validate=validate.Length(min=1)
    )

    @pre_load
    def fill_in_transit_warehouse(self, data, **kwargs):
        if (
            'transitPeer' in data.get('transit', {})
            and 'transitWarehouse' not in data.get('transit', {})
            and 'tenant_id' in self.context
        ):
            warehouse = self.context['db'].warehouses.find_one(
                {
                    'tenant_id': self.context['tenant_id'],
                    'wh': data['transit']['transitPeer'],
                }
            )
            if warehouse:
                data['transit']['transitWarehouse'] = warehouse['name']
        return data

    @validates_schema
    def validate_shop_id_is_not_transit_peer(self, data, **kwargs):
        """shop.id and transit.transitPeer should be different"""
        if data['transit']['transitPeer'] == data['shop']['id']:
            raise ValidationError(
                'Transit.transitPeer should be the different from shop.id.'
            )

    class Meta(BaseSchema.Meta):
        exclude = (
            'receiptEmail',
            'device_id',
            'payments',
            'coupon',
            'customer',
            'link',
            'totalDiscount',
            'buffer_id',
            'printed',
            'shift',
            'remark',
            'discountreason',
            'withdrawelreason',
            'cardType',
            'vat',
            'pinInfo',
            'pinError',
            'loyaltyPoints',
        )

    @classmethod
    def prepare_for_pdf(cls, transit):
        transit['totalNumber'] = 0
        for item in transit['receipt']:
            transit['totalNumber'] += abs(item['qty'])
        return transit

    @staticmethod
    def generate_fpqueries(transit, *common):
        from_ = resolve(transit, 'shop.id')
        to = resolve(transit, 'transit.transitPeer')

        # flip direction
        if transit['transit']['dir'] == 'from':
            from_, to = to, from_

        query = [
            *common,
            ('from', from_),
            ('to', to),
            ('refid', resolve(transit, 'nr')),
        ]
        barcodes = ','.join(
            [
                '%s:%s' % (resolve(i, 'barcode'), resolve(i, 'qty'))
                for i in transit['receipt']
            ]
        )
        query.append(('barcodes', barcodes))
        return serialize([('sendxtransit', query)])

    @post_load
    def postprocess(self, data, **kwargs):
        if (
            not data.get('receiptNr')
            and 'db' in self.context
            and 'tenant_id' in self.context
        ):
            data['receiptNr'] = self.get_next_receiptnr(
                self.context['db'],
                self.context['tenant_id'],
                transaction_type=data['type'],
            )
        return data


class ConsignmentCustomerSchema(CustomerSchema):
    """for a consignment, the id of the customer is required"""

    id = fields.String(required=True)
    custnum = fields.String()


class ConsignmentSchema(SaleSchema):
    """Schema or Consignment transactions"""

    type = fields.Constant(
        constant=CONSIGNMENT_TYPE,
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'number',
                'format': 'integer',
                'default': CONSIGNMENT_TYPE,
                'enum': [CONSIGNMENT_TYPE],
                'description': 'An integer that corresponds to a specific type of '
                'transaction',
            }
        },
    )
    status = fields.String(
        load_default='open',
        validate=validate.OneOf(choices=['open', 'closed'], error=BAD_CHOICE_MSG),
    )
    customer = Nested(ConsignmentCustomerSchema, required=True)


# Constansts and schemas for external documentation:

BARCODE_FIELDS = (
    'qty',
    'price',
    'nettPrice',
    'vat',
    'barcode',
    'articleCode',
    'articleDescription',
    'group',
    'brand',
    'color',
    'sizeLabel',
)


class ExternalSaleSchema(SaleSchema):
    """Schema used for generating external documentation"""

    payments = fields.Nested(PaymentSchema, only=('webshop',))
    receipt = fields.Nested(
        BarcodeItem,
        only=BARCODE_FIELDS,
        many=True,
        metadata={'description': 'The products to be sold on the sales transaction.'},
    )
    shop = fields.Nested(ShopSchema, only=('id',), required=True)
    cashier = fields.Nested(CashierSchema, only=('id',))
    customer = fields.Nested(CustomerSchema, only=('id',), allow_none=True)
    device_id = fields.String(
        load_default='WEBSH',
        validate=validate.Length(max=5),
        metadata={
            'description': 'Traditionally identified the POS device that created the '
            'sale.'
        },
    )

    class Meta:
        ordered = True
        fields = (
            'nr',
            'device_id',
            'totalDiscount',
            'overallReceiptDiscount',
            'payments',
            'receipt',
            # added so it can be removed without error when generating the docs:
            'tenant_id',
            'shop',
            'cashier',
            'customer',
            'remark',
            'created',
            'modified',
        )


class ExternalTransitSchema(TransitSchema):
    """Schema used for generating external documentation"""

    receipt = Nested(
        BarcodeItem,
        only=BARCODE_FIELDS,
        many=True,
        required=True,
        validate=validate.Length(min=1),
    )
    shop = fields.Nested(ShopSchema, only=('id',), required=True)

    class Meta:
        ordered = True
        fields = (
            'nr',
            'receipt',
            # added so it can be removed without error when generating the docs:
            'tenant_id',
            'shop',
            'cashier',
            'transit',
            'customer',
            'created',
            'modified',
        )
