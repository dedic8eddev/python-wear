"""Authentication tests for spynl.auth package."""

import datetime
from functools import partial

import pytest
import pytz
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.main.dateutils import date_to_str

from spynl.api.auth.authentication import challenge, scramble_password, set_password
from spynl.api.auth.session_cycle import USER_DATA_WHITELIST, get_cookie_domain
from spynl.api.auth.testutils import mkuser


@pytest.fixture
def set_db(db):
    """Fill the database with data for tests to have."""
    db.tenants.insert_one(
        {
            'active': True,
            '_id': 'tenant1',
            'name': 'Tenant Eins',
            'owners': ['owner'],
            'applications': ['pos', 'webshop', 'dashboard'],
            'retail': True,
        }
    )
    db.tenants.insert_one(
        {
            'active': True,
            '_id': 'tenant2',
            'name': 'Tenant Zwei',
            'applications': ['pos', 'webshop'],
        }
    )
    db.tenants.insert_one(
        {'_id': 'aninactivetenantid', 'active': False, 'name': 'an inactive tenant'}
    )
    db.tenants.insert_one({'active': True, '_id': 'yetanothertenantid'})
    db.tenants.insert_one({'_id': 'aninactivetenantid2', 'active': False})
    db.tenants.insert_one({'active': True, '_id': 'master'})
    mkuser(
        db,
        'blahuser',
        'blah',
        ['tenant1', 'aninactivetenantid'],
        language='en-gb',
        tenant_roles={'tenant1': ['pos-device'], 'tenant2': ['webshop-customer']},
        def_app={'tenant1': 'pos', 'tenant2': 'webshop'},
        custom_id='owner',
    )
    db.users.insert_one(
        {
            'username': 'blahuser2',
            'email': 'blahuser2@blah.com',
            'password_hash': scramble_password('blah2', 'blah2', '1'),
            'password_salt': 'blah2',
            'hash_type': '1',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            'username': 'blahuser3',
            'email': 'blahuser3@blah.com',
            'password_hash': scramble_password('blah3', 'blah3', '2'),
            'password_salt': 'blah3',
            'hash_type': '2',
            'active': False,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            'username': 'multi_user',
            'email': 'multiuser@blah.com',
            'password_hash': scramble_password('blah4', 'blah4', '2'),
            'password_salt': 'blah4',
            'default_application': {'tenant1': 'pos', 'tenant2': 'webshop'},
            'roles': {
                'tenant1': {'tenant': ['pos-device']},
                'tenant2': {'tenant': ['pos-device', 'webshop-customer']},
            },
            'hash_type': '2',
            'active': True,
            'tenant_id': ['aninactivetenantid', 'tenant1', 'tenant2'],
        }
    )
    db.users.insert_one(
        {
            'username': 'sneaky_user',
            'email': 'sneakyuser@blah.com',
            'password_hash': scramble_password('blah5', 'blah5', '2'),
            'password_salt': 'blah5',
            'default_application': {'tenant1': 'webshop'},
            'roles': {
                'aninactivetenant': {'tenant': ['pos-device', 'webshop-customer']}
            },
            'hash_type': '2',
            'active': True,
            'tenant_id': ['aninactivetenantid', 'aninactivetenantid2'],
        }
    )
    mkuser(
        db,
        'master_user',
        'blah',
        ['master'],
        tenant_roles={'master': ['sw-admin', 'sw-developer']},
    )


@pytest.fixture
def set_db_1(db):
    """Fill in the database some data for the tests."""
    # Copied the next query from conftest.py which is the bare minimum this
    # test file needs for the tests to continue passing,
    # TODO move all the db stuff from conftest.py to each testfile needs them
    # you need the two lines below if you only py.test this file by itself
    db.tenants.insert_one(
        {
            '_id': '55555',
            'name': 'BlaTenant',
            'applications': ['pos', 'webshop'],
            'retail': True,
            'addresses': [
                {
                    'primary': True,
                    'street': 'Main street',
                    'company': 'Disney',
                    'city': 'Disney World',
                    'houseno': 1,
                    'country': 'US',
                    'zipcode': '91210',
                    'state': 'CA',
                    'houseadd': None,
                    'type': 'main',
                    'street2': None,
                },
                {'primary': False},
            ],
        }
    )
    db.tenants.insert_one(
        {
            '_id': '55556',
            'name': 'BluppTenant',
            'applications': ['pos'],
            'wholesale': True,
        }
    )
    mkuser(
        db,
        'getuser',
        'blah',
        ['55555', '55556'],
        custom_id=ObjectId(),
        tenant_roles={
            '55555': ['pos-device', 'webshop-customer'],
            '55556': ['pos-device'],
        },
        settings={'applicationLinks': {'hardwearshop': True}},
    )


@pytest.fixture
def set_db_2(db):
    db.tenants.insert_one(
        {
            'active': True,
            '_id': 'tenant3',
            'name': 'Tenant test brand-owner',
            'applications': ['products'],
            'retail': True,
            'wholesale': True,
        }
    )
    mkuser(
        db,
        name='brand_owner',
        pwd='blah6',
        tenant_ids=['tenant3'],
        language='en-gb',
        tenant_roles={
            'tenant3': ['products-brand_owner'],
        },
        def_app={'tenant3': 'products'},
    )


@pytest.mark.parametrize(
    'login', [('brand_owner', 'blah6', dict(remember_me=True))], indirect=True
)
def test_successful_login_brand_owner_post(app, db, set_db_2, login):
    response = app.post_json('/me')
    print(response.json['data'])
    assert "products-brand_owner" in response.json['data']['roles']['tenant3']


@pytest.fixture(scope="module")
def user2():
    """Return user 2 dict."""
    return {
        'username': 'blahuser2',
        'email': 'blahuser2@blah.com',
        'password_hash': scramble_password('blah2', 'blah2', '1'),
        'password_salt': 'blah',
        'hash_type': '1',
        'active': True,
        'tenant_id': ['tenant1'],
    }


@pytest.fixture
def request_(spynl_data_db):
    DummyRequest.db = spynl_data_db
    return DummyRequest


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_logout(app, db, set_db, login):
    """Test the logout function, tests if session and cookie get deleted."""
    app.get('/logout')
    data = db.spynl_sessions.find_one({'_id': login['sid']})
    # session should now be deleted
    assert data is None
    # cookies should also be deleted
    cookies = app.cookies
    cookies.pop('lang')
    assert not cookies


def test_successful_locale_cookie_is_set(app, db, set_db):
    response = app.post_json('/login', {"username": "blahuser", "password": "blah"})
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert 'lang=en-gb' in cookies


# Several tests for login, test both GET and POST (login in body)
def test_successful_login(app, db, set_db):
    """Test standard successful login."""
    date = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    params = dict(username='blahuser', password='blah')
    response = app.get('/login', params)

    cookies = response.headers.getall('Set-Cookie')
    assert cookies
    for cookie in cookies:
        assert cookie.startswith('lang') or cookie.startswith('sid=')

    assert response.json['status'] == 'ok'
    assert response.json['current_tenant'] == 'tenant1'
    assert 'sid' in response.json
    assert 'tenants' in response.json
    user = db.users.find_one({'username': 'blahuser'})
    login_date = user['last_login']
    # check that the last_login date is within one second of date
    assert (
        date - datetime.timedelta(seconds=1)
        <= login_date
        <= date + datetime.timedelta(seconds=1)
    )


def test_successful_login_post(app, set_db):
    """Test standard successful login, login in body of post."""
    # test logging in via POST here
    response = app.post_json('/login', {"username": "blahuser", "password": "blah"})
    assert response.json['current_tenant'] == 'tenant1'
    assert 'sid' in response.json
    assert 'tenants' in response.json

    cookies = response.headers.getall('Set-Cookie')
    assert cookies
    for cookie in cookies:
        assert cookie.startswith('lang') or cookie.startswith('sid=')


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_session_after_login(app, db, set_db, login):
    """test that everything is set correctly in the session"""
    session = db.spynl_sessions.find_one({'_id': login['sid']})
    assert session['username'] == 'blahuser'
    assert session['_expire'] == _add_days(1)
    assert 'remote_addr' in session.keys()


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(remember_me=True))], indirect=True
)
def test_session_after_remember_me_login(app, db, set_db, login):
    """test that everything is set correctly in the session"""
    session = db.spynl_sessions.find_one({'_id': login['sid']})
    assert session['username'] == 'blahuser'
    assert session['_expire'] == _add_days(30)
    assert 'remote_addr' in session.keys()


@pytest.mark.parametrize('login', [('multiuser@blah.com', 'blah4')], indirect=True)
def test_login_with_multitenant(app, set_db, login):
    """Test successful login for user with multiple tenants."""
    assert login['status'] == 'ok'
    # multiple tenants, so first tenant should be set
    assert login['current_tenant'] == 'tenant1'
    assert 'sid' in login
    assert 'tenants' in login


def test_login_with_multitenant_switch_order(db, app, set_db):
    """Test successful login for user with multiple tenants."""
    tenant_id = ['aninactivetenant', 'tenant2', 'tenant1']
    db.users.update_one({'username': 'multi_user'}, {'$set': {'tenant_id': tenant_id}})
    params = dict(username='multiuser@blah.com', password='blah4')
    response = app.get('/login', params)
    assert response.json['status'] == 'ok'
    # multiple tenants, so first tenant should be set
    assert response.json['current_tenant'] == 'tenant2'
    assert 'sid' in response.json
    assert 'tenants' in response.json
    # put back for next tests:
    tenant_id = ['aninactivetenant', 'tenant1', 'tenant2']
    db.users.update_one({'username': 'multi_user'}, {'$set': {'tenant_id': tenant_id}})


@pytest.mark.parametrize(
    'password',
    [
        'non_asccii_ö',  # check 1 non ascii
        '_spa ce_',  # check 2 words with space
        'non_asccii_ψ',  # check another ascii
        'öψ€®∞ℜØ¶',  # full of non ascii chars
        'right_space ',  # ending space
        ' left_space',  # starting space
        ' _spaces_ ',  # ending + starting space
    ],
)
def test_login_with_non_ascii_weird_characters(db, app, password):
    """Ensure users can use non ascii characters for their passwords."""
    password = password.strip()
    hashed = scramble_password(password, 'fooSalt', '2')
    user = dict(
        password_hash=hashed,
        username='foo',
        email='foo@bar.com',
        active=True,
        hash_type='2',
        password_salt='fooSalt',
        tenant_id=['tenant1'],
    )
    db.users.insert_one(user)
    db.tenants.insert_one(dict(_id='tenant1', name='Tenant Eins', active=True))

    params = dict(username='foo', password=password)
    response = app.get('/login', params)
    assert response.json['status'] == 'ok'


def test_invalid_session(app, set_db):
    """No one is logged in, so we should get an error."""
    response = app.get('/validate-session', expect_errors=True)
    assert response.json['status'] == 'error'


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_valid_session(app, set_db, login):
    """Log in, then try validation."""
    assert app.get('/validate-session', status=200)


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_set_tenant_successfully(app, db, set_db, login):
    """Test simple login, set a valid tenant, get applications back."""
    app.get('/validate-session')
    response = app.get('/set-tenant?id=tenant1')
    assert response.json['default_application'] == 'pos'
    assert response.json['roles'] == ['pos-device', 'owner']
    data = db.spynl_sessions.find_one({'_id': response.json['sid']})
    assert data['tenant_id'] == 'tenant1'
    # test new cookie:
    cookies = response.headers.getall('Set-Cookie')
    assert cookies
    for cookie in cookies:
        assert cookie.startswith('lang') or cookie.startswith('sid=')


def test_set_tenant_keep_same_expire(app, db, set_db):
    response = app.post_json('/login', {'username': 'blahuser', 'password': 'blah'})
    first_session = db.spynl_sessions.find_one({'_id': response.json['sid']})
    # set expire back two days so we can check if expire is retained
    expire = first_session['_expire'] - datetime.timedelta(days=2)
    db.spynl_sessions.update_one(
        {'_id': response.json['sid']}, {'$set': {'_expire': expire}}
    )
    response = app.get('/set-tenant?id=tenant1')
    second_session = db.spynl_sessions.find_one({'_id': response.json['sid']})
    assert first_session['_id'] != second_session['_id']
    assert second_session['_expire'] == expire


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_set_inactive_tenant(app, db, set_db, login):
    """You cannot set an inactive tenant."""
    assert login['status'] == 'ok'

    response = app.get('/set-tenant?id=aninactivetenantid', expect_errors=True)
    assert "Account 'aninactivetenantid' is not active." in response.json['message']
    data = db.spynl_sessions.find_one({'_id': login['sid']})
    assert data['tenant_id'] != 'aninactivetenantid'


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_set_wrong_tenant(app, set_db, login):
    """You cannot set a tenant you do not have enabled."""
    assert login['status'] == 'ok'

    response = app.get('/set-tenant?id=yetanothertenantid', expect_errors=True)
    assert 'You do not have access' in response.json['message']


def _add_days(days):
    now_ = datetime.datetime.now(pytz.timezone('GMT'))

    return now_.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(
        days=days
    )


def _expire_midnight(period):
    if period == 'day':
        days = 1
    else:
        days = 30

    return 'expires=%s' % (_add_days(days) + datetime.timedelta(seconds=-1)).strftime(
        '%a, %d-%b-%Y %H:%M:%S %Z'
    )


expire_day = partial(_expire_midnight, 'day')
expire_month = partial(_expire_midnight, 'month')


def test_succesful_login_with_remember(app, set_db):
    """Test login with remember me option."""
    params = dict(username='blahuser', password='blah', remember_me=True)
    response = app.get('/login', params)

    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_month() in cookies
    assert 'sid' in response.json
    assert 'tenants' in response.json


def test_succesful_login_with_remember_get(app, set_db):
    """Test login with remember me option, login in using GET."""
    # test using a POST request
    response = app.get(
        '/login?username=blahuser', '&password=blah&remember_me=True', status=200
    )
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_month() in cookies
    assert 'sid' in response.json
    assert 'tenants' in response.json


def test_session_cookies_latest_collection(app, set_db):
    """Test login with remember me option, login in using GET."""
    # test using a POST request
    app.get('/login?username=blahuser', '&password=blah&remember_me=True', status=200)
    response = app.get('/logout')
    assert 'lc_response' in response.json


def test_master_is_remembered_for_48_hours_when_logging_in(app, set_db):
    """Test login with remember me option as master, login in using GET.
    max age should be 48 hours.
    """
    response = app.get(
        '/login?username=master_user', '&password=blah&remember_me=True', status=200
    )
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_day() in cookies
    assert 'sid' in response.json
    assert 'tenants' in response.json


def test_login_remember_me_false(app, set_db):
    """
    Test login with explicit false for remember me.

    successful_login tests False by default, now test explicit False.
    """
    response = app.post('/login?username=blahuser&password=blah&remember_me=False', '')
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_day() in cookies


def test_login_remember_me_false_post(app, set_db):
    """
    Test login with explicit false for remember me, login in body.

    successful_login tests False by default, now test explicit False
    """
    response = app.post(
        '/login', '{"username": "blahuser", "password": "blah", "remember_me": false}'
    )
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_day() in cookies


def test_login_remember_me_wrong(app, set_db):
    """Test invalid value for remember me in login will be false."""
    response = app.post('/login?username=blahuser&password=blah&remember_me=bla', '')
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_day() in cookies


def test_login_remember_me_wrong_post(app, set_db):
    """Test invalid value for remember me in login, login in body."""
    response = app.post(
        '/login', '{"username": "blahuser", "password": "blah", "remember_me": "bla"}'
    )
    cookies = ','.join(response.headers.getall('Set-Cookie'))
    assert expire_day() in cookies


def test_failed_login(app, set_db):
    """Test failed login."""
    response = app.post_json(
        '/login?username=blahuser&password=blahhhh', {}, status=401
    )
    assert response.json['type'] == 'WrongCredentials'


def test_failed_login_inactive_user(app, set_db):
    """Test failed login with an inactive user"""
    response = app.post_json('/login?username=blahuser3&password=blah3', {}, status=403)
    assert response.json['type'] == 'UserNotActive'
    # make sure user is not logged in:
    assert 'sid' not in response.json
    # the frontend depends on /me to know if a user is logged in or not:
    response = app.get('/me', status=403)
    # but we only want to show the user not active message if the password
    # and username are correct:
    response = app.post_json('/login?username=blahuser3&password=blah', {}, status=401)
    assert response.json['type'] == 'WrongCredentials'


def test_failed_login_non_existent_user(app, set_db):
    """Test failed login."""
    response = app.post_json(
        '/login?username=blahusers&password=blahhhh', {}, status=401
    )
    assert response.json['type'] == 'WrongCredentials'


def test_failed_login_post(app, set_db):
    """Test failed login, login in body."""
    response = app.post_json(
        '/login', {"username": "blahuser", "password": "blahhhh"}, status=401
    )
    assert response.json['type'] == 'WrongCredentials'


def test_increment_failed_login(app, db, set_db):
    """test increment failed login count happens"""
    username = 'blahuser'
    # login once with correct pwd to get rid of count of previous tests
    app.post_json('/login?username=blahuser&password=blah', {}, status=200)
    app.post_json('/login?username=blahuser&password=blahhhh', {}, expect_errors=True)
    user = db.users.find_one({'username': username})
    assert user['failed_login'] == 1
    app.post_json('/login?username=blahuser&password=blahhhh', {}, expect_errors=True)
    user = db.users.find_one({'username': username})
    assert user['failed_login'] == 2
    app.post_json('/login?username=blahuser&password=blah', {}, status=200)
    user = db.users.find_one({'username': username})
    assert user['failed_login'] == 0


def test_failed_login_no_active_tenants(app, set_db):
    """Test that login fails if the user has no active tenants"""
    response = app.post_json(
        '/login?username=sneaky_user&password=blah5', {}, expect_errors=True
    )
    assert response.json['type'] == 'NoActiveTenantsFound'


def test_subsequent_logins(app, set_db):
    """
    If after user A has logged in, user B logs in via the login page, user B
    should get a new session id. If user B logs in again, he should keep his
    session, though.
    """
    params = dict(username='blahuser', password='blah')
    response = app.get('/login', params)
    assert response.json['status'] == 'ok'
    sid1 = response.json['sid']

    params = dict(username='multi_user', password='blah4')
    response = app.get('/login', params)
    assert response.json['status'] == 'ok'
    sid2 = response.json['sid']
    assert sid1 != sid2

    response = app.get('/login', params)
    assert response.json['status'] == 'ok'
    sid3 = response.json['sid']
    assert sid2 == sid3


@pytest.mark.parametrize('login', [('blahuser', 'blah')], indirect=True)
def test_me_returns_correct_roles_roles(app, db, set_db, login):
    """
    Test if the /me endpoint returns the correct roles
    """
    response = app.get('/me', status=200)
    assert response.json['data']['roles']['tenant1'] == ['pos-device', 'owner']
    assert response.json['data']['applications'] == {
        'account': False,
        'crm': False,
        'dashboard': True,
        'inventory': False,
        'pos': True,
        'products': False,
        'secondscreen': False,
        'webshop': False,
        'sales': False,
        'logistics': False,
        'picking': False,
        'admin': False,
        'photos': False,
        'ecwid_link': False,
        'foxpro_backoffice': False,
        'polytex': False,
        'hardwearshop': False,
    }
    response = app.get('/me', status=200)


@pytest.mark.parametrize('login', [('getuser@blah.com', 'blah')], indirect=True)
def test_me(set_db_1, app, login):
    """Test /me endpoint, and that only whitelisted keys are returned."""
    me = app.get('/me', status=200)
    assert me.json['data']['email'] == 'getuser@blah.com'
    # add fields that /me adds itself:
    whitelist = USER_DATA_WHITELIST + ('current_tenant', 'tenants', 'applications')
    for key in me.json['data']:
        assert key in whitelist
    assert me.json['data']['tenants'] == [
        {
            'id': '55555',
            'name': 'BlaTenant',
            'retail': True,
            'wholesale': False,
            'address': {
                'primary': True,
                'street': 'Main street',
                'company': 'Disney',
                'city': 'Disney World',
                'houseno': 1,
                'country': 'US',
                'zipcode': '91210',
                'state': 'CA',
                'houseadd': None,
                'type': 'main',
                'street2': None,
            },
        },
        {
            'id': '55556',
            'name': 'BluppTenant',
            'retail': False,
            'wholesale': True,
            'address': None,
        },
    ]
    assert me.json['data']['current_tenant'] == '55555'
    assert me.json['data']['applications'] == {
        'account': False,
        'crm': False,
        'dashboard': False,
        'inventory': False,
        'pos': True,
        'products': False,
        'secondscreen': False,
        'webshop': False,
        'sales': False,
        'logistics': False,
        'picking': False,
        'admin': False,
        'photos': False,
        'ecwid_link': False,
        'foxpro_backoffice': False,
        'polytex': False,
        'hardwearshop': True,
    }

    app.post('/set-tenant?id={}'.format('55556'), status=200)
    me2 = app.get('/me', status=200)
    assert me2.json['data']['current_tenant'] == '55556'


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_me_master_user_returns_correct_roles(set_db, app, login):
    """Test /me endpoint returns the correct roles for a master user."""
    response = app.get('/me', status=200)
    assert response.json['data']['roles']['master'] == [
        'sw-admin',
        'sw-developer',
        'spynl-developer',
    ]


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_me_master_user_returns_correct_applications(set_db, app, login):
    """Test /me endpoint returns the correct applications for a master user."""
    response = app.get('/me', status=200)
    assert response.json['data']['applications'] == {
        'account': False,
        'crm': False,
        'dashboard': False,
        'inventory': False,
        'pos': False,
        'products': False,
        'secondscreen': False,
        'webshop': False,
        'sales': False,
        'logistics': False,
        'picking': False,
        'admin': True,
        'photos': False,
        'ecwid_link': False,
        'foxpro_backoffice': False,
        'polytex': False,
        'hardwearshop': False,
    }


def test_challenge(set_db, config, request_):
    """Test the challenge function."""
    assert challenge(request_, 'blah', username='blahuser')  # Correct challenge
    assert not challenge(request_, 'blech', username='blahuser')  # Incorrect
    assert challenge(request_, 'blah3', username='blahuser3')  # Inactive user
    assert not challenge(request_, '', username='')  # No data
    assert challenge(request_, 'blah', email='blahuser@blah.com')  # Email challenge


def test_set_password_func_when_fields_do_not_exist(
    db, set_db, user2, config, request_
):
    """The `set_password` func should expect fields to not always be there."""
    db.users.update_one(
        {'email': user2['email']},
        {
            '$unset': {
                'password_hash': 1,
                'password_salt': 1,
                'hash_type': 1,
                'hash_date': 1,
            }
        },
    )
    user = db.users.find_one({'email': user2['email']})
    set_password(request_, user, '123456', '2')  # no exception is raised


def test_set_password_keeps_history_of_previous_password(
    db, set_db, user2, config, request_
):
    """Setting a password should save the hash of the previous one."""
    user_before = db.users.find_one({'email': user2['email']})
    password_record = {
        'hash': user_before['password_hash'],
        'hash_type': user_before['hash_type'],
        'hash_date': None,
    }
    assert password_record['hash_type'] != 2  # make sure its different
    set_password(request_, user_before, '123456', '2')
    user_after = db.users.find_one({'email': user2['email']})
    assert user_after['oldPasswords'][-1] == password_record


def test_set_password_doesnt_allow_older_password_when_only_one_exists(
    db, set_db, user2, request_
):
    """Check when one password exists and no oldPasswords field exists."""
    user = db.users.find_one({'email': user2['email']})
    with pytest.raises(Exception):
        set_password(request_, user, 'blah2')


def test_set_password_doesnt_allow_older_ones_to_be_used(
    db, set_db, user2, config, request_
):
    """Ensure already used password doesnt allowed to be used."""
    user = db.users.find_one({'email': user2['email']})
    set_password(request_, user, 'blah3')
    with pytest.raises(Exception):
        set_password(request_, user, 'blah2')


def test_challenging_rehashes_users_password_and_ensures_loggingin(
    db, user2, set_db, config, request_
):
    """challenge should rehash password when non default hash type is used."""
    user_before = db.users.find_one({'email': user2['email']})
    assert user_before['hash_type'] == '1'
    challenge(request_, 'blah2', user2['username'])
    user_after = db.users.find_one({'email': user2['email']})
    assert user_after['hash_type'] != '1'
    assert user_before['password_hash'] != user_after['password_hash']
    # Ensure user can still login
    assert challenge(request_, 'blah2', user2['username'])


def test_scramble():
    """Test the scramble function."""
    md5 = '6512bd43d9caa6e02c990b0a82652dca'
    assert md5 == scramble_password('1', '1', '1')
    pbkdf2 = '$p5k2$$1$zLn2rCqgXTVFUuqr3rPXLL/47ME3idZc'
    assert pbkdf2 == scramble_password('1', '1', '2')
    sha = (
        '74a49c698dbd3c12e36b0b287447d833f74f3937ff132ebff7054baa18623c3'
        '5a705bb18b82e2ac0384b5127db97016e63609f712bc90e3506cfbea97599f46f'
    )
    assert sha == scramble_password('1', '1', '3')


def test_time(app, set_db):
    """
    test spynl.main.views.time,
    but with both server and user's local time
    """
    utc_now = datetime.datetime.now(tz=pytz.UTC)
    prec = 16  # first part of date iso str, no ms or timezone
    response = app.get('/time', status=200)
    assert response.json['server_time'][:prec] == date_to_str(utc_now)[:prec]
    # Authenticate, now we get local time
    params = dict(username='blahuser', password='blah')
    response = app.get('/login', params)
    response = app.get('/time?sid={}'.format(response.json['sid']), status=200)
    assert response.json['server_time'][:prec] == date_to_str(utc_now)[:prec]
    assert response.json['tz'] == 'Europe/Amsterdam'
    dst_factor = 1  # daylight saving time factor (added to UTC during winter)

    # During summer we have to add two hours to UTC
    if datetime.datetime.now(pytz.timezone('Europe/Amsterdam')).dst():
        dst_factor = 2
    # move date forward, to compare the first part
    ams_now = utc_now + datetime.timedelta(0, dst_factor * 60 * 60)
    assert response.json['local_time'][:prec] == date_to_str(ams_now)[:prec]


def test_login_rehashes_passwords_when_user_uses_old_hash_type(app, db, set_db):
    """If user has old hash type, spynl should change to new during login."""
    new_pass_hash = scramble_password('new.pass123', 'word', '1')
    new_values = {
        'hash_type': '1',
        'password_hash': new_pass_hash,
        'password_salt': 'word',
    }
    db.users.update_one({'username': 'blahuser'}, {'$set': new_values})

    payload = {'username': 'blahuser', 'password': 'new.pass123'}
    app.post_json('/login', payload, status=200)
    user = db.users.find_one({'username': 'blahuser'})
    # default hash type is 2(setting in .ini file)
    assert user['hash_type'] == '2'
    # hash changed during login..
    assert user['password_hash'] == scramble_password(
        'new.pass123', user['password_salt'], '2'
    )


@pytest.mark.parametrize(
    'domain_,expected',
    [
        ('spynl.dev.swcloud.nl', 'dev.swcloud.nl'),
        ('spynl-services.dev.swcloud.nl', 'dev.swcloud.nl'),
        ('spynl.test.softwearconnect.com', 'test.softwearconnect.com'),
        ('spynl.beta.softwearconnect.com', 'beta.softwearconnect.com'),
        ('spynl.softwearconnect.com', 'softwearconnect.com'),
        ('spynl-services.softwearconnect.com', 'softwearconnect.com'),
        ('a.b.c.d', 'b.c.d'),
    ],
)
def test_cookie_domain(domain_, expected):
    class R:
        domain = domain_

    assert get_cookie_domain(R()) == expected
