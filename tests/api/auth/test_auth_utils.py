"""Tests for the functions in the utils."""

from collections import OrderedDict
from datetime import datetime

import pytest
from pyramid.testing import DummyRequest

from spynl.main.exceptions import IllegalAction

from spynl.api.auth.exceptions import CannotRetrieveUser
from spynl.api.auth.testutils import mkuser
from spynl.api.auth.utils import (
    audit_log,
    check_agent_access,
    check_key,
    find_user,
    get_tenant_applications,
    get_tenant_roles,
    is_sales_admin,
    validate_password,
)


@pytest.fixture
def set_db(db):
    """Fill in the database some data for the tests."""
    # this tenant does not have the account app, because it should be added
    # by default
    db.tenants.insert_one(
        {'_id': 'tenant1', 'name': 'BlaTenant', 'applications': ['dashboard']}
    )
    # this user has unkown roles to check that they do not get returned.
    mkuser(
        db,
        'user_with_roles',
        'blah',
        ['tenant1'],
        tenant_roles={'tenant1': ['pos-device', 'reporting-reader', 'account-admin']},
    )


def simple_function(request):
    """A simple function so test functions can test the decorator."""
    pass


def function_with_exception(request):
    """A simple function that raises Exception for tests to use."""
    raise Exception


def test_audit_log_with_arguments_to_be_none(config, db):
    """
    Document shouldnt have message or current user.

    App is passed in order to trigger the creation of the database -> app.
    """
    request = DummyRequest(
        remote_addr='127.0.0.1',
        view_name='simple_function',
        current_tenant_id='_',
        requested_tenant_id='_',
        db=db,
    )
    audit_log(None, None)(simple_function)(request)
    doc = db.spynl_audit_log.find_one()
    assert isinstance(doc['date'], datetime)
    assert doc['action'] == 'simple_function'
    assert doc['remote_ip'] == '127.0.0.1'


def test_audit_log_with_defining_message_only(db, config):
    """Doc should be saved with the message."""
    request = DummyRequest(
        remote_addr='127.0.0.1',
        current_tenant_id='_',
        requested_tenant_id='_',
        args={},
        db=db,
    )
    audit_log("This is a test message.", None)(simple_function)(request)
    doc = db.spynl_audit_log.find_one()
    assert doc['message'] == 'This is a test message.'


def test_audit_log_with_defining_message_and_arguments_to_format(db, config):
    """Ensure brackets is replaced with the request_arg."""
    request = DummyRequest(
        remote_addr='127.0.0.1',
        current_tenant_id='_',
        requested_tenant_id='_',
        args={'username': 'Evagelos'},
        db=db,
    )
    audit_log("Welcome {}.", ['username'])(simple_function)(request)
    doc = db.spynl_audit_log.find_one()
    assert doc['message'] == 'Welcome Evagelos.'


def test_audit_log_with_defining_message_and_multiple_arguments_to_format(db, config):
    """Ensure brackets are replaced with all request_args."""
    request = DummyRequest(
        remote_addr='127.0.0.1',
        current_tenant_id='_',
        requested_tenant_id='_',
        args={'username': 'Evagelos', 'company': 'Softwear'},
        db=db,
    )
    audit_log("Welcome {} to {}.", ['username', 'company'])(simple_function)(request)
    doc = db.spynl_audit_log.find_one()
    assert doc['message'] == 'Welcome Evagelos to Softwear.'


def test_audit_log_by_passing_message_and_a_dictionary_instead_of_list(db, config):
    """Audit log shouldnt fail and save the message."""
    request = DummyRequest(
        remote_addr='127.0.0.1',
        current_tenant_id='_',
        requested_tenant_id='_',
        args={'username': 'Evagelos', 'company': 'Softwear'},
        db=db,
    )
    audit_log("Welcome {} to {}.", {'username': 'some_value'})(simple_function)(request)
    doc = db.spynl_audit_log.find_one()
    assert doc['message'] == 'Welcome {} to {}.'


def test_audit_log_when_exception_happens_in_function_that_is_logging(db, config):
    """Log should be saved even if exception is raised."""
    request = DummyRequest(
        remote_addr='127.0.0.1', requested_tenant_id='_', current_tenant_id='_', db=db
    )
    with pytest.raises(Exception):
        audit_log('Log saved.', None)(function_with_exception)(request)
    doc = db.spynl_audit_log.find_one()
    assert doc
    assert doc['message'] == 'Log saved.'


def test_get_tenant_apps_returns_correct_apps(set_db, db, config):
    """test that you also get the default apps"""
    tenant = db.tenants.find_one({'_id': 'tenant1'})
    applications = get_tenant_applications(tenant)
    assert set(applications) == set(['photos', 'account', 'dashboard'])


def test_get_tenant_roles_only_returns_known_roles(set_db, db, config, spynl_data_db):
    """test that get_tenant_roles only returns known roles"""
    user = db.users.find_one({'username': 'user_with_roles'})
    roles = get_tenant_roles(spynl_data_db, user, 'tenant1')
    assert roles == ['pos-device', 'account-admin']


def test_get_tenant_roles_restrict(set_db, db, config, spynl_data_db):
    """test that get_tenant_roles restricts roles correctly"""
    user = db.users.find_one({'username': 'user_with_roles'})
    roles = get_tenant_roles(spynl_data_db, user, 'tenant1')
    assert roles == ['pos-device', 'account-admin']
    roles = get_tenant_roles(spynl_data_db, user, 'tenant1', restrict=True)
    assert roles == ['account-admin']


@pytest.mark.parametrize(
    'string,error',
    [
        ('12345678', 'password should be at least 10 characters long'),
        (('12345678' * 16) + '1', 'password should be no longer than 128'),
    ],
)
def test_validate_password_function(app, db, string, error, config):
    """Ensure our password requirements are checked."""
    db.popular_passwords.insert_one({'_id': string})
    with pytest.raises(Exception):
        validate_password(string)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({'foo': [900]}, False),
        ({'foo': {'bar': 'tenant_id'}}, False),
        ({'tenant_id': 'foo'}, True),
        ({'foo': {'tenant_id': 'bar'}}, True),
        ({'foo': [{'bar': [900], 'tenant_id': '1'}]}, True),
        (
            {
                'foo': 1,
                'y': [234],
                'foo2': [{'bar': 'blah'}, {'tenant_id': 1}],
                'bar': {'x': 1},
            },
            True,
        ),
        (OrderedDict([('a', [{'foo': 1}]), ('b', {'tenant_id': 'bar'})]), True),
        (OrderedDict([('a', {'foo': 1}), ('b', {'tenant_id': 'bar'})]), True),
    ],
)
def test_find_tenant_ids(payload, expected):
    assert check_key(payload, 'tenant_id') == expected


@pytest.mark.parametrize(
    "roles,tenant_id,expected",
    [
        ([], 'master', True),
        ([], '1', False),
        (['sales-admin'], '1', True),
        (['reporting-admin', 'sales-user'], '1', False),
    ],
)
def test_is_sales_admin(roles, tenant_id, expected, monkeypatch):
    def patched_get_tenant_roles(*args):
        return roles

    monkeypatch.setattr(
        'spynl.api.auth.utils.get_tenant_roles', patched_get_tenant_roles
    )

    class R:
        cached_user = None
        requested_tenant_id = None
        current_tenant_id = tenant_id
        db = None

    assert is_sales_admin(R()) is expected


@pytest.mark.parametrize(
    "is_admin,agent_id,userid,success",
    [(True, 1, 2, True), (True, 1, 1, True), (False, 1, 1, True), (False, 1, 2, False)],
)
def test_check_agent_access(is_admin, agent_id, userid, success, monkeypatch):
    def patched_is_sales_admin(*args):
        return is_admin

    monkeypatch.setattr('spynl.api.auth.utils.is_sales_admin', patched_is_sales_admin)

    class R:
        authenticated_userid = userid

    if success:
        try:
            check_agent_access(agent_id, R())
        except IllegalAction as e:
            pytest.fail(str(e))
    else:
        with pytest.raises(IllegalAction):
            check_agent_access(agent_id, R())


def test_find_user_empty_string(spynl_data_db):
    with pytest.raises(CannotRetrieveUser) as e:
        find_user(spynl_data_db, '')
        assert e.developer_message == 'Username cannot be None or an empty string.'
