"""Tests for managing user for spynl.hr package."""


import pytest
from bson import ObjectId

from spynl.api.auth.authentication import scramble_password
from spynl.api.auth.session_cycle import (
    TENANT_FIELDS,
    USER_DATA_WHITELIST,
    USER_EDIT_WHITELIST,
)
from spynl.api.auth.testutils import mkuser

UID_EXISTING = ObjectId()
UID_BLAH = ObjectId()
UID_ANOTHER = ObjectId()
UID_MULTITENANT = ObjectId()


@pytest.fixture(scope='module', autouse=True)
def set_db_indexes(db):
    """Setup db indexes once and drop when all tests finish."""
    db.users.create_index('email', unique=True, sparse=True)
    db.users.create_index('username', unique=True)
    yield
    db.users.drop_indexes()


@pytest.fixture
def set_db(db):
    """Fill in the database with some data for the tests in this module."""
    mkuser(
        db,
        'existing',
        'blah',
        ['12345'],
        custom_id=UID_EXISTING,
        def_app={'12345': 'pos'},
        tenant_roles={'12345': ['posp-device', 'webshop-customer']},
    )
    # TODO: can name be deprecated?
    db.users.update_one({'_id': UID_EXISTING}, {'$set': {'name': 'John Doe'}})
    db.users.insert_one(
        {
            '_id': UID_BLAH,
            'email': 'create@blah.com',
            'password_hash': scramble_password('blah4', 'blah4', '2'),
            'password_salt': 'blah4',
            'hash_type': '2',
            'active': True,
            'username': 'create_username',
            'tenant_id': ['12345'],
            'default_application': {'12345': 'pos'},
            'acls': {'someacl': True},
            'roles': {
                '12345': {'tenant': ['pos-device', 'webshop-customer', 'account-admin']}
            },
        }
    )
    db.users.insert_one(
        {
            '_id': ObjectId(),
            'email': 'master@blah.com',
            'password_hash': scramble_password('blah4', 'blah4', '2'),
            'password_salt': 'blah4',
            'hash_type': '2',
            'active': True,
            'username': 'master_username',
            'tenant_id': ['master'],
            'roles': {'master': {'tenant': ['sw-admin']}},
        }
    )
    db.users.insert_one(
        {
            '_id': UID_ANOTHER,
            'email': 'anothertenant@blah.com',
            'password_hash': scramble_password('blah', 'blah', '2'),
            'password_salt': 'blah',
            'hash_type': '2',
            'name': 'John Doe',
            'oldkey': 'old value',
            'active': True,
            'tenant_id': ['54321'],
            'username': 'another_username',
            'type': 'device',
            'wh': '55',
            'deviceId': '77665',
            'default_application': {'54321': 'pos'},
            'roles': {'54321': {'tenant': ['pos-device', 'webshop-customer']}},
        }
    )
    db.users.insert_one(
        {
            '_id': UID_MULTITENANT,
            'email': 'multitenant@blah.com',
            'username': 'multitenant_username',
            'password_hash': scramble_password('blah', 'blah', '2'),
            'password_salt': 'blah',
            'hash_type': '2',
            'name': 'John Doe 2',
            'active': True,
            'tenant_id': ['54321', '12345'],
            'default_application': {'54321': 'pos', '12345': 'webshop'},
            'roles': {
                '12345': {'tenant': ['webshop-customer', 'account-admin']},
                '54321': {'tenant': []},
            },
        }
    )
    db.tenants.insert_one(
        {'_id': '12345', 'name': 'test tenant', 'applications': ['account']}
    )
    db.tenants.insert_one(
        {'_id': '54321', 'name': 'another tenant', 'applications': ['pos']}
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})


@pytest.mark.parametrize(
    'login', [('create@blah.com', 'blah4', dict(tenant_id=12345))], indirect=True
)
def test_get_users(set_db, app, login):
    """Test the /users/get function, check whitelisting, and roles."""
    response = app.get('/users/get', status=200)

    for doc in response.json['data']:
        for key in doc:
            assert key in USER_DATA_WHITELIST
        for field in TENANT_FIELDS:
            if hasattr(doc, field):
                for tenant in doc[field]:
                    assert tenant == '12345'
        if doc['email'] == 'create@blah.com':
            assert doc['roles']['12345'] == {
                'tenant': ['pos-device', 'webshop-customer', 'account-admin']
            }
        if doc['email'] == 'anothertenant@blah.com':
            assert doc['wh'] == '55'
            assert doc['deviceId'] == '77665'


@pytest.mark.parametrize(
    'login', [('master@blah.com', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_get_user_by_master_user(db, app, set_db, login):
    """
    Get a user from Master user account.
    Respect user field whitelist. Permissions are included even though
    they are a TENANT_FIELDS entry and 'master' not in ('12345', '54321')
    """
    response = app.post_json(
        '/users/get', {'filter': {'username': 'multitenant_username'}}, status=200
    )
    assert len(response.json['data']) == 1
    udoc = response.json['data'][0]
    for key in udoc:
        assert key in USER_DATA_WHITELIST
    assert '12345' in udoc['roles']
    assert '54321' in udoc['roles']


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_create_user(db, app, mailer_outbox, set_db, login):
    """Test creating a new user."""
    response = app.get(
        '/tenants/12345/users/add?user={{a_key:value}}&email={email}'
        '&tenant_id=12345&username={username}&type=standard'.format(
            email='newuser@blah.com', username='newuser_username'
        ),
        status=200,
    )
    assert (
        'Created user. A verification email has been sent to '
        '{}'.format('newuser@blah.com') in response.json['message']
    )
    # look up mail (only file in DB)
    user = db.users.find_one({'email': 'newuser@blah.com'})
    assert user['keys']['pwd_reset']['key'] in mailer_outbox[0].body.data
    assert user['tenant_id'][0] == '12345'
    assert user.get('a_key') == 'value'


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_create_user_with_existing_email_address(app, db, set_db, login):
    """Create a new user that already exists."""
    email = 'existing@blah.com'
    username = 'random_username'
    response = app.get(
        '/tenants/12345/users/add?user={{a_key:value}}&username={username}'
        '&tenant_id=12345&email={email}&type=standard'.format(
            email=email, username=username
        ),
        expect_errors=True,
    )
    assert "The email '{}' is already in use".format(email) in response.json['message']


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_create_user_with_existing_username(app, db, set_db, login):
    """Create a new user that already exists."""
    response = app.get(
        '/tenants/12345/users/add?user={a_key:value}&username=existing&'
        'tenant_id=12345&type=standard',
        expect_errors=True,
    )
    assert "The username 'existing' is already taken." in response.json['message']


@pytest.mark.parametrize(
    'login', [('master@blah.com', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_edit_by_master_user(db, app, set_db, login):
    """Edit a user from Master user account."""
    app.post_json(
        '/tenants/12345/users/edit',
        {'data': {'active': False, 'fullname': 'fullname'}, '_id': str(UID_EXISTING)},
        status=200,
    )
    user = db.users.find_one({'_id': UID_EXISTING})
    assert user is not None
    assert user['active'] is True  # not on edit whitelist (use change_active)
    assert user.get('fullname') == 'fullname'
    assert user.get('name') == 'John Doe'


@pytest.mark.skip(reason='we only allow edit for master users for now')
@pytest.mark.parametrize(
    'login', [('create@blah.com', 'blah4', dict(tenant_id=12345))], indirect=True
)
def test_edit_by_tenant_user(db, app, set_db, login):
    """Edit user from a tenant account."""
    app.get(
        '/users/edit?data={{fullname:fullname2}}&_id={}'.format(UID_EXISTING),
        status=200,
    )
    user = db.users.find_one({'_id': UID_EXISTING})
    assert user.get('fullname') == 'fullname2'
    assert user.get('name') == 'John Doe'


@pytest.mark.skip(reason='we only allow edit for master users for now')
@pytest.mark.parametrize(
    'login', [('multitenant@blah.com', 'blah', dict(tenant_id=12345))], indirect=True
)
def test_edit_by_multi_tenant_user(db, app, set_db, login):
    """Edit user from an account that has more than one tenant"""
    app.get(
        '/users/edit?data={{fullname:fullname3}}&_id={}'.format(UID_EXISTING),
        status=200,
    )
    user = db.users.find_one({'_id': UID_EXISTING})
    assert user.get('fullname') == 'fullname3'
    assert user.get('name') == 'John Doe'


@pytest.mark.skip(reason='we only allow edit for master users for now')
@pytest.mark.parametrize(
    'login', [('create@blah.com', 'blah4', dict(tenant_id=12345))], indirect=True
)
def test_edit_by_tenant_user_no_access(app, set_db, login):
    """Edit user that does not belong to a tenant account."""
    response = app.get(
        '/users/edit?data={{fullname:fullnamef}}&_id={}'.format(UID_ANOTHER),
        expect_errors=True,
    )
    assert response.json['message'] == (
        'This user does not belong to the requested tenant (12345).'
    )


@pytest.mark.skip(reason='we only allow edit for master users for now')
@pytest.mark.parametrize(
    'login', [('multitenant@blah.com', 'blah', dict(tenant_id=12345))], indirect=True
)
def test_edit_by_multi_tenant_user_no_access(app, set_db, login):
    """
    Edit user that belongs to one of the user's tenants, but not the one the
    user is logged in as.
    """
    response = app.get(
        '/users/edit?data={{fullname:fullnamef}}&_id={}'.format(UID_ANOTHER),
        expect_errors=True,
    )
    assert response.json['message'] == (
        'This user does not belong to the requested tenant (12345).'
    )


@pytest.mark.skip(reason='we only allow edit for master users for now')
@pytest.mark.parametrize(
    'login', [('multitenant@blah.com', 'blah', dict(tenant_id=54321))], indirect=True
)
def test_edit_by_multi_tenant_user_no_access_2(app, set_db, login):
    """
    Edit user that belongs to one of the user's tenants, but not the one the
    user is logged in as.
    """
    response = app.get(
        '/users/edit?data={{fullname:fullnamef}}&_id={}'.format(UID_ANOTHER),
        expect_errors=True,
    )
    assert response.json['message'] == ("Permission to 'edit' User was denied.")


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_edit_user_missing_params(app, set_db, login):
    """Edit a user without passing the id parameter."""
    response = app.get(
        '/tenants/12345/users/edit?data={fullname:fullnamef}', expect_errors=True
    )
    assert response.json['type'] == 'MissingParameter'
    assert 'Missing required parameter: _id' in response.json['message']


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_edit_user_forbidden_params(db, app, set_db, login):
    """Try to add master to the tenant_id of the user."""
    payload = {
        'data': {'fullname': 'JA', 'tenant_id': ['12345', 'master']},
        '_id': str(UID_BLAH),
    }
    response = app.post_json('/tenants/12345/users/edit?', payload, status=200)

    assert response.json['affected_fields'] == ['fullname']
    user = db.users.find_one({'email': 'create@blah.com'})
    assert user['tenant_id'] == ['12345']


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_edit_user_dot_notation_params(db, app, set_db, login):
    """Try to edit keys which are allowed but contain dot notation"""
    payload = {
        'data': {'favorites.reports': {}, 'favorites.something.id': 1},
        '_id': str(UID_BLAH),
    }
    response = app.post_json('/tenants/12345/users/edit?', payload, status=200)

    # order changes thats why assert on a sorted list
    assert sorted(response.json['affected_fields']) == sorted(
        ['favorites.reports', 'favorites.something.id']
    )
    user = db.users.find_one({'email': 'create@blah.com'})
    assert user['favorites']['reports'] == {}
    assert user['favorites']['something']['id'] == 1


@pytest.mark.parametrize(
    'login', [('create@blah.com', 'blah4', dict(tenant_id=12345))], indirect=True
)
def test_edit_multiple_users_wrong_id_param(db, app, set_db, login):
    """Updating a field on multiple users but wrong formatting for _id."""
    payload = {'data': {'fullname': 'Meyer'}, '_id': [str(UID_BLAH), 'fnord']}
    response = app.post_json('/users/edit', payload, expect_errors=True)
    assert 'a string or an object' in response.json['message']


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_edit_multiple_users(db, app, set_db, login):
    """Updating a field on multiple users."""
    payload = {
        'data': {'fullname': 'Meyer'},
        '_id': {'$in': [str(UID_BLAH), str(UID_EXISTING)]},
    }
    app.post_json('/tenants/12345/users/edit', payload, status=200)
    user1 = db.users.find_one({'_id': UID_BLAH})
    assert user1['fullname'] == 'Meyer'
    user2 = db.users.find_one({'_id': UID_EXISTING})
    assert user2['fullname'] == 'Meyer'


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_create_device_type_user_with_existing_device_id(app, db, set_db, login):
    """Device id should be unique."""
    # NOTE add type to the request just for the sake of making it, otherwise
    # the type will be removed in the future, so this test can be refactored.
    db.users.insert_one({'deviceId': 'foo_bar', 'tenant_id': ['12345']})
    payload = {
        'username': 'foo_username',
        'user': dict(deviceId='foo_bar'),
        'type': 'device',
    }
    response = app.post_json('/tenants/12345/users/add', payload, status=403)
    assert 'device id foo_bar is already used' in response.json['message']


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_create_device_type_user_with_other_tenants_device_id(
    app, db, set_db, patch_dns_resolver, login
):
    """Same device id can exist for multiple devices but per tenant."""
    # NOTE add type to the request just for the sake of making it, otherwise
    # the type will be removed in the future, so this test can be refactored.
    # add some random tenant and one user of his
    db.tenants.insert_one(dict(_id='123456'))
    db.users.insert_one(dict(deviceId='foo', tenant_id=['123456']))

    payload = {
        'username': 'foo_username',
        'email': 'foo@bar.com',
        'user': dict(deviceId='foo'),
        'type': 'device',
    }
    app.post_json('/tenants/12345/users/add', payload, status=200)
    devices = list(
        db.users.find(dict(deviceId='foo'), dict(_id=0, deviceId=1, tenant_id=1))
    )
    assert len(devices) == 2
    device_tenant_ids = [device['tenant_id'][0] for device in devices]
    # ensure they belong to different tenant
    assert set(['123456', '12345']) == set(device_tenant_ids)


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
def test_update_device_user_that_device_id_check_doesnt_happen(app, db, set_db, login):
    """Existing device ids are not checked for uniqueness."""

    # insert a device with same device id as ther other device from setup
    db.users.insert_one(dict(tenant_id=['54321'], deviceId='77665'))
    # Update device-user but update some other field than deviceId
    data_to_edit = {USER_EDIT_WHITELIST[0]: 'new_fullname'}
    payload = dict(_id=str(UID_ANOTHER), data=data_to_edit)
    app.post_json('/tenants/54321/users/edit', payload, status=200)
    # No check should have happened even though 2 devices have same id for the
    # same tenant.
    updated_user = db.users.find_one(dict(_id=UID_ANOTHER))
    assert updated_user[USER_EDIT_WHITELIST[0]] == 'new_fullname'


@pytest.mark.parametrize('login', [('master@blah.com', 'blah4')], indirect=True)
@pytest.mark.parametrize(
    "device_id,status_code,msg",
    [
        ('99999', 403, 'device id 99999 is already used'),
        ('foo_bar', 200, 'Updated user'),
    ],
)
def test_update_device_user_giving_existing_device_id_from_same_tenant(
    app, db, set_db, device_id, status_code, msg, login
):
    """Device id should be unique per tenant."""
    # insert a device with different device id from the other device from setup
    db.users.insert_one(dict(tenant_id=['54321'], deviceId='99999'))
    payload = dict(_id=str(UID_ANOTHER), data=dict(deviceId=device_id))
    response = app.post_json(
        '/tenants/54321/users/edit',
        payload,
        status=status_code,
        expect_errors=(status_code == 200),
    )
    assert msg in response.json['message']
    if status_code == 200:
        updated_user = db.users.find_one({'_id': UID_ANOTHER})
        assert updated_user['deviceId'] == device_id
