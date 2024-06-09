# -*- coding: utf-8 -*-
"""Tests for password resets and password change."""

import time
from copy import deepcopy
from uuid import uuid4

import pytest
from bson import ObjectId

from spynl.api.auth.authentication import scramble_password
from spynl.api.auth.keys import store_key
from spynl.api.auth.utils import app_url

USERID = ObjectId()
USER = {
    '_id': USERID,
    'email': 'blahuser@blah.com',
    'fullname': 'User Usertön',
    'password_hash': scramble_password('blah', 'blah', '2'),
    'password_salt': 'blah',
    'hash_type': '2',
    'active': True,
    'tenant_id': ['tenant1'],
    'username': 'blahuser',
}

USER_NOEMAIL = deepcopy(USER)
USER_NOEMAIL['username'] = 'user_noemail'
del USER_NOEMAIL['email']
del USER_NOEMAIL['_id']


TOWNER = {
    'email': 'towner@blah.com',
    'fullname': 'Owen Tenant',
    'password_hash': scramble_password('blah', 'blah', '2'),
    'password_salt': 'blah',
    'hash_type': '2',
    'active': True,
    '_id': 'towner',
    'tenant_id': ['tenant1'],
    'username': 'towner',
}


class DUMMY_REQUEST:
    def __init__(self, application_url):
        self.application_url = application_url


@pytest.fixture(autouse=True)
def set_db(db):
    """Add 1 tenant and 1 user before every test runs."""
    db.tenants.insert_one(
        {'_id': 'tenant1', 'name': 'Tenant Eins', 'owners': ['towner']}
    )
    db.users.insert_one(TOWNER)
    db.users.insert_one(USER)
    db.users.insert_one(USER_NOEMAIL)


@pytest.fixture()
def add_sessions(db):
    """
    Add multiple sessions for USER to the database, to simulate being logged in
    on multiple devices.
    """
    session = {
        '_created': time.time(),
        '_remember_me': False,
        'spynl_version': '6.0.0',
        'username': USER['username'],
        'auth___userid': USERID,
        'tenant_id': 'tenant1',
    }
    for _ in range(5):
        session['_id'] = uuid4().hex
        db.spynl_sessions.insert_one(session)


def test_request_pwd_reset_by_passing_empty_username(app):
    """The argument 'username' is required."""
    response = app.get('/request-pwd-reset?username=', expect_errors=True)
    assert response.json['type'] == 'CannotRetrieveUser'


def test_request_pwd_reset_passing_wrong_email(app):
    """Test invalid emails."""
    # non-existing email
    response = app.get('/request-pwd-reset?username=xx@email.com', expect_errors=True)
    assert 'Requested user cannot be found' in response.json['message']
    # existing email plus extra chars
    response = app.get(
        '/request-pwd-reset?username=XX{}'.format(USER['email']), expect_errors=True
    )
    assert 'Requested user cannot be found' in response.json['message']


def test_request_pwd_reset_that_email_sent_has_the_reset_key(db, app, mailer_outbox):
    """Ensure mail has reset_key when requesting password reset."""
    response = app.get(
        '/request-pwd-reset?username={}'.format(USER['email']), status=200
    )
    assert (
        "A reset link has been sent to the email registered to this " "account"
    ) in response.json['message']
    # look up mail (only file in folder for this test)
    db_user = db.users.find_one({'email': USER['email']})
    assert db_user['keys']['pwd_reset']['key'] in mailer_outbox[0].body.data


def test_request_pwd_reset_creates_value_for_reset_key(db, app):
    """Request password reset and ensure reset_key has a value."""
    app.get('/request-pwd-reset?username={}'.format(USER['email']), status=200)
    db_user = db.users.find_one({'email': USER['email']})
    assert db_user['keys']['pwd_reset']['key'] != ''
    assert len(db_user['keys']['pwd_reset']['key']) == 25


def test_request_pwd_reset_by_user_without_email_address(app, mailer_outbox):
    """
    Some users don't have an email address, the reset code should go to the
    owners then.
    """
    response = app.get(
        '/request-pwd-reset?username={}'.format(USER_NOEMAIL['username']), status=200
    )
    assert (
        "A reset link has been sent to the email registered to this " "account"
    ) in response.json['message']
    assert mailer_outbox[0].recipients == [TOWNER['email']]


def test_request_pwd_reset_using_str_template(db, app, mailer_outbox):
    """Test handling of the template if it contains str."""
    response = app.get(
        '/request-pwd-reset?username={}'.format(USER['email']), status=200
    )
    assert (
        "A reset link has been sent to the email registered to this " "account"
    ) in response.json['message']
    # look up mail (only file in folder for this test)
    db_user = db.users.find_one({'email': USER['email']})
    new_key = db_user['keys']['pwd_reset']['key']
    assert new_key in mailer_outbox[0].body.data
    assert 'Hello {}'.format(db_user['fullname']) in mailer_outbox[0].body.data
    assert new_key in mailer_outbox[0].body.data


def test_successful_reset_password_that_reset_key_gets_empty(db, app):
    """After a successful password reset reset_key has to be empty string."""
    app.get('/request-pwd-reset?username={}'.format(USER['email']), status=200)
    db_user = db.users.find_one({'email': USER['email']})
    response = app.get(
        '/reset-pwd?username={email}&key={key}&pwd1={pwd}&pwd2={pwd}'.format(
            email=USER['email'],
            key=db_user['keys']['pwd_reset']['key'],
            pwd='new-pwd-12',
        ),
        status=200,
    )
    assert 'Password has been set' in response.json['message']

    db_updated_user = db.users.find_one({'email': USER['email']})
    assert db_updated_user['keys']['pwd_reset']['key'] is None
    # Revert password change for next tests.
    result = db.users.update_one(
        {'email': USER['email']},
        {
            '$set': {
                'password_hash': scramble_password('blah', 'blah', '2'),
                'password_salt': 'blah',
            }
        },
    )
    assert result.matched_count == 1
    assert not result.upserted_id


def test_reset_password_by_passing_wrong_key_arg(db, app, config, spynl_data_db):
    """Update user's reset_key and request pwd reset with different key."""
    db_user = db.users.find_one({'email': USER['email']})
    store_key(spynl_data_db, db_user['_id'], 'pwd_reset', 3600)
    response = app.get(
        '/reset-pwd?username={}&key=GGG&pwd1={}&pwd2={}'.format(
            USER['email'], '_', '__'
        ),
        expect_errors=True,
    )
    assert response.json['type'] == 'Forbidden'
    assert 'not a valid key' in response.json['message']


def test_reset_password_by_passing_previous_key_arg(db, app, config, spynl_data_db):
    """Update user's reset_key and request pwd reset with different key."""
    db_user = db.users.find_one({'email': USER['email']})
    key = store_key(spynl_data_db, db_user['_id'], 'pwd_reset', 3600)
    store_key(spynl_data_db, db_user['_id'], 'pwd_reset', 3600)
    response = app.get(
        '/reset-pwd?username={}&key={}&pwd1={}&pwd2={}'.format(
            USER['email'], key, '_', '_'
        ),
        expect_errors=True,
    )
    assert response.json['type'] == 'Forbidden'
    assert 'key has expired' in response.json['message']


def test_reset_password_when_pwd1_is_different_than_pwd2(
    db, app, config, spynl_data_db
):
    """Test when pwd1 does not match with pwd2."""
    db_user = db.users.find_one({'email': USER['email']})
    key = store_key(spynl_data_db, db_user['_id'], 'pwd_reset', 3600)
    response = app.get(
        '/reset-pwd?username={}&key={}&pwd1=ddd&pwd2=eee'.format(USER['email'], key),
        expect_errors=True,
    )
    assert response.json['type'] == 'Forbidden'
    assert 'does not match' in response.json['message']


def test_reset_pwd_too_short(db, app, config, spynl_data_db):
    """New password is too short."""
    db_user = db.users.find_one({'email': USER['email']})
    key = store_key(spynl_data_db, db_user['_id'], 'pwd_reset', 3600)
    response = app.get(
        '/reset-pwd?username={}&key={}&pwd1=&pwd2='.format(USER['email'], key),
        expect_errors=True,
    )
    assert 'password should be at least 10 characters' in response.json['message']


@pytest.mark.parametrize(
    'password',
    [
        'non_asccii_ö',  # check 1 non ascii
        '_spa ce___',  # check 2 words with space
        'non_asccii_ψ',  # check another ascii
        'öψ€®∞ℜØ¶ab',  # full of non ascii chars
        'right_space ',  # ending space
        ' left_space',  # starting space
        ' __spaces__ ',  # ending + starting space
        ' ' * 10,  # use 10 to bypass validation
    ],
)
def test_reset_pwd_weird_characters(db, app, password):
    """Resetting password using non ascii characters should be allowed."""
    app.get('/request-pwd-reset?username={}'.format(USER['email']), status=200)
    user = db.users.find_one({'email': USER['email']})

    # any spaces will be stripped while getting the arguments from the request
    password = password.strip()
    params = dict(
        username=user['email'],
        key=user['keys']['pwd_reset']['key'],
        pwd1=password,
        pwd2=password,
    )
    if password == '':  # empty password is of course forbidden
        app.get('/reset-pwd', params, status=403)
    else:
        app.get('/reset-pwd', params, status=200)

        expected_password = scramble_password(
            password, user['password_salt'], user['hash_type']
        )
        updated_user = db.users.find_one({'email': user['email']})
        assert updated_user['password_hash'] == expected_password


def test_reset_pwd_remove_all_sessions(db, app, add_sessions):
    """
    when the pwd is reset, any sessions of the user should be removed,
    even a 'current' session if the user is logged in."""
    # make a 'current' session and request pwd reset:
    app.get('/login?username={}&password=blah'.format(USER['email']), status=200)
    app.get('/request-pwd-reset?username={}'.format(USER['email']), status=200)
    # reset pwd and make sure sessions are removed
    db_user = db.users.find_one({'email': USER['email']})
    app.get(
        '/reset-pwd?username={email}&key={key}&pwd1={pwd}&pwd2={pwd}'.format(
            email=USER['email'],
            key=db_user['keys']['pwd_reset']['key'],
            pwd='new-pwd-12',
        ),
        status=200,
    )
    session = db.spynl_sessions.find_one({'auth___userid': USERID})
    assert not session


@pytest.mark.parametrize('login', [(USER['username'], 'blah')], indirect=True)
def test_change_pwd_invalid_current_pwd(app, login):
    """Pass wrong current password when requesting password change."""
    payload = dict(pwd1='a', pwd2='a', current_pwd='wronggg')
    response = app.post_json('/change-pwd', payload, expect_errors=True)
    assert 'current password is not correct' in response.json['message']


@pytest.mark.parametrize('login', [(USER['username'], 'blah')], indirect=True)
def test_change_pwd_unmatching_new_pwds(app, login):
    """Pass different pwd1 and pwd2 when requesting password reset."""
    payload = dict(pwd1='a', pwd2='b', current_pwd='blah')
    response = app.post_json('/change-pwd', payload, expect_errors=True)
    assert 'Confirmation password does not match' in response.json['message']


@pytest.mark.parametrize('login', [(USER['username'], 'blah')], indirect=True)
def test_change_pwd_too_short(app, login):
    """New password is too short."""
    payload = dict(pwd1='', pwd2='', current_pwd='blah')
    response = app.post_json('/change-pwd', payload, expect_errors=True)
    assert 'password should be at least 10 characters' in response.json['message']


@pytest.mark.parametrize('login', [(USER['username'], 'blah')], indirect=True)
def test_change_pwd(app, db, mailer_outbox, login):
    """Test a successful password change."""
    # Ensure tenant1 was set
    app.get('/set-tenant?id={}'.format(USER['tenant_id'][0]), status=200)

    db.spynl_audit_log.delete_many({})
    payload = dict(pwd1='beelzebub1', pwd2='beelzebub1', current_pwd='blah')
    response = app.post_json('/change-pwd', payload, status=200)
    assert 'Password has been changed successfully' in response.json['message']

    assert mailer_outbox[0]
    assert USER['fullname'] in mailer_outbox[0].body.data
    assert "assword" in mailer_outbox[0].subject
    assert "change" in mailer_outbox[0].subject
    assert mailer_outbox[0].recipients == [USER['email']]
    aulog = db.spynl_audit_log.find_one({})
    assert 'Attempt to change password' in aulog['message']
    # update user with his previous password for the rest of the tests
    db.users.update_one(
        {'email': USER['email']}, {'$set': {'password_hash': USER['password_hash']}}
    )


@pytest.mark.parametrize('login', [(USER['username'], 'blah')], indirect=True)
def test_change_pwd_removes_other_sessions(db, app, login, add_sessions):
    """
    when pwd is changed, all sessions except for the current one should
    be removed.
    """
    payload = dict(pwd1='beelzebub1', pwd2='beelzebub1', current_pwd='blah')
    app.post_json('/change-pwd', payload, status=200)
    sessions = list(db.spynl_sessions.find({'username': USER['username']}))
    assert len(sessions) == 1
    assert sessions[0]['_id'] == login['sid']


@pytest.mark.parametrize('login', [(USER['username'], 'blah')], indirect=True)
@pytest.mark.parametrize(
    'password',
    [
        'non_asccii_ö',  # check 1 non ascii
        '_spa ce___',  # check 2 words with space
        'non_asccii_ψ',  # check another ascii
        'öψ€®∞ℜØ¶ab',  # full of non ascii chars
        'right_space ',  # ending space
        ' left_space',  # starting space
        ' __spaces__ ',  # ending + starting space
    ],
)
def test_change_pwd_using_non_ascii_weird_characters(db, app, password, login):
    """Users should be able to user passwords with 'weird'/non ascii chars."""
    password = password.strip()
    payload = dict(pwd1=password, pwd2=password, current_pwd='blah')
    app.post_json('/change-pwd', payload, status=200)

    expected_password = scramble_password(
        password, USER['password_salt'], USER['hash_type']
    )
    user = db.users.find_one(dict(email=USER['email']))
    assert user['password_hash'] != USER['password_hash']
    assert user['password_hash'] == expected_password
    # update user with his previous password for the rest of the tests
    db.users.update_one(
        {'email': USER['email']}, {'$set': {'password_hash': USER['password_hash']}}
    )


@pytest.mark.parametrize(
    'login',
    [(USER_NOEMAIL['username'], 'blah', dict(tenant_id='tenant1'))],
    indirect=True,
)
def test_change_pwd_user_has_no_email_so_send_to_owner(app, mailer_outbox, login):
    """Test a successful password change where we send the email to the owner"""
    payload = dict(pwd1='beelzebub1', pwd2='beelzebub1', current_pwd='blah')
    app.post_json('/change-pwd', payload, status=200)
    assert mailer_outbox[0]
    assert USER_NOEMAIL['fullname'] in mailer_outbox[0].body.data
    assert mailer_outbox[0].recipients == [TOWNER['email']]
    app.get('/logout', status=200)


def test_app_url():
    spynl = DUMMY_REQUEST('http://spynl.softwearconnect.lc')
    admin = DUMMY_REQUEST('http://admin.softwearconnect.lc')
    test = DUMMY_REQUEST('http://test.softwearconnect.lc')
    other_domain = DUMMY_REQUEST('http://spynl.hakuna.matata')

    assert app_url(spynl, "spynl") == "http://www.softwearconnect.lc/www.html#"
    assert app_url(admin, "admin") == "http://www.softwearconnect.lc/admin.html#"
    assert app_url(test, "test") == "http://www.softwearconnect.lc/test.html#"
    assert app_url(other_domain, "spynl") == "http://www.hakuna.matata/www.html#"
