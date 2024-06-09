"""Tests for transaction type 3: Transit."""
import copy

import pytest
from bson import ObjectId
from marshmallow import ValidationError
from pyramid.testing import DummyRequest

from spynl.api.retail.transit import add, save

TENANT_ID = '1'


def transit(_id=None):
    data = {
        'device_id': '123',
        'nr': '123',
        'receiptNr': '456',
        'shop': {'id': '50'},
        'type': 3,
        'overallReceiptDiscount': 0,
        'transit': {'transitWarehouse': '50', 'transitPeer': '55', 'dir': 'to'},
        'cashier': {'id': '123', 'name': 'kareem'},
        'receipt': [
            {
                'category': 'barcode',
                'qty': 4,
                'barcode': '123211233',
                'articleCode': 'CODE',
                'sizeLabel': 'M',
                'color': 'black',
                'vat': 21,
                'price': 12.23,
            },
            {
                'category': 'barcode',
                'barcode': '123211231',
                'qty': 5,
                'articleCode': 'CODE2',
                'sizeLabel': 'L',
                'color': 'blue',
                'vat': 21,
                'price': 20.00,
            },
        ],
    }
    if _id:
        data['_id'] = _id
    return copy.deepcopy(data)


class Resource:
    collection = 'transactions'


ctx = Resource()


@pytest.fixture
def request_(request, spynl_data_db, monkeypatch):
    payload = {'data': request.param}

    def get_user_info(*args, **kwargs):
        return {'user': {'_id': '1'}}

    monkeypatch.setattr('spynl.api.retail.transit.get_user_info', get_user_info)
    return DummyRequest(
        requested_tenant_id=TENANT_ID,
        cached_user={'_id': ObjectId(), 'username': 'a user'},
        json_payload=payload,
        args=payload,
        db=spynl_data_db,
        session_or_token_id='token',
    )
    spynl_data_db.transactions.remove({})


@pytest.mark.parametrize('request_', [{}], indirect=True)
def test_add_bad(request_):
    with pytest.raises(ValidationError):
        add(ctx, request_)


@pytest.mark.parametrize('request_', [transit()], indirect=True)
def test_add(request_):
    resp = add(ctx, request_)
    assert request_.db[ctx].find_one({'_id': ObjectId(resp['data'][0])})


@pytest.mark.parametrize('request_', [transit(_id=1)], indirect=True)
def test_save_bad(request_):
    with pytest.raises(ValidationError):
        save(ctx, request_)


@pytest.mark.parametrize('request_', [transit(_id=ObjectId())], indirect=True)
def test_save(request_):
    request_.db.transactions.insert_one(
        {'_id': ObjectId(request_.json_payload['data']['_id']), 'shop': {'id': '40'}}
    )
    resp = save(ctx, request_)
    t = request_.db.transactions.find_one({'_id': ObjectId(resp['data'][0])})
    assert t['shop']['id'] != 40
