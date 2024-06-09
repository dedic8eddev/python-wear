import uuid

from marshmallow import ValidationError, fields, validates_schema

from spynl_schemas.fields import LabelField, LenientDateTimeField
from spynl_schemas.shared_schemas import BaseSchema


class DeliveryPeriodSchema(BaseSchema):
    _id = fields.UUID(load_default=uuid.uuid4)
    label = LabelField(
        required=True, metadata={'description': 'The delivery period label'}
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

    @validates_schema
    def validate_label(self, data, **kwargs):
        db = self.context['db']
        if db.delivery_periods.count_documents(
            {
                'label': data['label'],
                'tenant_id': data['tenant_id'],
                '_id': {'$ne': data['_id']},
            }
        ):
            raise ValidationError('Label is not unique for this tenant', 'label')
