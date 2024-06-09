import datetime
import uuid

import pytest

from spynl.api.auth.testutils import mkuser


@pytest.fixture(autouse=True, scope='function')
def database_setup(app, spynl_data_db, monkeypatch):
    TENANT_ID = '1'
    USERNAME = 'test_buffer_user'
    PASSWORD = '00000000'

    db = spynl_data_db
    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['sales'], 'settings': {}})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-admin'},
    )
    app.get(f'/login?username={USERNAME}&password={PASSWORD}')
    yield db
    app.get('/logout')


def test_save_empty_buffer(app):
    app.post_json('/delivery-periods/save', {'data': {}}, status=400)


def test_save_and_get_period(app, spynl_data_db):
    period = {
        'label': '1',
        'reservationDate': str(datetime.datetime.utcnow()),
        'fixDate': str(datetime.datetime.utcnow()),
    }
    resp = app.post_json('/delivery-periods/save', {'data': period})
    db_content = list(spynl_data_db.delivery_periods.find())

    assert len(db_content) == 1 and str(db_content[0]['_id']) == resp.json['data'][0]

    resp = app.get('/delivery-periods/get', {'filter': {'_id': resp.json['data'][0]}})
    assert len(resp.json['data']) == 1

    # duplicate
    resp = app.post_json('/delivery-periods/save', {'data': period}, status=400)


def test_delete_period(app, spynl_data_db):
    period = {
        'label': '1',
        'reservationDate': str(datetime.datetime.utcnow()),
        'fixDate': str(datetime.datetime.utcnow()),
    }
    resp = app.post_json('/delivery-periods/save', {'data': period})
    resp = app.post_json(
        '/delivery-periods/remove', {'filter': {'_id': resp.json['data'][0]}}
    )
    assert not spynl_data_db.delivery_periods.count_documents({})


def test_delete_period_other_tenant(app, spynl_data_db):
    period = {
        '_id': uuid.uuid4(),
        'tenant_id': 'other',
        'label': '1',
        'reservationDate': str(datetime.datetime.utcnow()),
        'fixDate': str(datetime.datetime.utcnow()),
    }
    spynl_data_db.delivery_periods.insert_one(period)
    app.post_json(
        '/delivery-periods/remove', {'filter': {'_id': str(period['_id'])}}, status=404
    )
