"""
Logging tests for logging as implemented in spynl.mongo, but that rely on having
a logged in user.
"""

import logging

import pytest

from spynl.api.auth.authentication import scramble_password


@pytest.fixture(autouse=True)
def set_db(db):
    """Fill database with data for tests to use."""
    db.tenants.insert_one(
        {
            'active': True,
            '_id': 'test_tenant',
            'name': 'tenant 1',
            'applications': ['pos'],
        }
    )
    db.users.insert_one(
        {
            'username': 'user-logtest',
            'name': 'User Logtest',
            'email': 'user-logtest@email.com',
            'roles': {'test_tenant': {'tenant': ['pos-device']}},
            'active': True,
            'hash_type': '1',
            'password_hash': scramble_password('12341234', '', '1'),
            'password_salt': '',
            'tenant_id': ['test_tenant'],
        }
    )


def test_log_login(app, caplog):
    """Test the log when log in."""
    caplog.set_level(logging.DEBUG)
    app.post_json('/login?username=user-logtest&password=12341234')
    app.post_json('/set-tenant?id=test_tenant')
    # new session, login request, session lookup, set tenant request
    # set tenant remove session, set tenant new session
    assert len(caplog.records) == 6
    assert caplog.records[0].meta['url'].endswith('login')
    assert caplog.records[0].payload['username'] == 'user-logtest'
    assert caplog.records[0].payload['password'] == '*********'
    assert caplog.records[1].msg.startswith('New session init')
    assert caplog.records[2].meta['url'].endswith('set-tenant')
    assert caplog.records[2].payload['id'] == 'test_tenant'
    assert 'Looked up existing session' in caplog.records[3].msg


@pytest.mark.parametrize(
    'login',
    [('user-logtest', '12341234', dict(tenant_id='test_tenant'))],
    indirect=True,
)
def test_log_db_get_query(app, login, caplog):
    """Test logging a db query."""
    caplog.set_level(logging.DEBUG)
    app.post_json(
        '/test/get', {'sid': login['sid'], 'filter': {'no': 'idea'}}, status=200
    )
    # /get (request, session lookup, data query)
    assert len(caplog.records) == 3
    assert caplog.records[2].payload['filter']['no'] == 'idea'
    assert 'execution_time' in caplog.records[2].meta


@pytest.mark.parametrize(
    'login',
    [('user-logtest', '12341234', dict(tenant_id='test_tenant'))],
    indirect=True,
)
def test_log_db_remove_query(app, login, caplog):
    """Test logging a db query that removes a document."""
    caplog.set_level(logging.DEBUG)
    app.get(
        '/test/remove?filter={{testname:blabla}}&sid={}'.format(login['sid']),
        status=200,
    )
    assert 'MongoDB' in caplog.records[2].msg


@pytest.mark.parametrize(
    'login',
    [('user-logtest', '12341234', dict(tenant_id='test_tenant'))],
    indirect=True,
)
def test_error(app, login, caplog):
    """Test logging when theres an error."""
    caplog.set_level(logging.ERROR)
    response = app.post_json('/test/agg', {'filter': 13}, status=404)
    assert 'No endpoint found for path' in response.json['message']

    assert len(caplog.records) == 1
    assert 'raise PredicateMismatch' in caplog.records[0].meta['err_source']['src_code']
    assert caplog.records[0].meta['user']['username'] == 'user-logtest'
