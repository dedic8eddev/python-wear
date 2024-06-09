import pytest
from bson.objectid import ObjectId
from marshmallow import ValidationError

from spynl_schemas import Warehouse

WAREHOUSE = {
    'wh': '51',
    'name': 'some warehouse',
    'gln': '123456789',
    'email': None,
    'active': True,
    'addresses': [
        {'primary': True, 'street': 'blastreet', 'houseno': '1', 'zipcode': '1234 AB'}
    ],
}


def test_warehouse_wh_uniqueness(database):
    warehouse = {'wh': '51', 'tenant_id': ['tenant_1']}
    warehouse_id = database.warehouses.insert_one(warehouse.copy())
    schema = Warehouse(
        context={'db': database, 'tenant_id': 'tenant_1'}, only=('_id', 'wh')
    )
    with pytest.raises(
        ValidationError, match='This wh number already exists for this tenant'
    ):
        schema.load(warehouse)
    # no error:
    data = schema.load({'_id': str(warehouse_id.inserted_id), **warehouse})
    assert isinstance(data['_id'], ObjectId)


def test_adding_new_string_id(database):
    schema = Warehouse(
        context={'db': database, 'tenant_id': 'tenant_1'}, only=('_id', 'wh')
    )
    with pytest.raises(ValidationError, match='Not a valid ObjectId'):
        schema.load({'_id': 'A string', 'wh': '51'})


def test_using_string_id(database):
    warehouse = {'_id': 'A string', 'wh': '51', 'tenant_id': ['tenant_1']}
    database.warehouses.insert_one(warehouse.copy())
    schema = Warehouse(
        context={'db': database, 'tenant_id': 'tenant_1'}, only=('_id', 'wh')
    )
    # no error:
    schema.load({'_id': 'A string', 'wh': '51'})


def test_email_validation(database):
    # If email is empty string it should be removed
    warehouse = {'wh': '52', 'tenant_id': ['tenant_1'], 'email': 'blah'}
    warehouse_id = database.warehouses.insert_one(warehouse.copy())
    schema = Warehouse(
        context={'db': database, 'tenant_id': 'tenant_1'}, only=('_id', 'wh', 'email')
    )

    with pytest.raises(ValidationError, match='Not a valid email address.'):
        schema.load({'_id': str(warehouse_id.inserted_id), **warehouse})


def test_fpquery():
    expected = [
        (
            'setwarehouse',
            'setwarehouse/locationid__51/name__some%20warehouse/inactive__false/'
            'street__blastreet/housenum__1/zipcode__1234%20AB',
        )
    ]
    assert expected == Warehouse().generate_fpqueries(WAREHOUSE)
