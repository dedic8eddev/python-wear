"""Tests for the inventory endpoints."""
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
import pytz
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.main.dateutils import date_format_str

from spynl.api.retail import inventory
from spynl.api.retail.resources import Inventory

PATH = os.path.dirname(os.path.abspath(__file__))


class Factory:
    def __init__(self, username, tenant_id, warehouse_id):
        self.user_id = ObjectId()
        self.username = username
        self.tenant_id = tenant_id
        self.warehouse_id = warehouse_id


BOY = Factory('boy', 'tenant_1', '1')
# add a second group of data to ensure in tests that cannot be accessed
GIRL = Factory('girl', 'tenant_2', '2')


@pytest.fixture(scope="module")
def _read_sample_data():
    """Read once and return the test transaction data."""
    with open(f'{PATH}/data/inventory.json', 'r') as fob:
        data = json.loads(fob.read())
        # make the sample inventory transaction to have a valid warehouseId
        # that these tests expect to have
        data['warehouseId'] = BOY.warehouse_id
    return data


@pytest.fixture
def sample_data(_read_sample_data):
    return deepcopy(_read_sample_data)


class SpynlDummyRequest(DummyRequest):
    def __init__(self, *args, **kwargs):
        kwargs['headers'] = dict(sid='123123123123')
        self.session_or_token_id = kwargs['headers']['sid']

        kwargs['session'] = dict(username=BOY.username)
        kwargs['requested_tenant_id'] = BOY.tenant_id
        kwargs[
            'args'
        ] = {}  # need to be defined because Spynl attaches it to the request
        # A real pyramid request includes GET & POST in .params
        # A dummy one works a bit differently, fix that.
        if kwargs.get('post'):
            kwargs['args'] = kwargs['post']
        # a pyramid request provides the context in the request
        _request = super().__init__(*args, **kwargs)
        self.context = Inventory(_request)

    @property
    def json_payload(self):
        return self.json_body


@pytest.fixture
def request_(spynl_data_db):
    SpynlDummyRequest.db = spynl_data_db
    SpynlDummyRequest.cached_user = {'_id': ObjectId(), 'username': 'a user'}
    return SpynlDummyRequest


@pytest.fixture(autouse=True)
def setup_db(db, sample_data):
    for i, user in enumerate((BOY, GIRL)):
        warehouse = dict(
            _id=str(i + 1), tenant_id=[user.tenant_id], wh=user.warehouse_id
        )
        # map the 1st one with user's warehouse_id
        db.warehouses.insert_one(warehouse)

    db.tenants.insert_many([dict(_id=user.tenant_id) for user in (BOY, GIRL)])

    db.users.insert_many(
        [
            dict(_id=user.user_id, username=user.username, tenant_id=[user.tenant_id])
            for user in (BOY, GIRL)
        ]
    )

    for user in BOY, GIRL:
        for num in range(3):
            doc = deepcopy(sample_data)
            doc['docNumber'] = uuid.uuid4()
            doc['tenant_id'] = [user.tenant_id]
            doc['warehouseId'] = user.warehouse_id
            doc['active'] = True
            doc['created'] = dict(
                # starting from today and backwards pretend documents were
                # inserted in the past(one per day)
                date=datetime.now(pytz.utc) - timedelta(days=num),
                action='add inventory transaction',
                tenant_id=[user.tenant_id],
                user=dict(_id=user.user_id, username=user.username),
            )
            db.inventory.insert_one(doc)


def test_adding_new_products_to_inventory(db, config, request_, sample_data):
    """Basically check that the products exist in the saved transaction."""
    config.testing_securitypolicy(userid=BOY.user_id)
    original_products = deepcopy(sample_data['products'])
    response = inventory.add(request_(post={'data': sample_data}))
    doc = db.inventory.find_one(dict(_id=ObjectId(response['data'][0])))
    assert all(product in doc['products'] for product in original_products)
    assert db.events.count_documents({}) == 1
    event = db.events.find_one({})
    assert 'wh__1' in event['fpquery']


def test_total_qty_is_calculated(db, config, request_, app, sample_data):
    total_qty = sum(product['qty'] for product in sample_data['products'])
    config.testing_securitypolicy(userid=BOY.user_id)
    response = inventory.add(request_(post={'data': sample_data}))
    doc = db.inventory.find_one(dict(_id=ObjectId(response['data'][0])))
    assert doc['totalQty'] == total_qty


def test_transaction_with_invalid_docNumber(config, request_, sample_data):
    """The docNumber should be valid UUID."""
    config.testing_securitypolicy(userid=BOY.user_id)
    sample_data['docNumber'] = 'foo'
    with pytest.raises(Exception) as err:
        inventory.add(request_(post={'data': sample_data}))
    assert err.value.messages['docNumber'] == ['Not a valid UUID.']


def test_transaction_with_valid_docNumber(config, request_, db, sample_data):
    """Every transaction should have a valid unique uuid."""
    config.testing_securitypolicy(userid=BOY.user_id)
    uuid_ = uuid.uuid4()
    sample_data['docNumber'] = str(uuid_)
    response = inventory.add(request_(post={'data': sample_data}))
    doc = db.inventory.find_one({'_id': ObjectId(response['data'][0])})
    assert doc['docNumber'] == uuid_


def test_with_already_existing_docNumber(config, request_, sample_data):
    """The docNumber is what distinguishes transactions thus it should be unique."""
    config.testing_securitypolicy(userid=BOY.user_id)
    original_data = deepcopy(sample_data)
    inventory.add(request_(post={'data': sample_data}))
    with pytest.raises(Exception) as err:
        inventory.add(request_(post={'data': original_data}))
    assert 'uuid already exists' in err.value.developer_message


def test_getting_inventories_filtering_by_warehouse(db, sample_data, config, request_):
    for id_ in range(3):
        doc = deepcopy(sample_data)
        doc['tenant_id'] = [BOY.tenant_id]
        doc['active'] = True
        doc['warehouseId'] = BOY.warehouse_id
        db.inventory.insert_one(doc)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(warehouseId=BOY.warehouse_id))
    response = inventory.get(request_(json_body=params))

    query = {'warehouseId': BOY.warehouse_id, 'tenant_id': {'$in': [BOY.tenant_id]}}
    docs = list(db.inventory.find(query))
    assert response['data'] and response['data'] == docs


def test_getting_inventories_without_filters_includes_all_warehouses(
    db, config, request_
):
    warehouses = db.warehouses.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    warehouse_ids = [w['wh'] for w in warehouses]
    docs = db.inventory.find({'warehouseId': {'$in': warehouse_ids}})

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(username=BOY.username))
    response = inventory.get(request_(json_body=params))
    assert response['data'] == list(docs)


def test_start_date_only(db, config, request_):
    """From yesterday till today."""
    now = datetime.now()
    yesterday = datetime(
        now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=pytz.utc
    ) - timedelta(days=1)
    docs = list(
        db.inventory.find(
            {'tenant_id': {'$in': [BOY.tenant_id]}, 'created.date': {'$gte': yesterday}}
        )
    )
    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(startDate=yesterday.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    assert response['data'] == docs and len(docs) == 2


def test_end_date_only(db, config, request_):
    """From the beggining till yesterday."""
    now = datetime.now()
    yesterday = datetime(
        now.year, now.month, now.day, 23, 59, 59, 999, tzinfo=pytz.utc
    ) - timedelta(days=1)
    docs = list(
        db.inventory.find(
            {'tenant_id': {'$in': [BOY.tenant_id]}, 'created.date': {'$lte': yesterday}}
        )
    )
    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=yesterday.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    assert response['data'] == docs and len(docs) == 2


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
        db.inventory.find(
            {
                'tenant_id': {'$in': [BOY.tenant_id]},
                '$and': [
                    {'created.date': {'$gte': day_before_yesterday}},
                    {'created.date': {'$lte': yesterday}},
                ],
            }
        )
    )
    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=yesterday.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    assert response['data'] == docs and len(docs) == 2


def test_start_date_earlier_than_oldest_transaction(db, config, request_):
    """It should return all transactions from the beggining of time."""
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    nonexistent = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(startDate=nonexistent.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    inventories = list(db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}}))
    assert response['data'] == inventories and len(inventories) == 3


def test_start_date_later_than_newest_trasaction(db, config, request_):
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    nonexistent = newest + timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(startDate=nonexistent.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    assert not response['data']


def test_end_date_later_than_newest_transaction(db, config, request_):
    """It should return all transactions till the latest transaction."""
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    nonexistent = newest + timedelta(days=2)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=nonexistent.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    inventories = list(db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}}))
    assert response['data'] == inventories and len(inventories) == 3


def test_end_date_earlier_than_oldest_trasaction(db, config, request_):
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    nonexistent = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=nonexistent.strftime(date_format_str())))
    response = inventory.get(request_(json_body=params))
    assert not response['data']


def test_overlapping_dates(db, config, request_):
    """Cancels each other out."""
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(
        filter=dict(
            startDate=newest.strftime(date_format_str()),
            endDate=oldest.strftime(date_format_str()),
        )
    )
    response = inventory.get(request_(json_body=params))
    assert not response['data']


def test_start_and_end_dates_before_oldest_transaction(db, config, request_):
    """It should return empty list of transactions."""
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']

    start_date = oldest - timedelta(days=2)
    end_date = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(
        filter=dict(
            startDate=start_date.strftime(date_format_str()),
            endDate=end_date.strftime(date_format_str()),
        )
    )
    response = inventory.get(request_(json_body=params))
    assert not response['data']


def test_start_and_end_dates_after_newest_transaction(db, config, request_):
    """It should return empty list of transacztions."""
    docs = db.inventory.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    start_date = newest + timedelta(days=1)
    end_date = newest + timedelta(days=2)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(
        filter=dict(
            startDate=start_date.strftime(date_format_str()),
            endDate=end_date.strftime(date_format_str()),
        )
    )
    response = inventory.get(request_(json_body=params))
    assert not response['data']
