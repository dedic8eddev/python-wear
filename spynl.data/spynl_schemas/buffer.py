from marshmallow import fields, validate

from spynl_schemas.fields import Nested
from spynl_schemas.sale import BarcodeItem, PaymentSchema, SaleSchema

BUFFER_TYPE = 8

default_payments = dict(
    storecredit=0,
    pin=0,
    cash=0,
    creditcard=0,
    creditreceipt=0,
    couponin=0,
    withdrawel=0,
    consignment=0,
)


class BufferSchema(SaleSchema):
    """The buffer model"""

    # overridden fields
    receipt = Nested(BarcodeItem, required=True, many=True)
    # PaymentSchema has required fields, but a buffer is like a draft.
    # We don't actually need, or want any payment information.
    payments = Nested(PaymentSchema, load_default=lambda: default_payments)
    type = fields.Int(load_default=BUFFER_TYPE, validate=validate.Equal(BUFFER_TYPE))
    totalDiscount = fields.Float(load_default=0)
    nr = fields.String(load_default='')
    # This allows the UI to highlight the line that was highlighted
    # when creating the buffer.
    selectedLine = fields.Int(load_default=0)

    class Meta(SaleSchema.Meta):
        exclude = ('device_id',)

    @staticmethod
    def get_next_receiptnr(*args, **kwargs):
        # Buffers don't have a receiptNr but the POS expects something filled
        # in.
        return 0
