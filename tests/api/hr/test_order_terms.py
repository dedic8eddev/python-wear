import uuid

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

USERNAME = 'user1'
USERNAME_2 = 'user2'
USERNAME_ADMIN = 'admin'
PASSWORD = '0' * 10
USER_ID = ObjectId()
TENANT_ID = '1'
TENANT_ID_2 = '2'


@pytest.fixture(autouse=True, scope='function')
def login(app, spynl_data_db, monkeypatch):
    monkeypatch.setattr('spynl.api.retail.resources.Sales.is_large_collection', False)

    db = spynl_data_db
    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['sales'], 'settings': {}})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-admin'},
        custom_id=USER_ID,
    )
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    yield db
    spynl_data_db.order_terms.delete_many({})
    app.get('/logout')


def test_save_order_terms_bad_data(app):
    app.post_json(
        '/order-terms/save', {'data': {'orderPreviewText1': None}}, status=400
    )


def test_save_order_terms(app):
    app.post_json(
        '/order-terms/save', {'data': {'orderPreviewText1': 'hello'}}, status=200
    )


def test_save_order_terms_duplicate(app):
    # lang/country will default to 'default'
    app.post_json('/order-terms/save', {'data': {}}, status=200)
    app.post_json('/order-terms/save', {'data': {}}, status=400)


def test_save_order_terms_for_country_that_already_has_it(app):
    payload = {'data': {'orderPreviewText1': 'hello', 'country': 'NL'}}
    payload2 = {'data': {'orderPreviewText1': 'hello', 'country': 'NL'}}
    app.post_json('/order-terms/save', payload, status=200)
    app.post_json('/order-terms/save', payload2, status=400)


def test_filter_by_country(app):
    app.post_json('/order-terms/save', {'data': {'country': 'NL'}}, status=200)
    resp = app.post_json('/order-terms/get', {'filter': {'country': 'NL'}})
    expected = {
        'orderPreviewText1': '',
        'orderPreviewText2': '',
        'orderPreviewText3': '',
        'orderPreviewText4': '',
        'country': 'NL',
    }
    assert len(resp.json['data']) == 1 and all(
        expected[k] == resp.json['data'][0][k] for k in expected
    )


def test_upsert_order_terms(app, spynl_data_db):
    _id = uuid.uuid4()
    raw_order = {'data': {'_id': str(_id), 'country': 'NL'}}
    app.post_json('/order-terms/save', raw_order, status=200)
    order = spynl_data_db.order_terms.find_one({'_id': _id})
    raw_order['data']['orderPreviewText1'] = 'a'
    app.post_json('/order-terms/save', raw_order, status=200)
    order_modified = spynl_data_db.order_terms.find_one({'_id': _id})

    assert (
        all(
            order[k] == order_modified[k]
            for k in order
            if k not in ['modified', 'modified_history', 'orderPreviewText1']
        )
        and order_modified['orderPreviewText1'] == 'a'
        and order['orderPreviewText1'] == ''
    )


def test_remove_order_terms(app, spynl_data_db):
    resp = app.post_json('/order-terms/save', {'data': {}}, status=200)
    c = spynl_data_db.order_terms.count()
    app.post_json(
        '/order-terms/remove', {'filter': {'_id': resp.json['data'][0]}}, status=200
    )
    c2 = spynl_data_db.order_terms.count()
    assert c == 1 and c2 == 0


def test_remove_order_terms_non_existing(app, spynl_data_db):
    app.post_json(
        '/order-terms/remove', {'filter': {'_id': str(uuid.uuid4())}}, status=400
    )
