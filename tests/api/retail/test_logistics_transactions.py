import uuid
from collections import Counter

import pytest

from spynl.api.auth.testutils import mkuser

TENANT_ID = '1'


@pytest.fixture(autouse=True)
def setup(spynl_data_db, app):
    spynl_data_db.tenants.insert_one(
        {'_id': '1', 'applications': ['logistics'], 'settings': {}}
    )
    mkuser(
        spynl_data_db.pymongo_db,
        'username',
        'password',
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'logistics-inventory_user'},
    )

    docs = [
        {
            '_id': uuid.uuid4(),
            'supplierOrderReference': str(i),
            'orderNumber': str(i + 20),
            'warehouseId': '40' if i % 2 else '41',
            'tenant_id': [TENANT_ID] if i % 2 else '2',
            'status': 'complete' if i % 2 else 'draft',
            'active': True,
        }
        for i in range(20)
    ]
    spynl_data_db.inventory.insert_many(docs)
    spynl_data_db.receivings.insert_many(docs)
    spynl_data_db.warehouses.insert_many(
        [{'_id': '40', 'name': 'Amsterdam'}, {'_id': '41', 'name': 'Rotterdam'}]
    )
    yield


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_no_type(login, app):
    response = app.post_json('/logistics-transactions/get', status=200)
    data = response.json['data']
    assert len(data) == 20
    types = Counter()
    for d in data:
        types[d['type']] += 1
    assert types == {'receivings': 10, 'inventory': 10}


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_inventory(login, app):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'type': 'inventory'}}, status=200
    )
    data = response.json['data']
    assert len(data) == 10
    assert all([d['type'] == 'inventory' for d in data])


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_receiving(login, app):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'type': 'receivings'}}, status=200
    )
    data = response.json['data']
    assert len(data) == 10
    assert all([d['type'] == 'receivings' for d in data])


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_warehouseName(login, app):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'type': 'receivings'}}, status=200
    )
    data = response.json['data']
    assert all([d['warehouseName'] == 'Amsterdam' for d in data])


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_sorting(login, app):
    response = app.post_json('/logistics-transactions/get', status=200)
    data = response.json['data']
    assert all(
        data[i]['modified']['date'] <= data[i + 1]['modified']['date']
        for i in range(len(data) - 1)
    )


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_projection(login, app, spynl_data_db):
    _id = str(spynl_data_db.receivings.find_one({'tenant_id': TENANT_ID})['_id'])
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'_id': _id}}, status=200
    )
    data = response.json['data']
    assert 'warehouseName' in data[0]
    assert 'warehouse' not in data[0]
    assert 'type' in data[0]


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_query_status(login, app, spynl_data_db):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'status': 'complete'}}, status=200
    )
    data = response.json['data']
    assert all([d['status'] == 'complete' for d in data])

    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'status': 'draft'}}, status=200
    )
    data = response.json['data']
    assert all([d['status'] == 'draft' for d in data])


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_query_supplier_order_ref(login, app, spynl_data_db):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'text': '5'}}, status=200
    )
    data = response.json['data']
    assert len(data) == 2
    assert all(d['supplierOrderReference'] == '5' for d in data)


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_query_ordernumber(login, app, spynl_data_db):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'text': '25'}}, status=200
    )
    data = response.json['data']
    assert len(data) == 2
    assert all(d['orderNumber'] == '25' for d in data)


@pytest.mark.parametrize('login', [('username', 'password')], indirect=True)
def test_query_warehouse(login, app, spynl_data_db):
    response = app.post_json(
        '/logistics-transactions/get', {'filter': {'text': '40'}}, status=200
    )
    data = response.json['data']
    assert len(data) == 20
    assert all(d['warehouseName'] == 'Amsterdam' for d in data)
