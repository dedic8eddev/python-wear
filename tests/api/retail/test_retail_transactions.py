import uuid

import pymongo
import pytest
from bson import ObjectId

from spynl.api.auth.testutils import login, mkuser
from spynl.api.retail.retail_transactions import FIELDS, TransactionGetSchema

TENANT_ID = '1'
CUSTOMER_ID_1 = uuid.uuid4()
CUSTOMER_ID_2 = uuid.uuid4()


@pytest.fixture(autouse=True)
def setup(spynl_data_db, app):
    spynl_data_db.tenants.insert_one(
        {'_id': '1', 'applications': ['pos'], 'settings': {}}
    )
    mkuser(
        spynl_data_db.pymongo_db,
        'username',
        'password',
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'pos-device'},
    )

    transactions = [
        {
            'shop': {'id': '50'},
            'type': 3,
            'transit': {'transitPeer': '51'},
            'tenant_id': [TENANT_ID],
            'active': True,
            'customer': {'id': str(CUSTOMER_ID_1)},
        },
        {'shop': {'id': '50'}, 'type': 2, 'tenant_id': [TENANT_ID], 'active': True},
        {
            'shop': {'id': '50'},
            'type': 2,
            'tenant_id': [TENANT_ID],
            'active': True,
            'fiscal_receipt_nr': '123',
        },
        {
            'shop': {'id': '51'},
            'type': 3,
            'transit': {'transitPeer': '50'},
            'tenant_id': [TENANT_ID],
            'active': True,
            'customer': {'id': str(CUSTOMER_ID_2)},
            'fiscal_receipt_nr': '123',
        },
        {
            'shop': {'id': '52'},
            'type': 2,
            'tenant_id': [TENANT_ID],
            'active': True,
            'customer': {'id': str(CUSTOMER_ID_1)},
        },
    ]

    spynl_data_db.transactions.insert_many(transactions)
    spynl_data_db.transactions.pymongo_create_index([('shop.id', pymongo.ASCENDING)])
    spynl_data_db.transactions.pymongo_create_index(
        [('customer.id', pymongo.ASCENDING)]
    )
    yield


@pytest.mark.parametrize(
    'filtr,count',
    [
        ({'type': 2, 'warehouseId': '50'}, 2),
        ({'type': 2, 'warehouseId': '50', 'fiscal_receipt_nr': None}, 1),
        ({'type': 2, 'warehouseId': '50', 'fiscal_receipt_nr': '123'}, 1),
        ({'warehouseId': '50'}, 3),
        ({'warehouseId': '51'}, 1),
        ({'type': 3, 'warehouseId': '50'}, 2),
        ({'customerId': str(CUSTOMER_ID_1)}, 2),
        ({'customerId': str(CUSTOMER_ID_1), 'warehouseId': '50'}, 1),
    ],
)
def test_filter(app, filtr, count):
    login(app, 'username', 'password')
    payload = {'filter': filtr}
    response = app.post_json('/retail-transactions/get', payload, status=200)
    assert len(response.json['data']) == count


@pytest.mark.parametrize(
    'input,expected',
    [
        ({}, FIELDS),
        ({'filter': {'nr': '1'}}, {'modified_history': 0}),
        ({'filter': {'_id': ObjectId()}}, {'modified_history': 0}),
        ({'fields': ['a', 'b']}, ['a', 'b']),
    ],
)
def test_projection_defaulting(input, expected):
    context = {'tenant_id': 'lorem'}
    data = TransactionGetSchema(context=context).load(input)
    assert data['projection'] == expected
