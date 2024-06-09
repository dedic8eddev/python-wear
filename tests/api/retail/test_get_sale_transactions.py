import json
import os
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
import pytz
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.main.dateutils import date_format_str

from spynl.api.retail.resources import Sales
from spynl.api.retail.sales import sale_get

PATH = os.path.dirname(os.path.abspath(__file__))


class Factory:
    def __init__(self, username, tenant_id, warehouse_id):
        self.user_id = ObjectId()
        self.username = username
        self.tenant_id = tenant_id
        self.warehouse_id = ObjectId()
        # the 1st warehouse number should be mapped with the above warehouse_id
        # so there is a known warehouse with its _id for reference
        self.wh = warehouse_id


BOY = Factory('boy', 'tenant_1', '51')
# add a second group of data to ensure in tests that cannot be accessed
GIRL = Factory('girl', 'tenant_2', '52')


@pytest.fixture(scope="module")
def _read_sample_data():
    """Read once and return the test transaction data."""
    with open(f'{PATH}/data/transaction.json', 'r') as fob:
        data = json.loads(fob.read())
    return data


@pytest.fixture
def sample_data(_read_sample_data):
    return deepcopy(_read_sample_data)


@pytest.fixture(autouse=True)
def transactions_not_large_collections(monkeypatch):
    # for our purposes we do not need to check unindexed queries here. This
    # is tested elsewhere.
    monkeypatch.setattr('spynl.api.retail.resources.Sales.is_large_collection', False)


class SpynlDummyRequest(DummyRequest):
    db = None

    def __init__(self, *args, **kwargs):
        kwargs['headers'] = dict(sid='123123123123')
        kwargs['session'] = dict(username=BOY.username)
        kwargs['requested_tenant_id'] = BOY.tenant_id
        kwargs['requested_tenant_id'] = BOY.tenant_id
        kwargs['args'] = {}
        super().__init__(*args, **kwargs)

    @property
    def json_payload(self):
        return self.json_body


@pytest.fixture
def request_(spynl_data_db):
    SpynlDummyRequest.db = spynl_data_db
    return SpynlDummyRequest


@pytest.fixture(autouse=True)
def setup_db(db, sample_data):
    warehouses = [
        dict(_id=user.warehouse_id, tenant_id=[user.tenant_id], wh=user.wh)
        for user in (BOY, GIRL)
    ]
    db.warehouses.insert_many(warehouses)

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
            doc['tenant_id'] = [user.tenant_id]
            doc['shop']['id'] = user.wh
            doc['active'] = True
            doc['created'] = dict(
                # starting from today and backwards pretend documents were
                # inserted in the past(one per day)
                date=datetime.now(pytz.utc) - timedelta(days=num),
                action='add sale transaction',
                tenant_id=[user.tenant_id],
                user=dict(_id=user.user_id, username=user.username),
            )
            db.transactions.insert_one(doc)


def test_getting_sale_by_receiptNr(db, sample_data, config, request_):
    receiptnrs = [(ObjectId(), 50), (ObjectId(), 51), (ObjectId(), 52)]
    for i in range(3):
        doc = deepcopy(sample_data)

        doc['_id'] = receiptnrs[i][0]
        doc['tenant_id'] = [BOY.tenant_id]
        doc['shop']['id'] = str(i)
        doc['active'] = True
        doc['receiptNr'] = receiptnrs[i][1]
        db.transactions.insert_one(doc)

    config.testing_securitypolicy(userid=BOY.user_id)
    receiptnr = receiptnrs[1][1]
    expected_id = receiptnrs[1][0]

    params = dict(filter=dict(receiptNr=receiptnr))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert len(response['data']) == 1 and response['data'][0]['_id'] == expected_id


def test_getting_sale_filtering_by_warehouses(db, sample_data, config, request_):
    for id_ in range(3):
        doc = deepcopy(sample_data)
        doc['tenant_id'] = [BOY.tenant_id]
        doc['shop']['id'] = str(id_)
        doc['active'] = True
        db.transactions.insert_one(doc)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(warehouseId=BOY.wh))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)

    query = {'shop.id': BOY.wh, 'tenant_id': {'$in': [BOY.tenant_id]}}
    assert list(db.transactions.find(query)) == response['data']


def test_getting_sales_without_filters_includes_all_warehouses(db, config, request_):
    warehouses = db.warehouses.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    warehouse_ids = [w['wh'] for w in warehouses]
    docs = db.transactions.find({'shop.id': {'$in': warehouse_ids}})

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict()
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert response['data'] and response['data'] == list(docs)


def test_start_date_only(db, config, request_):
    """From yesterday till today."""
    now = datetime.now()
    yesterday = datetime(
        now.year, now.month, now.day, 0, 0, 0, 0, tzinfo=pytz.utc
    ) - timedelta(days=1)
    docs = list(
        db.transactions.find(
            {'tenant_id': {'$in': [BOY.tenant_id]}, 'created.date': {'$gte': yesterday}}
        )
    )
    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(startDate=yesterday.strftime(date_format_str())))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert response['data'] == docs and len(docs) == 2


def test_end_date_only(db, config, request_):
    """From the beggining till yesterday."""
    now = datetime.now()
    yesterday = datetime(
        now.year, now.month, now.day, 23, 59, 59, 999, tzinfo=pytz.utc
    ) - timedelta(days=1)
    docs = list(
        db.transactions.find(
            {'tenant_id': {'$in': [BOY.tenant_id]}, 'created.date': {'$lte': yesterday}}
        )
    )
    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=yesterday.strftime(date_format_str())))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
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
        db.transactions.find(
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
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert response['data'] == docs and len(docs) == 2


def test_start_date_earlier_than_oldest_transaction(db, config, request_):
    """It should return all transactions from the beggining of time."""
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    nonexistent = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(startDate=nonexistent.strftime(date_format_str())))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    inventories = list(db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}}))
    assert response['data'] == inventories and len(inventories) == 3


def test_start_date_later_than_newest_trasaction(db, config, request_):
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    nonexistent = newest + timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(startDate=nonexistent.strftime(date_format_str())))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert not response['data']


def test_end_date_later_than_newest_transaction(db, config, request_):
    """It should return all transactions till the latest transaction."""
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']
    nonexistent = newest + timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=nonexistent.strftime(date_format_str())))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    inventories = list(db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}}))
    assert response['data'] == inventories and len(inventories) == 3


def test_end_date_earlier_than_oldest_trasaction(db, config, request_):
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    nonexistent = oldest - timedelta(days=1)

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(filter=dict(endDate=nonexistent.strftime(date_format_str())))
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert not response['data']


def test_overlapping_dates(db, config, request_):
    """Cancels each other out."""
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    oldest = next(docs.sort('created.date', 1).limit(1))['created']['date']
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
    newest = next(docs.sort('created.date', -1).limit(1))['created']['date']

    config.testing_securitypolicy(userid=BOY.user_id)
    params = dict(
        filter=dict(
            startDate=newest.strftime(date_format_str()),
            endDate=oldest.strftime(date_format_str()),
        )
    )
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert not response['data']


def test_start_and_end_dates_before_oldest_transaction(db, config, request_):
    """It should return empty list of transactions."""
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
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
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert not response['data']


def test_start_and_end_dates_after_newest_transaction(db, config, request_):
    """It should return empty list of transacztions."""
    docs = db.transactions.find({'tenant_id': {'$in': [BOY.tenant_id]}})
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
    request = request_(json_body=params)
    response = sale_get(Sales(request), request)
    assert not response['data']
