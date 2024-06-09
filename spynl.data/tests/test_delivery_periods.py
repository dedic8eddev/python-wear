import datetime

import pytest
from marshmallow import ValidationError

from spynl_schemas import DeliveryPeriodSchema


def test_duplicate_label_delivery_period(database):
    schema = DeliveryPeriodSchema(context={'tenant_id': '1', 'db': database})
    period = {
        'fixDate': str(datetime.datetime.utcnow()),
        'reservationDate': str(datetime.datetime.utcnow()),
        'label': 'default',
    }
    loaded_period = schema.load(period)
    database.delivery_periods.insert_one(loaded_period)
    with pytest.raises(ValidationError):
        schema.load(period)


def test_duplicate_label_delivery_period_other_tenant(database):
    schema = DeliveryPeriodSchema(context={'tenant_id': '1', 'db': database})
    period = {
        'fixDate': str(datetime.datetime.utcnow()),
        'reservationDate': str(datetime.datetime.utcnow()),
        'label': 'default',
    }
    loaded_period = schema.load(period)
    database.delivery_periods.insert_one(loaded_period)
    try:
        schema = DeliveryPeriodSchema(context={'tenant_id': '2', 'db': database})
        schema.load(period)
    except ValidationError:
        pytest.fail('should not raise validationerror')
