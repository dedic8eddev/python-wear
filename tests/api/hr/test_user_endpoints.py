"""Tests for special endpoints for user management."""

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

UID_HANS = ObjectId()


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
            'owners': [UID_HANS],
        }
    )
    db.tenants.insert_one(
        {
            '_id': 'othertenantid',
            'name': 'New Corp.',
            'active': True,
            'applications': ['account', 'dashboard'],
        }
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    mkuser(db, 'existing-hans', 'blah', ['existingtenantid'], custom_id=UID_HANS)
    mkuser(
        db,
        'existing-jan',
        'blah',
        [str('existingtenantid')],
        custom_id=ObjectId(),
        tenant_roles={'existingtenantid': ['dashboard-user']},
        user_type='standard',
    )
    mkuser(
        db,
        'other_user',
        'blah',
        [str('othertenantid')],
        custom_id=ObjectId(),
        tenant_roles={'othertenantid': ['dashboard-user']},
        user_type='standard',
    )
    mkuser(
        db,
        'master_username',
        'blah4',
        ['master'],
        custom_id=ObjectId(),
        tenant_roles={'master': ['sw-admin']},
    )
    mkuser(
        db,
        'master_username-consultant',
        'blah4',
        ['master'],
        custom_id=ObjectId(),
        tenant_roles={'master': ['sw-consultant']},
    )
    db.spynl_audit_log.delete_many({})


@pytest.fixture
def set_db_1(db):
    """Fill in the database some data for the tests."""

    db.tenants.insert_one(
        {'_id': '55555', 'name': 'BlaTenant', 'applications': ['pos', 'webshop']}
    )
    db.tenants.insert_one(
        {'_id': '55556', 'name': 'BluppTenant', 'applications': ['pos']}
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
    )


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_update_roles_without_permission(db, app, login):
    """You need write permission on the users collection"""
    payload = {'username': 'existing-jan', 'roles': {'pos-device': True}}
    response = app.post_json('/users/update-roles', payload, expect_errors=True)
    assert response.json['message'] == "Permission to 'edit' User was denied."


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_update_roles_disallowed_app(db, app, login):
    """Cannot allow an application which the tenant does not have"""
    payload = {
        'username': 'existing-jan',
        'roles': {
            'dashboard-user': True,
            'logistics-receivings_user': True,
            'pos-device': False,
        },
    }
    response = app.post_json(
        '/tenants/existingtenantid/users/update-roles', payload, expect_errors=True
    )
    assert (
        'Users of account existingtenantid cannot get role logistics'
        in response.json['message']
    )


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_update_roles_with_empty_dict(db, app, login):
    """Give Hans no roles at all"""
    payload = {'username': 'existing-jan', 'roles': {}}
    app.post_json('/tenants/existingtenantid/users/update-roles', payload, status=200)
    user = db.users.find_one({'username': 'existing-jan'})
    assert user['roles']['existingtenantid']['tenant'] == ['dashboard-user']


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_update_roles_with_no_roles(db, app, login):
    """Give Hans no roles at all"""
    payload = {'username': 'existing-jan'}
    response = app.post_json(
        '/tenants/existingtenantid/users/update-roles', payload, expect_errors=True
    )
    assert 'Missing required parameter: roles' in response.json['message']


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_update_roles(db, app, login):
    """Successfully (un)setting roles"""
    # jan has account-admin now, which we unset.
    # He gets two new ones (pos-device & dashboard-user).
    # Unsetting account-admin is not necessary, but doesn't cause an error.
    payload = {
        'username': 'existing-jan',
        'roles': {'pos-device': True, 'dashboard-user': True, 'account-admin': False},
    }
    response = app.post_json(
        '/tenants/existingtenantid/users/update-roles', payload, status=200
    )
    assert (
        'The roles have been set for user existing-jan to ' in response.json['message']
    )
    assert 'pos-device' in response.json['message']
    assert 'dashboard-user' in response.json['message']
    assert 'account-amin' not in response.json['message']

    user = db.users.find_one({'username': 'existing-jan'})
    assert set(user['roles']['existingtenantid']['tenant']) == set(
        ['pos-device', 'dashboard-user']
    )

    aulog = db.spynl_audit_log.find_one({})
    assert 'pos-device' in aulog['message']
    assert 'dashboard-user' in aulog['message']
    assert 'existing-jan' in aulog['message']


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_add_non_existing_role(db, app, login):
    """Setting roles that are not known to Spynl"""
    payload = {
        'username': 'existing-jan',
        'roles': {'pos-device': True, 'dashboard-user': True, 'bloink-admin': True},
    }
    response = app.post_json(
        '/tenants/existingtenantid/users/update-roles', payload, expect_errors=True
    )
    assert 'Unknown role: bloink-admin' in response.json['message']

    aulog = db.spynl_audit_log.find_one({})
    assert 'pos' in aulog['message']
    assert 'dashboard' in aulog['message']
    assert 'existing-jan' in aulog['message']


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_update_roles_wrong_tenant(app, login):
    """Test trying to set a role for a user not of that tenant"""
    payload = {
        'username': 'other_user',
        'roles': {'pos-device': True, 'dashboard-user': True},
    }
    response = app.post_json(
        '/tenants/existingtenantid/users/update-roles', payload, expect_errors=True
    )
    assert (
        'This user does not belong to the requested tenant' in response.json['message']
    )


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_update_roles_master_user(app, login):
    """
    You are not allowed to change roles of a master user. This test is to check
    that the User resource is correctly marked as a restricted resource.
    """
    payload = {
        'username': 'master_username',
        'roles': {'pos-device': True, 'dashboard-user': True},
    }
    response = app.post_json('/tenants/master/users/update-roles', payload, status=403)
    assert (
        'You are not allowed to change this resource for the master tenant'
        in response.json['message']
    )


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_get_roles(app, login):
    """Test getting the roles of a user"""
    payload = {'username': 'other_user'}
    response = app.post_json(
        '/tenants/othertenantid/users/get-roles', payload, status=200
    )
    assert response.json['roles'] == {
        'dashboard-user': True,
        'dashboard-report_user': False,
        'account-admin': False,
        'dashboard-tenant_overview': False,
    }


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_get_roles_wrong_tenant(app, login):
    """Test trying to get a role for a user not of that tenant"""
    payload = {'username': 'other_user'}
    response = app.post_json(
        '/tenants/existingtenantid/users/get-roles', payload, expect_errors=True
    )
    assert (
        'This user does not belong to the requested tenant' in response.json['message']
    )


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_change_active_no_permission(app, login):
    """Change active when not logged in as user with user write permission."""
    payload = {'username': 'existing-jan'}
    response = app.post_json('/users/change-active', payload, expect_errors=True)
    assert response.json['message'] == "Permission to 'edit' User was denied."


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_active_already_active(app, login):
    """Set to true when already true."""
    payload = {'username': 'existing-jan', 'active': True}
    response = app.post_json(
        '/tenants/existingtenantid/users/change-active', payload, status=200
    )
    assert 'User status is already True' in response.json['message']


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_active_change_twice(db, app, mailer_outbox, login):
    """Change to false, change to true."""
    username = 'existing-jan'
    payload = {'username': username}
    response = app.post_json(
        '/tenants/existingtenantid/users/change-active', payload, status=200
    )
    assert (
        'The account of user {} is now deactivated'.format(username)
        in response.json['message']
    )

    user = db.users.find_one({'username': username})
    assert user['active'] is False
    assert 'was deactivated' in mailer_outbox[0].body.data
    # Change back to False
    response = app.post_json(
        '/tenants/existingtenantid/users/change-active', payload, status=200
    )
    assert (
        'The account of user {} is now activated'.format(username)
        in response.json['message']
    )

    user = db.users.find_one({'username': username})
    assert user['active'] is True
    assert 'was activated' in mailer_outbox[1].body.data


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_active_set_twice(db, app, mailer_outbox, login):
    """Set to false, set to true."""
    username = 'existing-jan'
    payload = {'username': username, 'active': False}
    response = app.post_json(
        '/tenants/existingtenantid/users/change-active', payload, status=200
    )
    assert (
        'The account of user {} is now deactivated'.format(username)
        in response.json['message']
    )
    user = db.users.find_one({'username': username})
    assert user['active'] is False
    assert 'was deactivated' in mailer_outbox[0].body.data
    # Change back to False
    payload = {'username': username, 'active': True}
    response = app.post_json(
        '/tenants/existingtenantid/users/change-active', payload, status=200
    )
    assert (
        'The account of user {} is now activated'.format(username)
        in response.json['message']
    )
    user = db.users.find_one({'username': username})
    assert user['active'] is True
    assert 'was activated' in mailer_outbox[1].body.data


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_active_set_false_get(db, app, mailer_outbox, login):
    """Set to false with get."""
    username = 'existing-jan'
    response = app.post_json(
        '/tenants/existingtenantid/users/change-active?'
        'username={}&active=false'.format(username),
        status=200,
    )
    assert (
        'The account of user {} is now deactivated'.format(username)
        in response.json['message']
    )
    user = db.users.find_one({'username': username})
    assert user['active'] is False
    assert 'was deactivated' in mailer_outbox[0].body.data


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_active_set_last_login(db, app, login):
    """
    last_login should not be set when deactivating, but it should be
    set when activating a user. (This test exploits the fact that a
    last_login is not set for existing-jan, because he never logged in.)
    """
    payload = {'username': 'existing-jan', 'active': False}
    app.post_json('/tenants/existingtenantid/users/change-active', payload, status=200)
    user = db.users.find_one({'username': 'existing-jan'})
    assert not user.get('last_login')
    payload = {'username': 'existing-jan', 'active': True}
    app.post_json('/tenants/existingtenantid/users/change-active', payload, status=200)
    user = db.users.find_one({'username': 'existing-jan'})
    assert user.get('last_login')


@pytest.mark.parametrize('login', [('getuser@blah.com', 'blah')], indirect=True)
def test_update_me(db, set_db_1, app, login):
    """Test /update-me endpoint"""
    payload = {'data': {'fullname': 'Juan', 'tz': 'Europe/Barcelona'}}
    response = app.post_json('/update-me?', payload, status=200)

    assert sorted(response.json['affected_fields']) == sorted(['fullname', 'tz'])
    user = db.users.find_one({'email': 'getuser@blah.com'})
    assert user['fullname'] == 'Juan'
    assert user['tz'] == 'Europe/Barcelona'


@pytest.mark.parametrize('login', [('getuser@blah.com', 'blah')], indirect=True)
def test_no_update_me(db, set_db_1, app, login):
    """Test no update /update-me endpoint"""
    payload = {'data': {'xxx': 'blah', 'zzz': 'blah'}}
    response = app.post_json('/update-me?', payload, status=200)

    assert sorted(response.json['affected_fields']) == sorted([])
    assert response.json['message'] == 'Nothing to update.'
    user = db.users.find_one({'email': 'getuser@blah.com'})
    assert user['fullname'] == 'Mister getuser'
    assert user['tz'] == 'Europe/Amsterdam'


def test_failed_update_me(db, set_db_1, app):
    """Test failed /update-me endpoint"""
    payload = {'data': {'xxx': 'blah', 'zzz': 'blah'}}
    response = app.post_json('/update-me?', payload, status=403)

    assert response.json['message'] == (
        'Anonymous access is not allowed to this resource.'
    )
    user = db.users.find_one({'email': 'getuser@blah.com'})
    assert user['fullname'] == 'Mister getuser'
    assert user['tz'] == 'Europe/Amsterdam'


def test_change_username(db, set_db, app):
    """Change own username"""
    user_id = ObjectId()
    mkuser(db, 'user', '0' * 10, ['existingtenantid'], custom_id=user_id)
    app.get('/login?username=user&password=0000000000')
    app.get('/change-username?username=user2', status=200)
    assert db.users.count_documents({'_id': user_id, 'username': 'user2'}) == 1


def test_change_other_username(db, set_db, app):
    """Change username of other user should fail"""
    user_id = ObjectId()
    mkuser(db, 'user', '0' * 10, ['existingtenantid'], custom_id=user_id)

    user_id2 = ObjectId()
    mkuser(db, 'user2', '0' * 10, ['existingtenantid'], custom_id=user_id2)
    app.get('/login?username=user2&password=0000000000')

    app.get('/change-username?username=user3&userId=%s' % user_id, status=403)


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_invalid_username(db, set_db, app, login):
    """Change username of other user should succeed if you have sw-admin"""
    app.get('/change-username?username=__user2', status=400)


@pytest.mark.parametrize(
    'login', [('master_username-consultant', 'blah4')], indirect=True
)
def test_change_other_username_as_consultant(db, set_db, app, login):
    user_id = ObjectId()
    mkuser(db, 'user', '0' * 10, ['existingtenantid'], custom_id=user_id)
    app.get('/change-username?username=user2&userId=%s' % user_id, status=403)


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_other_username_as_master(db, set_db, app, login):
    """Change username of other user should succeed if you have sw-admin"""
    user_id = ObjectId()
    mkuser(db, 'user', '0' * 10, ['existingtenantid'], custom_id=user_id)

    app.get('/change-username?username=user2&userId=%s' % user_id, status=200)
    assert db.users.count_documents({'_id': user_id, 'username': 'user2'}) == 1


def test_change_username_mail(db, set_db, app, mailer_outbox):
    """Change username should send a notification mail."""
    user_id = ObjectId()
    mkuser(db, 'user', '0' * 10, ['existingtenantid'], custom_id=user_id)
    app.get('/login?username=user&password=0000000000')
    app.get('/change-username?username=user2', status=200)
    email = mailer_outbox[0].body.data
    assert (
        'Hello Mister user' in email
        and 'This is a notification that your username has been changed from user to '
        'user2' in email
    )
