"""
Test the callbacks. Tests going through the app can be found in test_mongo_access
"""

from functools import partial

import bson
import pytest

from spynl.api.auth.testutils import mkuser
from spynl.api.mongo.plugger import (
    aggregate_callback,
    find_callback,
    save_callback,
    timestamp_callback,
)


@pytest.fixture
def set_db(spynl_data_db):
    db = spynl_data_db
    db.tenants.insert_one(
        {
            '_id': 'tenant1',
            'name': 'Tenant 1',
            'active': True,
            'applications': ['pos'],
            'settings': {},
        }
    )
    mkuser(spynl_data_db, 'user', 'password', ['tenant1'], {'tenant1': ['pos-device']})


class Collection:
    def __init__(self, name):
        class C_:
            def __init__(self, name):
                self.name = name

        self.pymongo_collection = C_(name)


def test_saved_timestamp_user_properties(set_db, spynl_data_db, app):
    app.post_json('/login', {'username': 'user', 'password': 'password'}, status=200)
    r = app.post_json('/sales/add', {'data': example_sale}, status=200)
    sale = spynl_data_db.transactions.find_one(
        {'_id': bson.ObjectId(r.json['data'][0])}
    )
    assert list(sale['created']['user'].keys()) == ['_id', 'username']


@pytest.mark.parametrize(
    'tenant_id,current_tenant_id,filter,collection,result',
    [
        ('1', '1', {'a': 'b'}, Collection('tenants'), {'a': 'b', '_id': '1'}),
        ('1', '1', {'a': 'b'}, Collection(''), {'a': 'b', 'tenant_id': '1'}),
        ('1', '1', None, Collection(''), {'tenant_id': '1'}),
        ('1', '1', None, Collection('col2'), {'tenant_id': '1'}),
        (
            '1',
            '1',
            {'tenant_id': '2', 'a': 'b'},
            Collection(''),
            {'a': 'b', 'tenant_id': '1'},
        ),
        (
            '2',
            'master',
            {'tenant_id': ['2'], 'a': 'b'},
            Collection(''),
            {'a': 'b', 'tenant_id': '2'},
        ),
        (
            '2',
            '1',
            {'tenant_id': ['3'], 'a': 'b'},
            Collection(''),
            {'a': 'b', 'tenant_id': '2'},
        ),
        (
            'master',
            'master',
            {'tenant_id': ['3'], 'a': 'b'},
            Collection(''),
            {'a': 'b', 'tenant_id': ['3']},
        ),
    ],
)
def test_find_callback(tenant_id, current_tenant_id, filter, collection, result):
    filter = find_callback(tenant_id, current_tenant_id, filter, collection)
    assert filter == result


@pytest.mark.parametrize(
    'tenant_id,data,collection,result',
    [
        ('1', {'a': 'b'}, Collection(''), {'a': 'b', 'tenant_id': ['1']}),
        ('1', {}, Collection(''), {'tenant_id': ['1']}),
        ('1', {}, Collection('col2'), {'tenant_id': ['1']}),
        ('1', {}, Collection('tokens'), {'tenant_id': '1'}),
        ('1', {}, Collection('tenants'), {}),
        (
            '1',
            {'tenant_id': '2', 'a': 'b'},
            Collection(''),
            {'a': 'b', 'tenant_id': ['1']},
        ),
    ],
)
def test_save_callback(tenant_id, data, collection, result):
    data = save_callback(tenant_id, data, collection)
    assert data == result


def test_timestamp_callback_modified(spynl_data_db):
    user = {'_id': 1, 'username': 'username'}
    data = {'_id': 1}

    # register for the "create" action
    spynl_data_db.timestamp_callback = partial(timestamp_callback, user, 'create')
    spynl_data_db.test.insert_one(data)

    assert data['created']['action'] == 'create'
    assert data['created']['user'] == user
    assert data['created'] == data['modified']
    assert [data['modified']] == data['modified_history']

    # register for the "update" action
    spynl_data_db.timestamp_callback = partial(timestamp_callback, user, 'update')
    spynl_data_db.test.update_one({'_id': data['_id']}, {'$set': {'key': 1}})

    data = spynl_data_db.test.find_one({'_id': data['_id']})
    assert data['created']['action'] == 'create'
    assert data['created']['user'] == user
    assert data['created'] != data['modified']
    assert data['modified']['action'] == 'update'
    assert len(data['modified_history']) == 2
    assert data['modified_history'][-1] == data['modified']

    data['key'] = 2

    # register for the "upsert" action
    spynl_data_db.timestamp_callback = partial(timestamp_callback, user, 'upsert')

    spynl_data_db.test.upsert_one({'_id': data['_id']}, data)
    data = spynl_data_db.test.find_one({'_id': data['_id']})
    assert data['created']['action'] == 'create'
    assert data['created'] != data['modified']
    assert data['modified']['action'] == 'upsert'
    assert len(data['modified_history']) == 3
    assert data['modified_history'][-1] == data['modified']


@pytest.mark.parametrize(
    'tenant_id,pipeline,collection,result',
    [
        ('1', None, Collection(''), [{'$match': {'tenant_id': '1'}}]),
        (
            '1',
            [{'$match': {'tenant_id': '2'}}],
            Collection(''),
            [{'$match': {'tenant_id': '1'}}],
        ),
        (
            '1',
            [{'$project': {'bla': 1}}],
            Collection(''),
            [{'$match': {'tenant_id': '1'}}, {'$project': {'bla': 1}}],
        ),
        (
            '1',
            [{'$project': {'bla': 1}}],
            Collection('tenants'),  # no special handling for tenants
            [{'$project': {'bla': 1}}],
        ),
        (
            '1',
            [
                {'$project': {'bla': 1}},
                {'$match': {'field': 'a'}},
                {},
                {'$match': {'tenant_id': '1'}},
            ],
            Collection(''),
            [
                {'$match': {'tenant_id': '1'}},
                {'$project': {'bla': 1}},
                {'$match': {'field': 'a'}},
                {},
                {'$match': {'tenant_id': '1'}},
            ],
        ),
    ],
)
def test_aggregate_callback(tenant_id, pipeline, collection, result):
    pipeline = aggregate_callback(tenant_id, pipeline, collection)
    assert pipeline == result


example_sale = {
    'shift': '1b2c2f189-486a-4cfc-a6f0-7daa364a0faf',
    'customer': None,
    'overallReceiptDiscount': 0.0,
    'type': 2,
    'nr': '50-12-19677',
    'device': '569bf0583209e90e021210aa',
    'device_id': '00000',
    'printed': '20-02-16 13:46',
    'cashier': {'id': 'mios.04@softwear.nu', 'name': 'Mylene', 'fullname': 'Mylene'},
    'loyaltyPoints': 0,
    'buffer_id': 'buffer_8cadb3da-d48a-43f4-9931-af66ab72cadc',
    'receiptNr': 19677.0,
    'receipt': [
        {
            'sizeLabel': 'ONE',
            'qty': 1,
            'rfid': None,
            'color': 'mult:multicolour',
            'category': 'barcode',
            'vat': 21.0,
            'group': None,
            'barcode': '000698032677',
            'articleCode': 'diversen',
            'articleDescription': 'diversen',
            'changeDisc': True,
            'nettPrice': 49.99,
            'price': 49.99,
        }
    ],
    'remark': '',
    'payments': {
        'cash': 0.0,
        'consignment': 0.0,
        'pin': 49.99,
        'withdrawel': 0.0,
        'storecredit': 0.0,
        'creditreceipt': 0.0,
        'couponin': 0.0,
        'creditcard': 0.0,
    },
    'shop': {
        'id': '50',
        'houseno': '',
        'zipcode': '2611 RJ',
        'street': 'Molslaan 35-39',
        'name': 'A-Keuze',
        'city': 'Delft',
        'phone': '015-2135004',
    },
    'totalAmount': 49.99,
    'totalStoreCreditPaid': 0.0,
    'totalNumber': 1.0,
    'totalPaid': 49.99,
    'totalCoupon': 0.0,
    'totalDiscountCoupon': 0.0,
    'vat': {
        'zerovalue': 0.0,
        'zerototal': 0.0,
        'zeroamount': 0.0,
        'lowvalue': 6.0,
        'lowtotal': 0.0,
        'lowamount': 0.0,
        'highvalue': 21.0,
        'hightotal': 49.99,
        'highamount': 8.68,
    },
    'difference': 0,
    'change': 0.0,
}
