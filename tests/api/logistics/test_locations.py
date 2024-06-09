""" Tests for locations endpoints """
import pytest
from bson import ObjectId

from spynl.api.auth.testutils import login, mkuser

EXISTING_ID = ObjectId()


@pytest.fixture()
def set_db(db):
    """fill the db"""
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    db.tenants.insert_one({'_id': 'a_tenant', 'name': 'A tenant'})
    mkuser(
        db,
        'account_manager',
        'blah',
        ['master'],
        tenant_roles={'master': ['sw-account_manager']},
    )
    mkuser(db, 'admin', 'blah', ['master'], tenant_roles={'master': ['sw-admin']})
    mkuser(
        db,
        'normal_user',
        'blah',
        ['a_tenant'],
        tenant_roles={'a_tenant': ['account-admin']},
    )

    db.warehouses.insert_one(
        {'_id': EXISTING_ID, 'wh': '51', 'tenant_id': ['a_tenant'], 'active': True}
    )
    db.warehouses.insert_one({'wh': '51', 'tenant_id': ['b_tenant'], 'active': True})
    db.warehouses.insert_one({'wh': '52', 'tenant_id': ['b_tenant'], 'active': False})


def test_get(app, set_db):
    login(app, 'normal_user', 'blah')
    response = app.post_json('/locations/get')
    assert len(response.json['data']) == 1


def test_get_master(app, set_db):
    login(app, 'admin', 'blah')
    response = app.post_json('/tenants/a_tenant/locations/get')
    assert len(response.json['data']) == 1
    response = app.post_json('/tenants/b_tenant/locations/get')
    assert len(response.json['data']) == 1


def test_count(app, set_db):
    login(app, 'normal_user', 'blah')
    response = app.post_json('/locations/count')
    assert response.json['count'] == 1


def test_count_master(app, set_db):
    login(app, 'admin', 'blah')
    response = app.post_json('/tenants/a_tenant/locations/count')
    assert response.json['count'] == 1
    response = app.post_json('/tenants/b_tenant/locations/count')
    assert response.json['count'] == 1


def test_succesfull_save_master(app, set_db, db):
    login(app, 'admin', 'blah')
    app.post_json(
        '/tenants/a_tenant/locations/save',
        {'data': {'_id': str(EXISTING_ID), 'wh': '53', 'name': 'location'}},
    )
    wh = db.warehouses.find_one({'_id': EXISTING_ID})
    assert wh['wh'] == '53'
    assert wh['tenant_id'] == ['a_tenant']


def test_succesfull_save_normal_user(app, set_db, db):
    login(app, 'normal_user', 'blah')
    app.post_json(
        '/locations/save',
        {'data': {'_id': str(EXISTING_ID), 'wh': '53', 'name': 'location'}},
    )
    wh = db.warehouses.find_one({'_id': EXISTING_ID})
    # wh will not be changed:
    assert wh['wh'] == '51'


def test_foxpro_event_save(app, set_db, db):
    login(app, 'normal_user', 'blah')
    app.post_json(
        '/locations/save', {'data': {'_id': str(EXISTING_ID), 'name': 'location'}}
    )
    event = db.events.find_one({})
    assert 'locationid__51' in event['fpquery']


def test_save_as_add_not_allowed(app, set_db):
    login(app, 'normal_user', 'blah')
    response = app.post_json(
        '/locations/save', {'data': {'wh': '51', 'name': 'location'}}, status=403
    )
    assert response.json['message'] == 'You are not allowed to add a location this way.'


def test_succesfull_add_master(app, set_db, db):
    login(app, 'account_manager', 'blah')

    app.post_json(
        '/tenants/tenant_b/locations/add',
        {'data': {'wh': '53', 'name': 'new location'}},
    )
    assert db.warehouses.find_one({'wh': '53', 'tenant_id': 'tenant_b'})


def test_foxpro_event_add(app, set_db, db):
    login(app, 'account_manager', 'blah')

    app.post_json(
        '/tenants/tenant_b/locations/add',
        {'data': {'wh': '53', 'name': 'new location'}},
    )

    event = db.events.find_one({})
    assert 'locationid__53' in event['fpquery']
