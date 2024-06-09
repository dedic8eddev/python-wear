"""Tests for user sessions."""


import pytest
from pyramid import testing

from spynl.main.version import __version__ as spynl_version

from spynl.api.auth.authentication import scramble_password
from spynl.api.auth.session_authentication import rolefinder
from spynl.api.auth.testutils import mkuser

# not interested in authentication here, so all test users have the same pwd
pwd = 'pustekuchen'


@pytest.fixture(autouse=True)
def set_db(db):
    """Fill database with data for tests to use."""
    db.tenants.insert_one({'_id': 'unittest_tenant', 'name': 'tenant 1'})
    db.users.insert_one(
        {
            'email': 'user1@email.com',
            'username': 'user1',
            'hash_type': '1',
            'password_hash': scramble_password('12341234', '', '1'),
            'password_salt': '',
            'active': True,
            'tz': 'Europe/Amsterdam',
            'tenant_id': ['unittest_tenant'],
        }
    )

    db.tenants.insert_one(
        {'_id': 'inactive_tenant_id', 'name': 'I. Tenant', 'active': False}
    )
    db.tenants.insert_one(
        {
            '_id': 'a_tenant_id',
            'name': 'A. Tenant',
            'applications': ['pos', 'dashboard'],
        }
    )
    db.tenants.insert_one(
        {
            '_id': 'another_tenant_id',
            'name': 'A.N. Tenant',
            'applications': ['pos', 'reporting'],
        }
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})

    mkuser(db, 'poor_user', pwd, ['inactive_tenant_id'], tenant_roles={})
    mkuser(
        db,
        'dummy_user',
        pwd,
        ['a_tenant_id', 'another_tenant_id'],
        tenant_roles={
            'a_tenant_id': ['pos-device', 'dashboard-user'],
            'another_tenant_id': ['dashboard-user'],
        },
        def_app={'a_tenant_id': 'pos', 'another_tenant_id': 'reporting'},
        owns=['another_tenant_id'],
    )
    mkuser(
        db, 'master_user', pwd, ['master'], tenant_roles={'master': ['sw-servicedesk']}
    )
    mkuser(
        db, 'developer_user', pwd, ['master'], tenant_roles={'master': ['sw-developer']}
    )
    mkuser(
        db,
        'unsupported_user',
        pwd,
        ['a_tenant_id'],
        tenant_roles={'a_tenant_id': ['pos-unknown', 'dashboard-user']},
    )


@pytest.mark.parametrize('login', [('user1', '12341234')], indirect=True)
def test_session_create(db, login):
    """Test session create when login."""
    data = db.spynl_sessions.find_one({'_id': login['sid']})
    # auth___userid should exist if user authenticated
    assert 'auth___userid' in data
    assert '_expire' in data
    # Tenant Id should exist after set-tenant called
    assert data['tenant_id'] == 'unittest_tenant'
    # Remember me should be False by default
    assert not data['_remember_me']
    assert data['spynl_version'] == spynl_version


@pytest.mark.parametrize(
    'login', [('user1', '12341234', dict(remember_me=True))], indirect=True
)
def test_session_remember_me(db, app, login):
    """Test when <remember me> is True."""
    data = db.spynl_sessions.find_one({'_id': login['sid']})
    assert data['_remember_me']


@pytest.mark.parametrize(
    'login', [('user1', '12341234', dict(remember_me=False))], indirect=True
)
def test_session_remember_me_false_default(db, app, login):
    """Test explicit remember_me=False."""
    data = db.spynl_sessions.find_one({'_id': login['sid']})
    assert not data['_remember_me']


@pytest.mark.parametrize(
    'login', [('user1', '12341234', dict(remember_me=True))], indirect=True
)
def test_change_remember_me(db, app, login):
    """
    Test user stays logged in and logs in again now with remember_me False
    """
    params = dict(username='user1', password='12341234', remember_me=False)
    response = app.get('/login', params, status=200)
    data = db.spynl_sessions.find_one({'_id': response.json['sid']})
    assert not data['_remember_me']


def test_rolefinder(spynl_data_db, db, set_db, config):
    """test if rolefinder returns expected roles"""
    # this test has nothing to do with principles so remove them.
    def rolefinder_(*args, **kwargs):
        rv = rolefinder(*args, **kwargs)
        # test if item is string to filter out Principals
        return [item for item in rv if isinstance(item, str)]

    drequest = testing.DummyRequest(
        remote_addr='dummy_ip',
        current_tenant_id='a_tenant_id',
        requested_tenant_id='a_tenant_id',
        endpoint_method='',
    )
    drequest.db = spynl_data_db

    user = db.users.find_one({'username': 'poor_user'})
    roles = rolefinder_(user['_id'], drequest)
    assert len(roles) == 0

    user = db.users.find_one({'username': 'dummy_user'})
    roles = rolefinder_(user['_id'], drequest)
    assert len(roles) == 2
    assert 'role:pos-device' in roles
    assert 'role:dashboard-user' in roles

    drequest.requested_tenant_id = 'another_tenant_id'
    drequest.current_tenant_id = 'another_tenant_id'
    roles = rolefinder_(user['_id'], drequest)
    assert len(roles) == 1
    assert 'role:owner' in roles

    # test master user:
    user = db.users.find_one({'username': 'master_user'})
    drequest.requested_tenant_id = 'another_tenant_id'
    drequest.current_tenant_id = 'master'
    roles = rolefinder_(user['_id'], drequest)
    assert roles == ['role:sw-servicedesk']

    # test master developer user:
    user = db.users.find_one({'username': 'developer_user'})
    drequest.requested_tenant_id = 'another_tenant_id'
    drequest.current_tenant_id = 'master'
    roles = rolefinder_(user['_id'], drequest)
    assert roles == ['role:sw-developer', 'role:spynl-developer']


def test_no_session_for_unauthenticated_requests(app, db):
    """
    Do not save sessions without a user_id
    """
    app.get('/ping')
    assert db.spynl_sessions.count_documents({}) == 0


def test_spynl_developer_role(app):
    """
    Test you can access spynl.main endpoints available for spynl-developer role
    with the sw-developer role.
    """
    params = dict(username='developer_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='master', sid=response.json['sid'])
    app.get('/set-tenant', params)

    assert app.post_json('/about/sleep', {'sleep': 0}, status=200)
