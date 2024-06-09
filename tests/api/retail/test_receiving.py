"""Tests for the transaction type: Receivings."""

import uuid
from copy import deepcopy
from datetime import datetime, timedelta

import pymongo
import pytest
import pytz
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.main.dateutils import date_format_str

from spynl.api.auth.authentication import scramble_password
from spynl.api.retail.receiving import ReceivingFilterSchema, get
from spynl.api.retail.resources import Receiving

USER_ID = ObjectId()
TENANT_ID = '43588'
WAREHOUSE_ID = '61'
WAREHOUSE_ID_2 = '123'

TENANT = {'_id': TENANT_ID, 'applications': ['logistics']}
USER = {
    '_id': USER_ID,
    'email': 'blahuser@blah.com',
    'roles': {TENANT_ID: {'tenant': ['logistics-receivings_user']}},
    'password_hash': scramble_password('blah', 'blah', '2'),
    'password_salt': 'blah',
    'hash_type': '2',
    'active': True,
    'tenant_id': [TENANT_ID],
    'username': 'blahuser',
}
WAREHOUSE = {'_id': '1', 'wh': WAREHOUSE_ID, 'tenant_id': TENANT_ID}
WAREHOUSE_2 = {'_id': ObjectId(), 'wh': WAREHOUSE_ID_2, 'tenant_id': TENANT_ID}

RANDOM_USER_ID = ObjectId()
RANDOM_TENANT_ID = 'foo'
RECEIVINGS_PER_WAREHOUSE = 2


class SpynlDummyRequest(DummyRequest):
    def __init__(self, *args, **kwargs):
        kwargs['headers'] = dict(sid='123123123123')
        self.session_or_token_id = kwargs['headers']['sid']
        kwargs['requested_tenant_id'] = TENANT_ID
        kwargs.setdefault('args', {})
        # treat DummyRequest as a real one by using the port arguments but Spynl pass
        # them in the .args attribute
        if kwargs.get('post'):
            kwargs['args'] = kwargs['post']
        super().__init__(*args, **kwargs)

    @property
    def json_payload(self):
        return self.json_body


@pytest.fixture
def request_(spynl_data_db):
    SpynlDummyRequest.db = spynl_data_db
    return SpynlDummyRequest


@pytest.fixture(scope='module')
def setup_db_indexes(db):
    """Setup indexes once for all tests."""
    db.receivings.create_index([('docNumber', pymongo.ASCENDING)], unique=True)
    yield
    db.receivings.drop_indexes()


@pytest.fixture(autouse=True)
def setup_db(db, setup_db_indexes):
    db.tenants.insert_one(TENANT)
    db.users.insert_one(USER)
    db.warehouses.insert_many([WAREHOUSE, WAREHOUSE_2])

    tenant_ids = (TENANT_ID, RANDOM_TENANT_ID)
    warehouse_ids = (WAREHOUSE_ID, WAREHOUSE_ID_2)
    user_ids = (USER_ID, RANDOM_USER_ID)

    for tenant_id, wh in zip(tenant_ids, warehouse_ids):
        db.warehouses.insert_one(dict(wh=wh, tenant_id=[tenant_id]))

    dummy_data = dict(
        remarks='',
        totalBuyPrice=0,
        totalLandedCostPrice=0,
        totalPosNormalPrice=0,
        active=True,
        created=dict(action='add receiving transaction', user=dict()),
    )

    def make_product(num):
        """Helper function to return a product with sample data."""
        return dict(
            qty=num,
            barcode='{}|||{}'.format(num, num),
            articleCode='foo',
            supplierId=None,
            buyPrice=None,
            landedCostPrice=None,
            posNormalPrice=None,
        )

    for tenant_id, user_id, wh in zip(tenant_ids, user_ids, warehouse_ids):
        for num in range(RECEIVINGS_PER_WAREHOUSE):
            data = deepcopy(dummy_data)
            data['products'] = [make_product(num)]
            data['totalQty'] = num
            data['docNumber'] = uuid.uuid4()
            data['warehouseId'] = wh
            data['tenant_id'] = [tenant_id]

            # today, yesterda, day before yesterday etc
            data['created']['date'] = datetime.now(pytz.utc) - timedelta(days=num)
            data['created']['user']['_id'] = user_id
            data['created']['tenant_id'] = tenant_id

            db.receivings.insert_one(data)


def test_warehouses_receiving():
    input = {'warehouseId': '1'}
    data = ReceivingFilterSchema(context=dict(tenant_id='1')).load(input)
    # see the DB class above to check how it's mocked.
    assert data['warehouseId'] == '1'
    assert 'warehouse' not in data


def test_add_receiving(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '1', 'status': 'draft'}}
    app.post_json('/receivings/save', payload, status=200)


def test_add_receiving_increment_counter(app, db):
    """This was a bug"""
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '1', 'status': 'draft', 'skus': []}}
    response = app.post_json('/receivings/save', payload, status=200)
    payload = {'filter': {'_id': response.json['data'][0]}}
    receiving = app.post_json('/receivings/get', payload, status=200).json['data'][0]
    order_number = receiving['orderNumber']
    receiving['status'] = 'complete'
    response = app.post_json('/receivings/save', {'data': receiving}, status=200)
    receiving = db.receivings.find_one({'_id': uuid.UUID(response.json['data'][0])})
    assert receiving['orderNumber'] == order_number


def test_add_receiving_objectid_warehouse(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': str(WAREHOUSE_2['_id']), 'status': 'draft'}}
    app.post_json('/receivings/save', payload, status=200)


def test_add_receiving_non_existent_warehouse(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '2', 'status': 'draft'}}
    app.post_json('/receivings/save', payload, status=400)


def test_edit_receiving(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '1', 'status': 'draft'}}
    resp = app.post_json('/receivings/save', payload, status=200)
    payload['data'].update({'_id': resp.json['data'][0], 'status': 'complete'})
    app.post_json('/receivings/save', payload, status=200)


def test_bad_warehouse(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '10000000', 'status': 'draft'}}
    app.post_json('/receivings/save', payload, status=400)


def test_edit_complete(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '1', 'status': 'complete'}}
    resp = app.post_json('/receivings/save', payload, status=200)
    payload['data'].update({'_id': resp.json['data'][0]})
    app.post_json('/receivings/save', payload, status=400)


def test_duplicate_docnumber(app):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {
        'data': {'docNumber': uuid.uuid4().hex, 'warehouseId': '1', 'status': 'draft'}
    }
    app.post_json('/receivings/save', payload, status=200)
    app.post_json('/receivings/save', payload, status=400)


def test_events(app, spynl_data_db):
    app.get('/login', params=dict(username=USER['username'], password='blah'))
    payload = {'data': {'warehouseId': '1', 'status': 'draft'}}
    resp = app.post_json('/receivings/save', payload, status=200)
    assert spynl_data_db.events.count_documents({}) == 0
    payload['data'].update({'_id': resp.json['data'][0], 'status': 'complete'})
    app.post_json('/receivings/save', payload, status=200)
    event = spynl_data_db.events.find_one({})
    assert 'wh__61' in event['fpquery']


def test_receivings_get_complains_filtering_with_bad_date(config, db, request_):
    config.testing_securitypolicy(userid=USER_ID)
    params = dict(filter=dict(startDate='foo bar'))
    request = request_(json_body=params)
    with pytest.raises(Exception) as err:
        get(Receiving(request), request)
    assert err.value.messages['filter']['startDate'] == ['Not a valid datetime.']


def test_start_date_only(db, config, request_):
    """From yesterday till today."""
    now = datetime.now()
    yesterday = datetime(
        now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=pytz.utc
    ) - timedelta(days=1)

    docs = db.receivings.find(
        {'tenant_id': {'$in': [TENANT_ID]}, 'created.date': {'$gte': yesterday}}
    )
    config.testing_securitypolicy(userid=USER_ID)
    params = dict(startDate=yesterday.strftime(date_format_str()))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert response['data'] == list(docs)


def test_end_date_only(db, config, request_):
    """From the beggining till yesterday."""
    now = datetime.now()
    yesterday = datetime(
        now.year, now.month, now.day, 23, 59, 59, 999, tzinfo=pytz.utc
    ) - timedelta(days=1)
    docs = db.receivings.find(
        {'tenant_id': {'$in': [TENANT_ID]}, 'created.date': {'$lte': yesterday}}
    )
    config.testing_securitypolicy(userid=USER_ID)
    params = dict(filter=dict(endDate=yesterday.strftime(date_format_str())))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert response['data'] == list(docs)


def test_start_date_and_end_date(db, config, request_):
    """Aim for the first 2 transactions, yesterday and the day before."""
    now = datetime.now()
    day_before_yesterday = datetime(
        now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=pytz.utc
    ) - timedelta(days=2)
    yesterday = datetime(
        now.year, now.month, now.day, 23, 59, 59, 999, tzinfo=pytz.utc
    ) - timedelta(days=1)

    docs = list(
        db.receivings.find(
            {
                'tenant_id': {'$in': [TENANT_ID]},
                '$and': [
                    {'created.date': {'$gte': day_before_yesterday}},
                    {'created.date': {'$lte': yesterday}},
                ],
            }
        )
    )
    config.testing_securitypolicy(userid=USER_ID)
    params = dict(filter=dict(endDate=yesterday.strftime(date_format_str())))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert response['data'] == docs and len(docs) == 1


def test_start_date_earlier_than_oldest_transaction(db, config, request_):
    """It should return all transactions from the beggining of time."""
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    nonexistent = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(startDate=nonexistent.strftime(date_format_str()))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    inventories = list(db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}}))
    assert response['data'] == inventories and len(inventories) == 2


def test_start_date_later_than_newest_trasaction(db, config, request_):
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    nonexistent = newest + timedelta(days=1)

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(filter=dict(startDate=nonexistent.strftime(date_format_str())))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert not response['data']


def test_end_date_later_than_newest_transaction(db, config, request_):
    """It should return all transactions till the latest transaction."""
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    nonexistent = newest + timedelta(days=1)

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(endDate=nonexistent.strftime(date_format_str()))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    inventories = list(db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}}))
    assert response['data'] == inventories and len(inventories) == 2


def test_end_date_earlier_than_oldest_trasaction(db, config, request_):
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    nonexistent = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(filter=dict(endDate=nonexistent.strftime(date_format_str())))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert not response['data']


def test_overlapping_dates(db, config, request_):
    """Cancels each other out."""
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(
        filter=dict(
            startDate=newest.strftime(date_format_str()),
            endDate=oldest.strftime(date_format_str()),
        )
    )
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert not response['data']


def test_start_and_end_dates_before_oldest_transaction(db, config, request_):
    """It should return empty list of transactions."""
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    start_date = oldest - timedelta(days=2)
    end_date = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(
        filter=dict(
            startDate=start_date.strftime(date_format_str()),
            endDate=end_date.strftime(date_format_str()),
        )
    )
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert not response['data']


def test_start_and_end_dates_after_newest_transaction(db, config, request_):
    """It should return empty list of transacztions."""
    docs = db.receivings.find({'tenant_id': {'$in': [TENANT_ID]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    start_date = newest + timedelta(days=1)
    end_date = newest + timedelta(days=2)

    config.testing_securitypolicy(userid=USER_ID)
    params = dict(
        filter=dict(
            startDate=start_date.strftime(date_format_str()),
            endDate=end_date.strftime(date_format_str()),
        )
    )
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert not response['data']


def test_receivings_get_by_invalid_docnumber(db, config, request_):
    config.testing_securitypolicy(userid=USER_ID)
    params = dict(filter=dict(docNumber=str(uuid.uuid4())))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert response['data'] == []


def test_receivings_get_by_valid_docnumber(db, config, request_):
    config.testing_securitypolicy(userid=USER_ID)
    doc = db.receivings.find_one({'created.user._id': USER_ID})

    params = dict(filter=dict(docNumber=str(doc['docNumber'])))
    request = request_(json_body=params)
    response = get(Receiving(request), request)
    assert response['data'] == [doc]
