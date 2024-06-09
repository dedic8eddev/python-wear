import datetime

import pyotp
import pytest

from spynl.api.auth.testutils import mkuser


@pytest.fixture(autouse=True)
def set_db(db):
    """Fill the database with data for tests to have."""
    db.tenants.insert_one({'active': True, '_id': 'master', 'name': 'master'})
    mkuser(
        db,
        'master user 2',
        'password',
        ['master'],
        tenant_roles={'master': ['sw-admin', 'sw-developer']},
    )
    mkuser(
        db,
        'master user',
        'password',
        ['master'],
        tenant_roles={'master': ['sw-admin', 'sw-developer']},
    )


def test_set_2fa_fail(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    app.post_json('/set-2fa', {'TwoFactorAuthEnabled': True}, status=400)
    app.post_json(
        '/set-2fa',
        {'TwoFactorAuthEnabled': True, 'username': 'master user', 'password': '0'},
        status=401,
    )


def test_set_2fa_success(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    resp = app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    user = spynl_data_db.users.find_one({'username': 'master user'})
    assert (
        'two_factor_shared_secret' in user and user['settings']['TwoFactorAuthEnabled']
    )
    assert resp.json == {
        'status': 'ok',
        '2FAProvisioningUri': (
            'otpauth://totp/sw2fa:master%20user?secret={}&issuer=sw2fa'.format(
                user['two_factor_shared_secret']
            )
        ),
    }


def test_set_2fa_noop(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    payload = {
        'TwoFactorAuthEnabled': True,
        'username': 'master user',
        'password': 'password',
    }
    app.post_json('/set-2fa', payload, status=200)
    resp = app.post_json('/set-2fa', payload, status=200)
    user = spynl_data_db.users.find_one({'username': 'master user'})
    assert (
        'two_factor_shared_secret' in user and user['settings']['TwoFactorAuthEnabled']
    )
    assert resp.json == {'status': 'ok'}


def test_set_2fa_unset(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    resp = app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': False,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    user = spynl_data_db.users.find_one({'username': 'master user'})
    assert (
        'two_factor_shared_secret' not in user
        and not user['settings']['TwoFactorAuthEnabled']
    )
    assert resp.json == {'status': 'ok'}


def test_2fa_login(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    app.get('/logout')
    user = spynl_data_db.users.find_one({'username': 'master user'})
    resp = app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    resp = app.post_json(
        '/validate-otp',
        {
            '2FAToken': resp.json['2FAToken'],
            '2FAOtp': pyotp.TOTP(user['two_factor_shared_secret']).now(),
        },
        status=200,
    )
    assert 'sid' in resp.json


def test_2fa_login_fail(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    app.get('/logout')
    user = spynl_data_db.users.find_one({'username': 'master user'})
    resp = app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    resp = app.post_json(
        '/validate-otp',
        {
            '2FAToken': resp.json['2FAToken'],
            '2FAOtp': pyotp.TOTP(user['two_factor_shared_secret']).at(
                datetime.datetime.utcnow() - datetime.timedelta(seconds=31)
            ),
        },
        status=401,
    )


def test_2fa_login_after_unset(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': False,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    resp = app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    assert 'sid' in resp.json


def test_2fa_login_different_user(spynl_data_db, app):
    app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user',
            'password': 'password',
        },
        status=200,
    )
    app.get('/logout')

    app.post_json(
        '/login', {'username': 'master user 2', 'password': 'password'}, status=200
    )
    app.post_json(
        '/set-2fa',
        {
            'TwoFactorAuthEnabled': True,
            'username': 'master user 2',
            'password': 'password',
        },
        status=200,
    )
    app.get('/logout')

    user_2 = spynl_data_db.users.find_one({'username': 'master user 2'})
    resp = app.post_json(
        '/login', {'username': 'master user', 'password': 'password'}, status=200
    )
    resp = app.post_json(
        '/validate-otp',
        {
            '2FAToken': resp.json['2FAToken'],
            '2FAOtp': pyotp.TOTP(user_2['two_factor_shared_secret']).now(),
        },
        status=401,
    )
