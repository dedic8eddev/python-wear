"""
Authorization tests.
We need to test if our ACL mechanism correctly applies to users,
when they access certain resources and need certain permissions.

In particular, we test things we implement in a custom manner
for our use case:
* Cross-tenant access: a user specifies a tenant he is not working under
* Conditionals on the documents returned for each ACL if it applies TODO
* Field-level access TODO

The resources we test are in spynl.auth.testutils.
"""

import bson
import pytest
from pyramid.authorization import Allow

from spynl.main.routing import Resource

from spynl.api.auth.plugger import includeme
from spynl.api.auth.testutils import login, make_auth_header, mkuser

# not interested in authentication here, so all test users have the same pwd
pwd = 'pustekuchen'


@pytest.fixture(autouse=True)
def set_db(db):
    """Fill the database with tenants and users for tests."""
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
            'applications': ['pos', 'dashboard'],
        }
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    db.tenants.insert_one({'_id': 'b2b', 'name': 'B2B'})

    mkuser(db, 'user_with_nonexistant_tenant', pwd, ['00000'], tenant_roles={})
    mkuser(db, 'poor_user', pwd, ['inactive_tenant_id'], tenant_roles={})
    mkuser(
        db,
        'dummy_user',
        pwd,
        ['a_tenant_id', 'another_tenant_id'],
        tenant_roles={
            'a_tenant_id': ['pos-device'],
            'another_tenant_id': ['dashboar-user'],
        },
        def_app={'a_tenant_id': 'pos', 'another_tenant_id': 'reporting'},
        owns=['another_tenant_id'],
    )
    mkuser(
        db, 'master_user', pwd, ['master'], tenant_roles={'master': ['sw-servicedesk']}
    )
    mkuser(
        db,
        'dashboard_user',
        pwd,
        ['a_tenant_id'],
        tenant_roles={'a_tenant_id': ['pos-device', 'dashboard-user']},
    )


# Fixtures etc needed for test using token authentication
USERID = bson.ObjectId()


def patched_includeme(config):
    class TestResource(Resource):
        """Represents POS resources"""

        collection = 'dummy_pos'
        paths = ['test']

        __acl__ = [(Allow, 'role:pos-device', ('read',))]

    includeme(config)
    config.add_endpoint(lambda _: {}, '/', context=TestResource, permission='read')


def test_no_permission_required(app):
    """access an endpoint which is free for all"""
    app.get('/public/open', status=200)


# Test check 1 of permits:
def test_options_request(app):
    """
    The frontend should be able to send options requests without logging in.
    """
    response = app.options('/test-dashboard', status=200)
    headers = response.headers
    for header in [
        ('Access-Control-Allow-Methods', 'GET,POST'),
        ('Access-Control-Max-Age', '86400'),
        ('Access-Control-Allow-Credentials', 'true'),
    ]:
        assert header[0] in headers
        assert header[1] in headers.getall(header[0])


# Test check 2 of permits:
def test_authenticated_denied(app):
    """
    test that access is denied to an authenticated endpoint when not
    authenticated.
    """
    response = app.get('/authenticated', status=403)
    assert 'Anonymous access' in response.json['message']


# Test check 3  of permits:
def test_authenticated_allowed(app):
    """
    test that access is allowed to an authenticated endpoint when
    authenticated.
    """
    response = app.get('/login', dict(username='dummy_user', password=pwd))
    response = app.get('/authenticated', status=200)
    assert 'This is an authenticated view.' in response.json['message']


# Test check 4 of permits:
def test_access_tenant_not_allowed(app, db):
    """
    dashboard user logs in with a_tenant_id, but then this tenant_id
    gets removed from his allowed tenants. user can no longer access
    dashboard.
    """
    params = dict(username='dashboard_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='a_tenant_id', sid=response.json['sid'])
    app.get('/set-tenant', params)

    app.get('/test-dashboard', status=200)
    db.users.update_one({'username': 'dashboard_user'}, {'$set': {'tenant_id': []}})
    response = app.get('/test-dashboard', status=403)
    assert 'You do not have access' in response.json['message']
    db.users.update_one(
        {'username': 'dashboard_user'}, {'$set': {'tenant_id': ['a_tenant_id']}}
    )


# Test check 5 of permits:
def test_work_on_inactive_tenant(app):
    """
    A regular user can not even login on an inactive tenant.

    In this case we do not actually test the authorization, because
    it gets denied during login. However because we cannot test this
    directly, we keep this test in case we change the login. Then this
    test should be changed to fail during authorization check 5.
    """
    params = dict(username='poor_user', password=pwd)
    response = app.get('/login', params, expect_errors=True)
    assert "no access to active accounts" in response.json["message"]


def test_tenant_does_not_exist(app):
    """
    Tenant does not exist

    This test has the same problem as the test above.
    """
    app.post_json(
        '/login',
        {'username': 'user_with_nonexistant_tenant', 'password': pwd},
        status=403,
    )


def test_tenant_inactive_token(app, spynl_data_db):
    """
    Test access denied when the current tenant is not active.

    Because we cannot properly test check 5 with session authentication, (see
    docstring test_work_on_inactive_tenant), we test it with token
    authentication.
    """
    spynl_data_db.users.insert_one({'_id': USERID, 'active': True})
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    response = app.get('/test-pos', headers=headers, status=403)
    assert 'The current account (1) is not active.' in response.json['message']


def test_tenant_becomes_inactive(app, db):
    """
    if a tenant becomes inactive after the user logged in, the user
    should no longer be permitted access.
    """
    params = dict(username='dashboard_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='a_tenant_id', sid=response.json['sid'])
    app.get('/set-tenant', params)

    app.get('/test-dashboard', status=200)
    db.tenants.update_one({'_id': 'a_tenant_id'}, {'$set': {'active': False}})
    response = app.get('/test-dashboard', status=403)
    assert response.json['message'] == (
        'The current account (a_tenant_id) is not active.'
    )
    db.tenants.update_one({'_id': 'a_tenant_id'}, {'$set': {'active': True}})


# Test check 6 of permits:
def test_requested_tenant_master_access(app):
    """
    Test that a master user can access a different tenant
    """
    params = dict(username='master_user', password=pwd)
    app.get('/login', params)
    app.get('/tenants/another_tenant_id/test-dashboard', status=200)


def test_work_on_inactive_tenant_master_user(app):
    """a master user can work on an inactive tenant"""
    params = dict(username='master_user', password=pwd)
    app.get('/login', params)
    app.get('/tenants/inactive_tenant_id/test-reporting', status=200)


@pytest.mark.skip(reason='to be implemented')
def test_access_b2b_resource(app, db):
    """successfully access a b2b resource"""
    login(app, 'dummy_user', pwd, 'another_tenant_id')
    response = app.get('/tenants/b2b/test-shared/get', status=200)
    assert 'You accessed SharedResource' in response.json['message']


# 6a
def test_no_b2b_resource(app):
    """
    Test that a user cannot access another tenant's data by setting the
    requested_tenant.
    """
    params = dict(username='dashboard_user', password=pwd)
    response = app.get('/login', params)
    response = app.get('/tenants/another_tenant_id/test-dashboard', status=403)
    assert 'You cannot access this endpoint for shared data' in response.json['message']


def test_nob2b_resource_with_b2b_access(app):
    """
    This user does have a connection with the requested tenant, and the correct
    role, but tries to access this via an non b2b resource.
    """
    login(app, 'dummy_user', pwd, 'another_tenant_id')
    response = app.get('/tenants/b2b/test-reporting', status=403)
    assert 'You cannot access this endpoint for shared data' in response.json['message']


# 6b
def test_requested_tenant_inactive(app):
    """deny access because the requested tenant is inactive"""
    login(app, 'dummy_user', pwd, 'another_tenant_id')
    response = app.get('/tenants/inactive_tenant_id/test-shared/get', status=403)
    assert (
        'The requested account (inactive_tenant_id) is not active'
        in response.json['message']
    )


# 6c
def test_requested_tenant_no_access(app):
    """deny access if there is no known connection"""
    login(app, 'dummy_user', pwd, 'a_tenant_id')
    response = app.get('/tenants/b2b/test-shared/get', status=403)
    assert (
        'You do not have access to shared data of account b2b.'
        in response.json['message']
    )


# Test check 7 of permits:
def test_edit_not_protected_resource(app):
    """requested tenant is master, context is not restricted"""
    login(app, 'master_user', pwd)
    app.get('/tenants/master/test-dashboard', status=200)


def test_edit_protected_resource_normal_tenant(app):
    """master user can edit for normal tenant"""
    login(app, 'master_user', pwd)
    app.get('/tenants/a_tenant_id/users/test_edit', status=200)


def test_read_protected_resource_master_tenant(app):
    """master user can edit for normal tenant"""
    login(app, 'master_user', pwd)
    app.get('/tenants/master/users/test_get', status=200)


def test_edit_protected_resource_master_tenant(app):
    """master user can edit for normal tenant"""
    login(app, 'master_user', pwd)
    response = app.get('/tenants/master/users/test_edit', status=403)
    assert (
        'You are not allowed to change this resource for the master tenant'
        in response.json['message']
    )


# Test check 8 of permits:
def test_read_public_resource(app):
    """
    read an endpoint which is public to all authenticated users.

    In this case the Authenticated permission is not set when registering
    the endpoint, but in the ACL of the resource. (this is why this test
    is for check 7 and not check 3)
    """
    params = dict(username='dummy_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='a_tenant_id', sid=response.json['sid'])
    app.get('/set-tenant', params)
    app.get('/public/get', status=200)


def test_permission_denied(app):
    """User role does not include the needed write permission"""
    params = dict(username='dummy_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='a_tenant_id', sid=response.json['sid'])
    app.get('/set-tenant', params)
    response = app.get('/public/update', status=403)
    assert response.json['type'] == 'HTTPForbidden'
    assert "Permission to 'edit' PublicResource was denied" in response.json['message']


def test_role_access(app):
    """dummy-user can access POS but not dashboard.
    dashboard-user can access both."""
    params = dict(username='dummy_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='a_tenant_id', sid=response.json['sid'])
    app.get('/set-tenant', params)
    app.get('/test-pos', status=200)
    response = app.get('/test-dashboard', status=403)
    assert (
        "Permission to 'edit' DashboardResource was denied" in response.json['message']
    )

    params = dict(username='dashboard_user', password=pwd)
    response = app.get('/login', params)
    params = dict(id='a_tenant_id', sid=response.json['sid'])
    app.get('/set-tenant', params)
    app.get('/test-pos', status=200)
    app.get('/test-dashboard', status=200)
