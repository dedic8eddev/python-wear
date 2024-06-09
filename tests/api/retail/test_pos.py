"""Testing endpoints for pos workflow."""

from uuid import uuid4

import pytest
from pymongo import ASCENDING
from pyramid.testing import DummyRequest

from spynl.api.auth.testutils import mkuser
from spynl.api.retail.pos import get_new_pos_instance_id


@pytest.fixture(autouse=True)
def set_db(db):
    """
    Fill in the database with one company, its owner and one employee.

    We are setting up an existing company with one existing user who is
    owner and one existing user who is employee.
    We also note what new user and company names we'll use.
    """
    db.tenants.insert_one(
        {
            '_id': 'existingtenantid',
            'name': 'Old Corp.',
            'active': True,
            'applications': ['account', 'dashboard', 'pos'],
            'owners': ['existing-hans'],
        }
    )
    db.transactions.create_index(
        [
            ('tenant_id', ASCENDING),
            ('type', ASCENDING),
            ('receiptNr', ASCENDING),
            ('device', ASCENDING),
        ]
    )


@pytest.fixture
def request_(spynl_data_db):
    """Return a ready pyramid fake request."""
    request = DummyRequest()
    request.requested_tenant_id = 'existingtenantid'
    request.current_tenant_id = 'existingtenantid'
    request.session = {'auth.userid': 'test_user_id'}
    request.cached_user = None
    request.headers = {'sid': '123123123123'}
    request.db = spynl_data_db
    return request


def test_getting_new_pos_instance_id(db, request_, config):
    """Ensure first(field doesnt even exist) and second time works."""

    def _get_tenant():
        return db.tenants.find_one(dict(_id='existingtenantid'))

    assert 'counters' not in _get_tenant().keys()
    for new_id in range(1, 3):
        get_new_pos_instance_id(request_)
        assert _get_tenant()['counters']['posInstanceId'] == new_id


def test_getting_pos_instance_id_for_non_existent_tenant(db, request_, config):
    """Error should be returned, no tenant should be created in any way."""
    tenants_count_before = db.tenants.count_documents({})
    request_.current_tenant_id = uuid4().hex
    with pytest.raises(Exception) as err:
        get_new_pos_instance_id(request_)
    assert err.type.__name__ == 'TenantDoesNotExist'
    assert db.tenants.count_documents({}) == tenants_count_before


def test_pos_init(app, spynl_data_db):
    tenant_id = '0000'
    username = 'user'
    password = 'password'
    spynl_data_db.tenants.insert_one(
        {'_id': tenant_id, 'applications': ['sales', 'pos'], 'settings': {}}
    )
    mkuser(
        spynl_data_db.pymongo_db,
        username,
        password,
        [tenant_id],
        tenant_roles={tenant_id: ['pos-device']},
        custom_id='1',
    )

    t = []
    for i in range(100):
        t.extend(
            [
                {'device': '1', 'receiptNr': i, 'type': 2, 'tenant_id': tenant_id},
                {'device': '1', 'receiptNr': i, 'type': 9, 'tenant_id': tenant_id},
            ]
        )
    spynl_data_db.transactions.insert_many(t)
    app.get('/login?username=%s&password=%s' % (username, password))
    resp = app.post_json('/pos/init')
    assert resp.json['data'] == {
        'counters': {'consignments': 100, 'sales': 100, 'transits': 1}
    }
