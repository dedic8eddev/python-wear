"""Tests for endpoing resend_email_verification."""

import pytest

from spynl.api.auth.authentication import scramble_password


@pytest.fixture
def set_db(db):
    """Populate database with data."""
    db.tenants.insert_one({'_id': '91537'})
    db.users.insert_one(
        {
            'username': 'maddoxx.aveen',
            'email': 'maddoxx.aveen@softwear.nu',
            'fullname': 'Maddoxx Aveen',
            'tenant_id': ['91537'],
            'password_hash': scramble_password('aveen', 'aveen', '2'),
            'password_salt': 'aveen',
            'hash_type': '2',
            'active': True,
        }
    )


@pytest.mark.parametrize('login', [('maddoxx.aveen', 'aveen')], indirect=True)
def test_when_theres_no_email_verify_pending_field_in_user_doc(set_db, app, login):
    """If field doesnt exist, resending email should be forbidden."""
    response = app.post('/resend-email-verification-key', status=403)
    assert response.json['message'] == 'Account does not require verification.'


@pytest.mark.parametrize('login', [('maddoxx.aveen', 'aveen')], indirect=True)
def test_when_email_verify_pending_field_in_user_doc_is_empty(set_db, app, login):
    """If field is empty, resending email should be forbidden."""
    response = app.post('/resend-email-verification-key', status=403)
    assert response.json['message'] == 'Account does not require verification.'


@pytest.mark.parametrize('login', [('maddoxx.aveen', 'aveen')], indirect=True)
def test_when_email_verify_pending_field_in_user_doc_is_false(set_db, app, login):
    """If field is False, resending email should be forbidden."""
    response = app.post('/resend-email-verification-key', status=403)
    assert response.json['message'] == 'Account does not require verification.'


@pytest.mark.parametrize('login', [('maddoxx.aveen', 'aveen')], indirect=True)
def test_change_and_verify_email_end_to_end(set_db, app, db, login, mailer_outbox):
    """
    Test a full cycle through changing the email, resending the key and
    verifying it.
    """
    # change email
    payload = {'new_email': 'test@test.com', 'current_pwd': 'aveen'}
    app.post_json('/change-email', payload, status=200)
    user = db.users.find_one({'username': 'maddoxx.aveen'})
    assert user['email_verify_pending'] is True
    key_1 = user['keys']['email-verification']['key']
    assert key_1 in mailer_outbox[1].body.data
    assert 'email=test%40test.com' in mailer_outbox[1].body.data
    # request new verification key:
    app.post_json('/resend-email-verification-key', status=200)
    user = db.users.find_one({'username': 'maddoxx.aveen'})
    assert user['email_verify_pending']
    key_2 = user['keys']['email-verification']['key']
    assert key_2 in mailer_outbox[2].body.data
    assert key_2 != key_1
    assert 'email=test%40test.com' in mailer_outbox[2].body.data
    # verify email with new key:
    payload = {'email': 'test@test.com', 'key': key_2}
    app.post_json('/verify-email', payload, status=200)
    user = db.users.find_one({'username': 'maddoxx.aveen'})
    assert not user['email_verify_pending']


@pytest.mark.parametrize('login', [('maddoxx.aveen', 'aveen')], indirect=True)
def test_when_email_has_been_unset(set_db, app, login, db):
    """Should be forbidden."""
    db.users.update_one({'username': 'maddoxx.aveen'}, {'$unset': {'email': 1}})
    app.post('/resend-email-verification-key', status=403)
