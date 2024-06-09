"""Tests for the change_email endpoint."""

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

UID = ObjectId()


@pytest.fixture
def set_db(db):
    """Populate database with data."""
    owner_id = ObjectId()
    db.tenants.insert_one(
        {
            '_id': '91537',
            'name': 'maddoxx',
            'applications': ['inventory'],
            'owners': [owner_id],
        }
    )
    db.tenants.insert_one(
        {
            '_id': '91538',
            'name': 'maddoxe',
            'applications': ['inventory'],
            'owners': [owner_id],
        }
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    mkuser(
        db,
        'Maddoxx',
        'aveen',
        ['91537'],
        tenant_roles={'91537': ['inventory-user']},
        custom_id=UID,
    )
    mkuser(
        db,
        'device',
        'aveen',
        ['91537'],
        tenant_roles={'91537': ['pos-device']},
        user_type='device',
    )

    mkuser(db, 'multipletenants', 'blah', ['91537', '91538'])

    mkuser(
        db,
        'account_manager',
        'blah4',
        ['master'],
        tenant_roles={'master': ['sw-account_manager']},
    )


@pytest.mark.parametrize(
    'payload,message',
    [
        ({}, 'current_pwd'),
        ({'new_email': 'test@test.com'}, 'current_pwd'),
        ({'current_pwd': '1234'}, 'new_email'),
        ({'current_pwd': '1234', 'new_email': None}, 'new_email'),
    ],
)
def test_missing_arguments(app, set_db, payload, message):
    """Ensure email value is None after changing to empty string."""
    app.post_json('/login', {'username': 'Maddoxx@blah.com', 'password': 'aveen'})
    response = app.post_json('/change-email', payload, status=400)
    assert message in response.json['message']


def test_by_passing_email_in_strange_format(app, set_db):
    """Email uses validate_email to check if an email is valid."""
    app.post_json('/login', {'username': 'Maddoxx@blah.com', 'password': 'aveen'})
    payload = {'new_email': 'test_com', 'current_pwd': 'aveen'}
    response = app.post_json('/change-email', payload, status=400)
    assert 'email address does not seem to be valid.' in response.json['message']


@pytest.mark.parametrize('login', [('Maddoxx@blah.com', 'aveen')], indirect=True)
def test_setting_email_to_empty_string_gets_set_to_none(app, set_db, login, db):
    """Ensure email value is None after changing to empty string."""
    payload = {'new_email': '', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)
    assert db.users.find_one({'username': 'Maddoxx'})['email'] is None


@pytest.mark.parametrize('login', [('device', 'aveen')], indirect=True)
def test_setting_email_to_empty_string_if_device_user(app, set_db, login, db):
    """Ensure email value is None after changing to empty string."""
    payload = {'new_email': '', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)
    assert db.users.find_one({'username': 'device'})['email'] is None


@pytest.mark.parametrize('login', [('multipletenants', 'blah')], indirect=True)
def test_setting_email_to_empty_string_if_belongs_to_multiple_tenants(
    app, set_db, login, db
):
    """Ensure email value is None after changing to empty string."""
    payload = {'new_email': '', 'current_pwd': 'blah'}
    app.post_json('/change-email', payload, status=403)


@pytest.mark.parametrize('login', [('Maddoxx@blah.com', 'aveen')], indirect=True)
def test_setting_email_to_empty_string_with_one_tenant(app, set_db, login):
    """When email is set to '' emails should be forward to his tenant."""
    payload = {'new_email': '', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)


def test_setting_email_to_empty_string_with_multiple_tenants(app, set_db, db):
    """It's not allowed due to not knowing to who tenant emails should be forward to."""
    db.tenants.insert_one({'_id': '99999', 'name': 'a second tenant'})
    db.users.update_one({'_id': UID}, {'$push': {'tenant_id': '99999'}})

    app.get('/login', dict(username='Maddoxx@blah.com', password='aveen'))
    payload = {'new_email': '', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=403)


@pytest.mark.parametrize('login', [('Maddoxx@blah.com', 'aveen')], indirect=True)
def test_by_passing_wrong_password_with_email(app, set_db, db, login):
    """Pass a wrong password when request changing email address."""
    payload = {'new_email': 'test@test.com', 'current_pwd': 'wrong_pwd'}
    response = app.post_json('/change-email', payload, status=403)
    assert response.json['type'] == 'Forbidden'


@pytest.mark.parametrize('login', [('Maddoxx@blah.com', 'aveen')], indirect=True)
def test_by_passing_wrong_password_with_username(app, set_db, db, login):
    """Pass a wrong password when request changing email address."""
    db.users.update_one({'_id': UID}, {'$set': {'username': 'maddoxx'}})
    payload = {'new_email': 'test@test.com', 'current_pwd': 'wrong_pwd'}
    response = app.post_json('/change-email', payload, status=403)
    assert response.json['type'] == 'Forbidden'


@pytest.mark.parametrize('login', [('Maddoxx@blah.com', 'aveen')], indirect=True)
def test_when_new_email_is_associated_with_other_account(set_db, db, app, login):
    """When changing email the new one must be unique."""
    db.users.insert_one({'email': 'bla@test.com'})
    payload = {'new_email': 'bla@test.com', 'current_pwd': 'aveen'}
    response = app.post_json('/change-email', payload, expect_errors=True)
    assert response.json['type'] == 'Forbidden'


@pytest.mark.parametrize(
    'login', [('Maddoxx', 'aveen', dict(tenant_id='91537'))], indirect=True
)
def test_change_email(set_db, app, db, mailer_outbox, login):
    """
    Successful change of email.
    Check artifacts: audit_log and emails.
    """
    db.spynl_audit_log.delete_many({})
    payload = {'new_email': 'bla+1@test.com', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)
    aulog = db.spynl_audit_log.find_one()
    assert (
        'Email address requested to be changed to <bla+1@test.com>' in aulog['message']
    )
    # notification email
    assert mailer_outbox[0]
    assert mailer_outbox[0].recipients == ['Maddoxx@blah.com']
    # confirmation email
    assert mailer_outbox[1]
    assert mailer_outbox[1].recipients == ['bla+1@test.com']


@pytest.mark.parametrize(
    'login', [('Maddoxx', 'aveen', dict(tenant_id='91537'))], indirect=True
)
def test_when_current_email_empty_and_change_to_new_one(set_db, app, db, login):
    """
    When current email is empty, it should be updated with the new one.

    Scanners dont have email addresses, maybe a tenant wants to add one.
    """
    db.users.update_one({'_id': UID}, {'$set': {'email': ''}})
    payload = {'new_email': 'bla@test.com', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)


@pytest.mark.parametrize('login', [('Maddoxx@blah.com', 'aveen')], indirect=True)
def test_that_generated_key_is_saved(set_db, app, db, login):
    """
    When changing email a key is generated and saved in user's document.

    Check that also email has changed and the old one was saved in the
    oldEmails array.
    """
    user_before = db.users.find_one({'_id': UID})
    assert 'email_verify_pending' not in user_before
    assert user_before['email'] == 'Maddoxx@blah.com'

    payload = {'new_email': 'test@test.com', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)
    user_after = db.users.find_one({'_id': UID})
    assert user_after['keys']['email-verification']['key']
    assert user_after['email'] == 'test@test.com'
    assert user_after['oldEmails'] == ['Maddoxx@blah.com']


@pytest.mark.parametrize('login', [('account_manager', 'blah4')], indirect=True)
def test_change_email_account_manager(set_db, app, db, mailer_outbox, login):
    """
    Successful change of email.
    Check artifacts: audit_log and emails.
    """
    db.spynl_audit_log.delete_many({})
    payload = {'new_email': 'bla+2@test.com', 'username': 'Maddoxx'}
    app.post_json('/account-manager/change-email', payload, status=200)
    aulog = db.spynl_audit_log.find_one()
    assert (
        'Email address requested to be changed to <bla+2@test.com>' in aulog['message']
    )
    # notification email
    assert mailer_outbox[0]
    assert mailer_outbox[0].recipients == ['Maddoxx@blah.com']
    # confirmation email
    assert mailer_outbox[1]
    assert mailer_outbox[1].recipients == ['bla+2@test.com']


@pytest.mark.parametrize('login', [('account_manager', 'blah4')], indirect=True)
def test_change_email_account_manager_nonexistent_user(set_db, app, login):
    payload = {'new_email': 'bla+2@test.com', 'username': 'does_not_exist'}
    app.post_json('/account-manager/change-email', payload, status=400)
