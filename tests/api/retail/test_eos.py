"""Tests for eos endpoints."""

import uuid
from collections import namedtuple
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from marshmallow import Schema, ValidationError, fields
from pyramid.testing import DummyRequest

from spynl.main.exceptions import IllegalAction

from spynl.api.auth.testutils import mkuser
from spynl.api.retail.eos import (
    EOSOverviewSchema,
    _get_last_open,
    get,
    get_eos_overview,
    init,
    reset,
    save,
)
from spynl.api.retail.resources import EOS

Tenant = namedtuple('Tenant', 'id, user_ids, shops')
Shop = namedtuple('Shop', 'name, device_names')

TENANTS = [
    Tenant(
        '12345',
        [ObjectId(), ObjectId()],
        [Shop('Amsterdam', ['D1', 'D2']), Shop('Utrecht', ['D3', 'D4'])],
    ),
    Tenant('foo', [ObjectId()], [Shop('Breda', ['D1', 'D2', 'D3', 'D4'])]),
]


# reference for the keys that included in the result of the key 'totals' in endpoint's
# response
TOTAL_FIELDS = {
    'cash',
    'change',
    'couponin',
    'couponout',
    'creditreceiptin',
    'creditcard',
    'deposit',
    'pin',
    'consignment',
    'storecredit',
    'storecreditin',
    'withdrawel',
    'creditreceipt',
    'difference',
    'endBalance',
    'openingBalance',
    'turnover',
}

TENANT_ID = '12345'
TENANT_ID_2 = '54321'


@pytest.fixture(scope='function')
def database_setup(app, db, monkeypatch):

    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['pos'], 'settings': {}})
    db.tenants.insert_one({'_id': TENANT_ID_2, 'applications': ['pos'], 'settings': {}})
    db.warehouses.insert_one({'tenant_id': [TENANT_ID], 'wh': '50', 'active': True})

    mkuser(db, 'user', 'password', [TENANT_ID], tenant_roles={TENANT_ID: 'pos-device'})
    mkuser(
        db, 'user2', 'password', [TENANT_ID_2], tenant_roles={TENANT_ID_2: 'pos-device'}
    )

    app.get('/login?username=%s&password=%s' % ('user', 'password'))
    yield db
    app.get('/logout')


def make_relative_dates(*nums):
    """Return datetimes relative to today(start of day)."""
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return [today + timedelta(days=num) for num in nums]


def eos_doc_factory(num, user_id, tenant_id, shop, device_name, status='generated'):
    """Return a new eos document with sample eos data."""
    # assign to all number fields the same value for easier testing
    period_start = make_relative_dates(-num)[0]
    period_end = period_start + timedelta(hours=5)
    return {
        'created': {'date': period_end, 'user': {'_id': user_id}},
        # periodStart is earlier than when the document is created/saved
        'periodStart': period_start,
        'periodEnd': period_end,
        'tenant_id': [tenant_id],
        'device': {'name': device_name, 'id': device_name},
        'shop': {'name': shop.name, 'id': '51'},
        'cashier': {'fullname': 'John', 'id': '1'},
        'status': status,
        'cycleID': '1',
        'deposit': num,
        'difference': num,
        'endBalance': num,
        'openingBalance': num,
        'turnover': num,
        'final': {
            'cash': num,
            'change': num,
            'couponin': num,
            'couponout': num,
            'creditreceiptin': num,
            'creditcard': num,
            'consignment': num,
            'storecredit': num,
            'storecreditin': num,
            'withdrawel': num,
            'creditreceipt': num,
            'pin': num,
        },
        'active': True,
    }


@pytest.fixture
def request_(spynl_data_db):
    """Prepare and return a dummy request for spynl needs."""

    class SpynlDummyRequest(DummyRequest):
        def __init__(self, *args, **kwargs):
            kwargs['requested_tenant_id'] = TENANTS[0].id
            kwargs.setdefault('json_body', {})
            kwargs.setdefault('args', kwargs['json_body'])
            super().__init__(*args, **kwargs)

        @property
        def json_payload(self):
            return self.json_body

    SpynlDummyRequest.db = spynl_data_db
    SpynlDummyRequest.session_or_token_id = '123456'
    return SpynlDummyRequest


def test_save_uses_new_endpoint(database_setup, app):
    """old endpoint would not fail when sending in wrong data"""
    payload = {'data': {'some': 'data'}}
    app.post_json('/eos/save', payload, status=400)


@pytest.mark.parametrize('status', ['completed', 'rectification'])
def test_payment_totals(spynl_data_db, request_, status):
    """test o1 c c o2 o3 returns o2"""
    eos_docs = []
    period_starts = []
    for days in range(1, 5):
        period_start = make_relative_dates(-days)[0]
        period_starts.append(period_start)
        eos_docs.append(
            {
                'tenant_id': '12345',
                'device': {'id': 'D1'},
                'cycleID': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'periodStart': period_start,
                'periodEnd': period_start + timedelta(hours=5),
                'status': 'generated',
                'active': True,
            }
        )
    eos_docs[2].update({'status': status, 'endBalance': 1})
    eos_docs.append(eos_docs[3].copy())
    eos_docs[4].update({'active': False})
    spynl_data_db.eos.insert_many(eos_docs)

    spynl_data_db.transactions.insert_many(
        [
            {
                'type': 2,
                'active': True,
                'payments': {
                    'cash': 5,
                    'consignment': 5,
                    'creditcard': 5,
                    'creditreceipt': 5,
                    'pin': 5,
                    'storecredit': 5,
                    'withdrawel': 5,
                },
                'receipt': [
                    {'type': 'T', 'price': 5},
                    {'type': 'T', 'price': 10},
                    {'type': 'I', 'price': 5},
                    {'type': 'U', 'price': 5},
                    {'type': 'O', 'price': 5},
                ],
                'change': 5,
                'tenant_id': ['12345'],
                'shift': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'device': 'D1',
            },
            {
                'type': 2,
                'active': True,
                'payments': {
                    'cash': 5,
                    'consignment': 5,
                    'creditcard': 5,
                    'creditreceipt': 5,
                    'pin': 5,
                    'storecredit': 5,
                    'withdrawel': 5,
                },
                'receipt': [
                    {'type': 'T', 'price': 6},
                    {'type': 'T', 'price': 11},
                    {'type': 'I', 'price': 6},
                    {'type': 'U', 'price': 6},
                    {'type': 'O', 'price': 6},
                ],
                'change': 5,
                'tenant_id': ['12345'],
                'shift': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'device': 'D1',
            },
            {
                'type': 9,
                'active': True,
                'payments': {
                    'cash': 7,
                    'consignment': 7,
                    'creditcard': 7,
                    'creditreceipt': 7,
                    'pin': 7,
                    'storecredit': 7,
                    'withdrawel': -5,
                },
                'change': 7,
                'tenant_id': ['12345'],
                'shift': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'device': 'D1',
            },
            {
                'type': 9,
                'payments': {
                    'cash': 5,
                    'consignment': 5,
                    'creditcard': 5,
                    'creditreceipt': 5,
                    'pin': 5,
                    'storecredit': 5,
                    'withdrawel': 5,
                },
                'change': 5,
                'tenant_id': ['12345'],
                'shift': '2',
                'device': 'D1',
            },
            {
                'type': 9,
                'active': True,
                'payments': {
                    'cash': 7,
                    'consignment': 7,
                    'creditcard': 7,
                    'creditreceipt': 7,
                    'pin': 7,
                    'storecredit': 7,
                    'withdrawel': -5,
                },
                'change': 7,
                'tenant_id': ['12345'],
                'shift': '2',
                'device': 'D2',
            },
            {
                'receipt': [
                    {'type': 'T', 'price': 6},
                    {'type': 'T', 'price': 11},
                    {'type': 'I', 'price': 6},
                    {'type': 'U', 'price': 6},
                    {'type': 'O', 'price': 6},
                ],
                'type': 2,
                'active': True,
                'tenant_id': ['12345'],
                'shift': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'device': 'D1',
            },
            {
                'receipt': [
                    {'type': 'T', 'price': 6},
                    {'type': 'T', 'price': 11},
                    {'type': 'I', 'price': 6},
                    {'type': 'U', 'price': 6},
                    {'type': 'O', 'price': 6},
                ],
                'type': 3,
                'active': True,
                'tenant_id': ['12345'],
                'shift': '2',
                'device': 'D1',
            },
        ]
    )

    response = get_eos_overview(
        EOS(), request_(json_body={'filter': {'deviceId': 'D1'}})
    )
    # tested seperately
    response['data'].pop('openShifts')
    assert response['data'] == {
        'endBalance': 1,
        'expectedCashInDrawer': 1,
        'receiptTotals': {
            'couponIn': 17,
            'couponOut': -17,
            'creditReceipt': 49,
            'storeCredit': 17,
        },
        'paymentTotals': {
            'cash': 17,
            'change': 17,
            'consignment': 17,
            'creditcard': 17,
            'creditreceipt': 17,
            'deposit': 5,
            'pin': 17,
            'storecredit': 17,
            'withdrawel': 10,
        },
    }


def test_get_all_open(spynl_data_db, request_):
    """test o1 c c o2 o3 returns o2"""
    eos_docs = []
    period_starts = []
    for days in range(1, 5):
        period_start = make_relative_dates(-days)[0]
        period_starts.append(period_start)
        eos_docs.append(
            {
                'tenant_id': '12345',
                'device': {'id': 'D1'},
                'cycleID': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'periodStart': period_start,
                'periodEnd': period_start + timedelta(hours=5),
                'status': 'generated',
                'active': True,
            }
        )
    eos_docs[2].update({'status': 'completed', 'endBalance': 1})
    eos_docs[3]['status'] = 'completed'
    eos_docs.append(eos_docs[1].copy())
    eos_docs[4].update({'active': False})
    spynl_data_db.eos.insert_many(eos_docs)

    response = get_eos_overview(
        EOS(), request_(json_body={'filter': {'deviceId': 'D1'}})
    )['data']

    assert response['openShifts'][0]['periodStart'] == period_starts[1]
    assert len(response['openShifts']) == 2


def test_get_all_open_eos_no_closed_exists(spynl_data_db, request_):
    """test o1 o2 o3 o4 returns o1"""
    eos_docs = []
    period_starts = []
    for days in range(1, 5):
        period_start = make_relative_dates(-days)[0]
        period_starts.append(period_start)
        eos_docs.append(
            {
                'tenant_id': '12345',
                'device': {'id': 'D1'},
                'cycleID': 'cfbde51b-cb76-44e6-8cf5-4c264444f8c5',
                'periodStart': period_start,
                'periodEnd': period_start + timedelta(hours=5),
                'status': 'generated',
                'active': True,
            }
        )
    spynl_data_db.eos.insert_many(eos_docs)

    response = get_eos_overview(
        EOS(), request_(json_body={'filter': {'deviceId': 'D1'}})
    )['data']

    assert response['openShifts'][0]['periodStart'] == period_starts[3]
    assert len(response['openShifts']) == 4


@pytest.mark.parametrize(
    'docs,_id',
    [
        (
            [
                {'_id': 1, 'status': 'generated', 'periodStart': datetime(2019, 1, 1)},
                {'_id': 2, 'status': 'generated', 'periodStart': datetime(2019, 1, 2)},
                {'_id': 3, 'status': 'generated', 'periodStart': datetime(2019, 1, 3)},
                {'_id': 4, 'status': 'generated', 'periodStart': datetime(2019, 1, 4)},
            ],
            1,
        ),
        (
            [
                {'_id': 1, 'status': 'generated', 'periodStart': datetime(2019, 1, 1)},
                {'_id': 2, 'status': 'completed', 'periodStart': datetime(2019, 1, 2)},
                {'_id': 3, 'status': 'generated', 'periodStart': datetime(2019, 1, 3)},
                {'_id': 4, 'status': 'generated', 'periodStart': datetime(2019, 1, 4)},
            ],
            3,
        ),
        (
            [
                {'_id': 1, 'status': 'completed', 'periodStart': datetime(2019, 1, 1)},
                {'_id': 2, 'status': 'generated', 'periodStart': datetime(2019, 1, 2)},
                {
                    '_id': 3,
                    'status': 'rectification',
                    'periodStart': datetime(2019, 1, 3),
                },
                {'_id': 4, 'status': 'generated', 'periodStart': datetime(2019, 1, 4)},
            ],
            4,
        ),
    ],
)
def test_newest_start(spynl_data_db, docs, _id):
    for doc in docs:
        doc.setdefault('active', True)
    spynl_data_db.eos.insert_many(docs)
    assert _get_last_open(spynl_data_db.eos, {'filter': {}})[0]['_id'] == _id


@pytest.mark.parametrize(
    'filter_, count',
    [
        ({'deviceId': '1'}, 1),
        ({'device.id': '2'}, 1),
        ({'periodStart': '2019-01-01T00:00:00'}, 1),
        ({'periodStart': {'$gte': '2019-01-01T00:00:00'}}, 1),
        ({'periodEnd': '2018-01-30T00:00:00'}, 1),
        ({'periodEnd': {'$lte': '2018-01-30T00:00:00'}}, 1),
        ({'periodEnd': {'$lte': '2020-01-30T00:00:00'}}, 2),
        ({'periodStart': {'$exists': True}}, 2),
        ({'periodEnd': {'$exists': True}}, 2),
        ({'status': ['completed', 'generated']}, 2),
        ({'status': ['completed']}, 1),
        ({}, 2),
    ],
)
def test_get_eos(filter_, count, spynl_data_db, request_):
    spynl_data_db.eos.insert_many(
        [
            {
                'tenant_id': ['12345'],
                'device': {'id': '1'},
                'periodStart': datetime(2019, 1, 10),
                'periodEnd': datetime(2019, 1, 20),
                'active': True,
                'status': 'generated',
            },
            {
                'tenant_id': ['12345'],
                'device': {'id': '2'},
                'periodStart': datetime(2018, 1, 1),
                'periodEnd': datetime(2018, 1, 20),
                'active': True,
                'status': 'completed',
            },
            {
                'tenant_id': ['12345'],
                'device': {'id': '2'},
                'active': True,
                'status': 'completed',
            },
        ]
    )
    response = get(EOS(), request_(json_body={'filter': filter_}))['data']
    assert len(response) == count


def test_save_eos(request_, monkeypatch, spynl_data_db):
    monkeypatch.setattr(
        'spynl.api.retail.eos.get_user_info', lambda *a, **kw: {'user': {'_id': 1}}
    )

    class PatchedEOS(Schema):
        _id = fields.Field()
        status = fields.Field(load_default='opened')

    monkeypatch.setattr('spynl.api.retail.eos.EOSSchema', PatchedEOS)
    response = save(
        EOS(),
        request_(
            cached_user={'_id': ObjectId(), 'username': 'a user'},
            json_body={'data': [{'_id': 1}]},
        ),
    )
    assert len(response['data']) == 1


def test_save_completed_eos(request_, monkeypatch, spynl_data_db):
    monkeypatch.setattr(
        'spynl.api.retail.eos.get_user_info', lambda *a, **kw: {'user': {'_id': 1}}
    )

    user_id = TENANTS[0].user_ids[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]

    # Create a new eos with some fake values
    new_eos = eos_doc_factory(
        2, user_id, tenant_id, shop, device_name, status='completed'
    )

    new_eos['periodStart'] = str(new_eos['periodStart'])
    # Remove the periodEnd, the endpoint should create it
    new_eos.pop('periodEnd')

    response = save(
        EOS(),
        request_(
            cached_user={'_id': ObjectId(), 'username': 'a user'},
            session_or_token_id='1',
            json_body={'data': [new_eos]},
        ),
    )
    assert len(response['data']) == 1

    # check the result of the save
    saved_eos = spynl_data_db.pymongo_db.eos.find_one(response['data'][0])
    # The periodEnd should be set on saving completed EOS
    assert saved_eos['periodEnd']

    # A seteod event should be created on saving a completed EOS
    events = spynl_data_db.pymongo_db.events.count_documents(dict(method='seteod'))
    assert events == 1


def test_calculate_expected_cash_in_drawer():
    start_balance = 1
    payment_totals = {
        'cash': 4,
        'change': 2,
        'consignment': 8,
        'creditcard': 16,
        'creditreceipt': 32,
        'deposit': 64,
        'pin': 128,
        'storecredit': 256,
        'withdrawel': 512,
    }
    schema = EOSOverviewSchema()
    # Result should only depend on start balance, cash and change.
    assert schema.calculate_expected_cash_in_drawer(start_balance, payment_totals) == 3


def test_reset_eos(request_, monkeypatch, spynl_data_db):
    monkeypatch.setattr(
        'spynl.api.retail.eos.get_user_info', lambda *a, **kw: {'user': {'_id': 1}}
    )

    user_id = TENANTS[0].user_ids[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]

    # Create a new eos with some fake values
    new_eos = eos_doc_factory(
        2, user_id, tenant_id, shop, device_name, status='completed'
    )
    new_eos.update(
        {
            '_id': '1',
            'turnover': 100,
            'openingBalance': 100,
            'endBalance': 300,
            'deposit': 200,
            'expectedCashInDrawer': 100,
            'totalCashInDrawer': 100,
            'cashInDrawer': [{'value': 10}],
            'original': {'cash': 100},
            'final': {'cash': 100},
        }
    )

    result = spynl_data_db.pymongo_db.eos.insert_one(new_eos)

    response = reset(
        EOS(),
        request_(
            cached_user={'_id': ObjectId(), 'username': 'a user'},
            json_body={'filter': {'_id': result.inserted_id}},
        ),
    )
    assert len(response['data']) == 1

    # check the result of the reset
    reset_eos = spynl_data_db.pymongo_db.eos.find_one(result.inserted_id)

    # These fields should be reset
    assert reset_eos['status'] == 'generated'
    assert reset_eos['turnover'] == 0
    assert reset_eos['openingBalance'] == 0
    assert reset_eos['endBalance'] == 0
    assert reset_eos['deposit'] == 0
    assert reset_eos['expectedCashInDrawer'] == 0
    assert reset_eos['totalCashInDrawer'] == 0
    assert reset_eos['cashInDrawer'] == list()
    assert reset_eos['original']['cash'] == 0
    assert reset_eos['final']['cash'] == 0

    # These fields should remain the same as the original eos
    assert reset_eos['cycleID'] == '1'
    assert reset_eos['shop'] == new_eos['shop']
    assert reset_eos['device'] == new_eos['device']
    assert reset_eos['periodStart'] == new_eos['periodStart']

    events = list(spynl_data_db.events.find({'method': 'reseteod'}))
    assert len(events) == 1


def test_reset_eos_only_completed(request_, monkeypatch, spynl_data_db):
    monkeypatch.setattr(
        'spynl.api.retail.eos.get_user_info', lambda *a, **kw: {'user': {'_id': 1}}
    )

    user_id = TENANTS[0].user_ids[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]

    # Create a new eos with some fake values
    new_eos = eos_doc_factory(
        2, user_id, tenant_id, shop, device_name, status='generated'
    )
    new_eos['_id'] = '2'

    result = spynl_data_db.pymongo_db.eos.insert_one(new_eos)

    with pytest.raises(IllegalAction):
        reset(EOS(), request_(json_body={'filter': {'_id': result.inserted_id}}))


@pytest.mark.parametrize('json_body', [{'id': 'xxx'}, {'xxx': 'xxx'}, {}, None])
def test_reset_eos_filter(request_, monkeypatch, json_body):
    monkeypatch.setattr(
        'spynl.api.retail.eos.get_user_info', lambda *a, **kw: {'user': {'_id': 1}}
    )

    with pytest.raises(ValidationError):
        reset(EOS(), request_(json_body=json_body))


def test_reset_eos_endpoint(app):
    # Test that endpoint is registered
    app.post_json('/eos/reset', status=403)


def test_eos_init_endpoint(app):
    # Test that endpoint is registered
    app.post_json('/eos/init', status=403)


@pytest.mark.parametrize(
    "status, cycle_id, create_previous, expected",
    [
        (
            'generated',
            '1111',
            True,
            'previous_1111',
        ),  # should return the previously saved eos doc
        (
            'completed',
            '2222',
            True,
            'uuid',
        ),  # should return a new eos doc, if the previous is complete
        (
            None,
            '3333',
            False,
            'uuid',
        ),  # should return a new eos doc because none existed before
    ],
)
def test_eos_init(
    monkeypatch, spynl_data_db, request_, status, cycle_id, create_previous, expected
):
    monkeypatch.setattr(
        'spynl.api.retail.eos.get_user_info', lambda *a, **kw: {'user': {'_id': 1}}
    )

    user_id = TENANTS[0].user_ids[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]
    location_id = '51'
    device_id = 'D1'

    # Insert location document
    location = {'wh': location_id, 'name': shop.name, 'tenant_id': [tenant_id]}
    spynl_data_db.pymongo_db.warehouses.insert_one(location)

    # Create a new eos with some fake values and save in database
    if create_previous:
        new_eos = eos_doc_factory(2, user_id, tenant_id, shop, device_name, status)

        new_eos['cycleID'] = 'previous_' + cycle_id

        # Insert an existing eos
        spynl_data_db.pymongo_db.eos.insert_one(new_eos)

    response = init(
        EOS(),
        request_(
            json_body={},
            cached_user={
                'deviceId': device_id,
                'wh': location_id,
                'fullname': device_name,
            },
        ),
    )
    assert len(response['data']) == 1

    eos = response['data'][0]
    if expected == 'uuid':
        uuid.UUID(eos['cycleID'])  # will fail if not a uuid
    else:
        assert eos['cycleID'] == expected
    assert eos['shop']['id'] == location_id
    assert eos['shop']['name'] == shop.name
    assert eos['device']['id'] == device_id
    assert eos['device']['name'] == device_name


USER_ID = ObjectId()
USER_ID_2 = ObjectId()


@pytest.fixture
def setup_for_rectify(spynl_data_db):
    device_id = '1'
    location_id = '51'
    device = {
        '_id': USER_ID,
        'deviceId': device_id,
        'wh': location_id,
        'fullname': 'device_name',
        'tenant_id': [TENANT_ID],
    }
    spynl_data_db.pymongo_db.users.insert_one(device)
    device_2 = {
        '_id': USER_ID_2,
        'deviceId': device_id,
        'wh': '52',
        'fullname': 'device_name',
        'tenant_id': [TENANT_ID_2],
    }
    spynl_data_db.pymongo_db.users.insert_one(device_2)

    spynl_data_db.warehouses.insert_many(
        [
            {'wh': location_id, 'name': 'shop name', 'tenant_id': [TENANT_ID]},
            {'wh': '52', 'name': 'shop name', 'tenant_id': [TENANT_ID_2]},
        ]
    )


def test_eos_rectify(database_setup, app, setup_for_rectify):
    payload = {'userId': str(USER_ID), 'value': 22.65, 'remarks': 'fix eos!'}
    response = app.post_json('/eos/rectify', payload, status=200)
    assert response.json['data'][0]['endBalance'] == 22.65
    assert response.json['data'][0]['openingBalance'] == 22.65
    assert response.json['data'][0]['remarks'] == 'fix eos!'


def test_eos_rectify_unique(database_setup, app, setup_for_rectify):
    payload = {'userId': str(USER_ID), 'value': 22.65, 'remarks': 'fix eos!'}
    app.post_json('/eos/rectify', payload, status=200)

    app.get('/login?username=%s&password=%s' % ('user2', 'password'))
    payload = {'userId': str(USER_ID_2), 'value': 22.65, 'remarks': 'fix eos!'}
    app.post_json('/eos/rectify', payload, status=200)
    app.get('/logout')


def test_eos_rectify_restriction(database_setup, app, setup_for_rectify):
    """second time should fail."""
    payload = {'userId': str(USER_ID), 'value': 22.65}
    app.post_json('/eos/rectify', payload, status=200)
    app.post_json('/eos/rectify', payload, status=400)
