import datetime
import uuid

from marshmallow import INCLUDE, fields, post_load, validate

from spynl_schemas.fields import Nested
from spynl_schemas.foxpro_serialize import fp_date, fp_datetime, resolve, serialize
from spynl_schemas.shared_schemas import BaseSchema, CashierSchema, Schema
from spynl_schemas.shared_schemas import ShopSchema as ShopSchema_
from spynl_schemas.utils import cast_percentage

PAYMENT_METHODS = {
    'cash': {'turnover': '+', 'type': 'cash'},
    'change': {'turnover': '-', 'type': 'cash'},
    'consignment': {'turnover': 'null', 'type': 'other'},
    'creditcard': {'turnover': '+', 'type': 'electronic'},
    'creditreceipt': {'turnover': '+', 'type': 'other'},
    'creditreceiptin': {'turnover': '+', 'type': 'other'},
    'couponin': {'turnover': '+', 'type': 'other'},
    'couponout': {'turnover': '+', 'type': 'other'},
    'deposit': {'turnover': '-', 'type': 'cash'},
    'pin': {'turnover': '+', 'type': 'electronic'},
    'storecredit': {'turnover': '+', 'type': 'other'},
    'storecreditin': {'turnover': '-', 'type': 'other'},
    'withdrawel': {'turnover': '+', 'type': 'cash'},
}


# we don't care about populating extra values here
class ShopSchema(ShopSchema_):
    @post_load
    def populate_values(self, data, **kwargs):
        return data


class VATSchema(Schema):
    zeroAmount = fields.Float(
        load_default=0, metadata={'description': 'The zero VAT amount.'}
    )
    lowAmount = fields.Float(
        load_default=0, metadata={'description': 'The low VAT amount.'}
    )
    highAmount = fields.Float(
        load_default=0, metadata={'description': 'The high VAT amount.'}
    )


class DeviceSchema(Schema):
    id = fields.String(
        required=True,
        metadata={'description': 'This is the unique id of the POS device.'},
    )
    name = fields.String(
        load_default='',
        metadata={'description': 'This is the name given to the POS device.'},
    )


class CashInDrawerSchema(Schema):
    qty = fields.Integer(
        load_default=0, metadata={'description': 'The number of coins or bills.'}
    )
    value = fields.Float(
        load_default=0,
        metadata={
            'description': 'The value of the coin or the bill. Example 20 cents would'
            ' be a value of .2'
        },
    )


class PaymentSchema(Schema):
    cash = fields.Float(
        load_default=0,
        metadata={
            'description': 'The amount of physical bills and coin currency accepted.'
        },
    )
    change = fields.Float(
        load_default=0, metadata={'description': 'The amount of change given.'}
    )
    consignment = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of payments as consignment accepted.'},
    )
    couponin = fields.Float(
        load_default=0, metadata={'description': 'The amount of coupons redeemed.'}
    )
    couponout = fields.Float(
        load_default=0, metadata={'description': 'The amount of coupons given out.'}
    )
    creditcard = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of payments by credit card accepted.'},
    )
    creditreceipt = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of credit receipts given out.'},
    )
    creditreceiptin = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of payments by credit receipt accepted.'},
    )
    deposit = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of money deposited into the cash drawer.'},
    )
    pin = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of payments by PIN accepted.'},
    )
    storecredit = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of payments by credit credit accepted.'},
    )
    storecreditin = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of store credit accounts payables made.'},
    )
    withdrawel = fields.Float(
        load_default=0,
        metadata={'description': 'The amount of money withdrawn from the cash drawer.'},
    )

    class Meta(Schema.Meta):
        unknown = INCLUDE


class EOSSchema(BaseSchema):
    """The End of Shift Document."""

    _id = fields.String(
        load_default=lambda: str(uuid.uuid4()),
        metadata={'description': 'The primary key of the document.'},
    )
    shop = Nested(
        ShopSchema,
        only=['id', 'name'],
        required=True,
        metadata={'description': 'The location processing the EOS document.'},
    )
    cashier = Nested(
        CashierSchema,
        required=True,
        metadata={'description': 'The cashier finalising the EOS document.'},
    )
    device = Nested(
        DeviceSchema,
        required=True,
        metadata={'description': 'The POS where the EOS is being processed.'},
    )
    difference = fields.Float(
        load_default=0,
        metadata={
            'description': 'The amount in cash which does not match what was '
            'collected during the shift.'
        },
    )
    cashInDrawer = Nested(
        CashInDrawerSchema,
        many=True,
        load_default=list,
        metadata={'description': 'The physical cash in the cash drawer.'},
    )
    original = Nested(
        PaymentSchema,
        load_default=dict,
        metadata={
            'description': 'The original amounts before potentially being altered '
            'by the cashier during the EOS process.'
        },
    )
    final = Nested(
        PaymentSchema,
        load_default=dict,
        metadata={
            'description': 'The final amounts after potentially being altered by the '
            'cashier during the EOS process.'
        },
    )
    totalCashInDrawer = fields.Float(
        load_default=0,
        metadata={
            'description': 'Total amount of the physical cash in the cash drawer.'
        },
    )
    expectedCashInDrawer = fields.Float(
        load_default=0,
        metadata={
            'description': 'The cash that should be in the drawer at the end of the '
            'shift if no irregularities occured.'
        },
    )
    deposit = fields.Float(
        load_default=0,
        metadata={
            'description': 'The amount of physical cash being deposited into the bank.'
        },
    )
    endBalance = fields.Float(
        load_default=0,
        metadata={
            'description': 'The final balance of physical cash in the cash drawer at '
            'the end of the shift minus the deposit. This will become the '
            'openingBalance of the next shift.'
        },
    )
    openingBalance = fields.Float(
        load_default=0,
        metadata={
            'description': 'The opening balance of physical cash in the cash drawer at '
            'the beginning of the shift.'
        },
    )
    periodStart = fields.DateTime(
        metadata={'description': 'The date and time when the shift begins.'}
    )
    periodEnd = fields.DateTime(
        metadata={'description': 'The date and time when the shift ends.'}
    )
    edited = fields.Boolean(
        load_default=False,
        metadata={
            'description': 'If the shift document has been edited by the cashier.'
        },
    )
    cycleID = fields.String(
        load_default=lambda: str(uuid.uuid4()),
        metadata={
            'description': 'The unique identifier generated at the beginning of each'
            ' shift. Every transaction made during this shift will have this cyleID '
            'stored on the shift field.'
        },
    )
    status = fields.String(
        validate=validate.OneOf(['generated', 'completed', 'rectification']),
        load_default='generated',
        metadata={
            'description': 'An enum field of either generated or completed. The '
            'generated status means the document has been generated but has not yet '
            'been closed. A "rectification" document corrects a monetary imbalance.'
        },
    )
    remarks = fields.String(
        load_default='', metadata={'description': 'A free text remarks field.'}
    )
    turnover = fields.Float(
        load_default=0,
        metadata={'description': 'The amount in turnover made during the shift.'},
    )
    vat = fields.Nested(
        VATSchema,
        load_default=dict,
        metadata={
            'description': 'The amount of VAT collected during a particular shift.'
        },
    )

    def get_vat_totals(self, data):
        if 'db' in self.context:
            pipeline = [
                {
                    '$match': {
                        'tenant_id': self.context['tenant_id'],
                        'shift': data['cycleID'],
                        'type': 2,
                    }
                },
                {
                    '$group': {
                        '_id': None,
                        'zeroAmount': {'$sum': '$vat.zeroamount'},
                        'lowAmount': {'$sum': '$vat.lowamount'},
                        'highAmount': {'$sum': '$vat.highamount'},
                    }
                },
                {'$project': {'_id': 0}},
            ]
            try:
                return next(self.context['db'].transactions.aggregate(pipeline))
            except StopIteration:
                pass

    @staticmethod
    def calculate_turnover(data, type_=None):
        if isinstance(type_, str):
            type_ = [type_]

        turnover = 0
        for payment, value in data['final'].items():
            if payment in PAYMENT_METHODS and (
                type_ is None or PAYMENT_METHODS[payment]['type'] in type_
            ):
                if PAYMENT_METHODS[payment]['turnover'] == '+':
                    turnover += value
                elif PAYMENT_METHODS[payment]['turnover'] == '-':
                    turnover -= value

        turnover = round(turnover, 2)

        return turnover

    @staticmethod
    def calculate_difference(data):
        """
        Calculates the difference, which is the amount of money unaccounted for,
        by adding up the differences between original and final payments and
        the cash deficit (difference ). NB1: the seteod event contains a
        difference field that only contains cash difference. NB2: final.cash is always
        the same to original.cash, if it weren't then any difference there would be
        added twice because it would also appear in the difference between
        totalCashInDrawer and expectedCashInDrawer.
        """
        difference = 0
        for payment in data['final'].keys():
            if payment not in PAYMENT_METHODS:
                continue

            final = data['final'][payment]
            original = data['original'][payment]

            if PAYMENT_METHODS[payment]['turnover'] == '+':
                difference = difference + final - original

            elif PAYMENT_METHODS[payment]['turnover'] == '-':
                difference = difference - final + original

        if 'expectedCashInDrawer' in data and 'totalCashInDrawer' in data:
            difference = (
                difference + data['totalCashInDrawer'] - data['expectedCashInDrawer']
            )

        difference = round(difference, 2)

        return difference

    @post_load
    def postprocess(self, data, **kwargs):
        data.update(
            {
                'turnover': self.calculate_turnover(data),
                'difference': self.calculate_difference(data),
            }
        )
        if not data.get('periodStart'):
            data['periodStart'] = datetime.datetime.now(datetime.timezone.utc)

        if data['status'] == 'completed':
            data['vat'] = self.get_vat_totals(data) or data['vat']
            if not data.get('periodEnd'):
                data['periodEnd'] = datetime.datetime.now(datetime.timezone.utc)
        elif data['status'] == 'rectification':
            data['periodEnd'] = data['periodStart']
        return data

    @classmethod
    def prepare_for_pdf(cls, data):
        # if there are modfied values, originals will be printed and headers are needed:
        if data['final'] != data.get('original'):
            data['print_modified_headers'] = True

        data['final']['net_cash'] = data['final']['cash'] - data['final']['change']

        if data.get('cashInDrawer'):
            data['cashInDrawer'] = {
                item['value']: item['qty'] for item in data['cashInDrawer']
            }
        return data

    def generate_fpqueries(self, eos, *common):
        miscellaneous = self.calculate_turnover(eos, type_=['other', 'electronic'])
        query = [
            *common,
            ('warehouse', resolve(eos, 'shop.id')),
            ('posid', resolve(eos, 'device.id')),
            ('periodstart', fp_datetime(resolve(eos, 'periodStart'))),
            ('periodend', fp_datetime(resolve(eos, 'periodEnd'))),
            # Payments, store credit and coupons
            ('cash', cast_percentage(resolve(eos, 'final.cash'))),
            ('change', cast_percentage(resolve(eos, 'final.change'))),
            ('consignment', cast_percentage(resolve(eos, 'final.consignment'))),
            ('couponin', cast_percentage(resolve(eos, 'final.couponin'))),
            ('couponout', cast_percentage(resolve(eos, 'final.couponout'))),
            ('creditcard', cast_percentage(resolve(eos, 'final.creditcard'))),
            (
                'creditreceipt',
                cast_percentage(
                    resolve(eos, 'final.creditreceiptin')
                    + resolve(eos, 'final.creditreceipt')
                ),
            ),
            ('deposit', cast_percentage(resolve(eos, 'deposit'))),
            ('miscelaneous', cast_percentage(miscellaneous)),
            ('pin', cast_percentage(resolve(eos, 'final.pin'))),
            ('storecredit', cast_percentage(resolve(eos, 'final.storecredit'))),
            ('storedebit', cast_percentage(resolve(eos, 'final.storecreditin'))),
            (
                'withdrawel',
                cast_percentage(
                    resolve(eos, 'final.withdrawel') - resolve(eos, 'final.deposit')
                ),
            ),
            # Difference in seteod should contain cash difference only.
            (
                'difference',
                cast_percentage(
                    resolve(eos, 'totalCashInDrawer')
                    - resolve(eos, 'expectedCashInDrawer')
                ),
            ),
            # This is the correct (mis)spelling:
            ('openningbalance', cast_percentage(resolve(eos, 'openingBalance'))),
            ('closingbalance', cast_percentage(resolve(eos, 'endBalance'))),
            ('turnover', cast_percentage(resolve(eos, 'turnover'))),
        ]
        return serialize([('seteod', query)])

    def generate_reset_fpqueries(self, eos, *common):
        date = fp_date(eos['periodStart'])
        query = [*common, ('shopid', resolve(eos, 'shop.id')), ('date', date)]
        return serialize([('reseteod', query)])
