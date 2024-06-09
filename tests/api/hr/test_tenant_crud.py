""" tests for tenant crud views """

import pytest
from bson import ObjectId
from pyramid.authorization import DENY_ALL, Allow

from spynl.api.auth.resources import Tenants
from spynl.api.auth.testutils import mkuser

UID_1 = ObjectId()
UID_2 = ObjectId()
UID_MASTER = ObjectId()


@pytest.fixture
def set_db(db):
    """Fill in the database some data for the tests."""
    # need more than one tenant to check filtering:
    db.tenants.insert_one(
        {
            '_id': 'tenant1',
            'name': 'Tenant 1',
            'applications': ['pos', 'webshop', 'account'],
            'not_in_whitelist': 'bla',
            'vatNumber': '123',
        }
    )
    db.tenants.insert_one(
        {'_id': 'tenant2', 'name': 'Tenant 2', 'applications': ['pos', 'account']}
    )
    db.tenants.insert_one(
        {'_id': 'tenant3', 'name': 'Tenant 3', 'applications': ['pos']}
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})

    mkuser(
        db,
        'user1',
        'blah',
        ['tenant1', 'tenant2'],
        tenant_roles={'tenant1': ['account-admin'], 'tenant2': ['account-admin']},
    )
    mkuser(db, 'user2', 'blah', ['tenant2'])
    mkuser(
        db,
        'master_user',
        'blah',
        ['master'],
        def_app={'master': 'pos'},
        tenant_roles={'master': ['sw-admin']},
    )


@pytest.fixture
def add_roles(monkeypatch):
    """
    add extra roles to the Tenants resource, so we can also test that the tenant
    crud endpoints work for normal users, in case we want to add them to the
    acl.
    """
    patched_acl = [
        (Allow, 'role:account-admin', ('read', 'edit', 'add')),
        (Allow, 'role:sw-finance', ('read', 'edit', 'add')),
        (Allow, 'role:sw-admin', ('read', 'edit', 'add')),
        (Allow, 'role:sw-servicedesk', 'read'),
        DENY_ALL,
    ]
    monkeypatch.setattr(Tenants, '__acl__', patched_acl)


@pytest.mark.parametrize(
    'login', [('user1', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_no_agg_endpoint_found(app, set_db, login):
    """No agg endpoint should be defined for Tenants"""
    response = app.get('/tenants/agg', expect_errors=True)
    assert response.json['message'] == ("No endpoint found for path" " '/tenants/agg'.")


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_get_data_is_whitelisted(app, set_db, login):
    """test that get only shows whitelisted properties"""
    response = app.get('/tenants')
    tenant = response.json['data'][0]
    for entry in ('_id', 'applications', 'vatNumber'):
        assert entry in tenant
    assert 'not_in_whitelist' not in tenant


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_edit_tenant_missing_params(app, set_db, login):
    """Edit a tenant without passing the data parameter"""
    response = app.get('/tenants/tenant2/tenants/edit', expect_errors=True)
    assert response.json['type'] == 'MissingParameter'
    assert 'Missing required parameter: data' in response.json['message']


@pytest.mark.parametrize(
    'login', [('user2', 'blah', dict(tenant_id='tenant2'))], indirect=True
)
def test_edit_tenant_without_access_roles(app, set_db, login):
    """test no access with roles"""
    response = app.get('/tenants/edit?_id=tenant2&data={vat:number}', status=403)
    assert response.json['type'] == 'HTTPForbidden'
    assert "Permission to 'edit' Tenants was denied." in response.json['message']


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_master_user_can_edit_tenant(app, set_db, db, login):
    """master user can edit any tenant"""
    response = app.get('/tenants/tenant2/tenants/edit?data={bic:number}', status=200)
    assert response.json['affected_fields'] == ['bic']
    tenant = db.tenants.find_one({'_id': 'tenant2'})
    assert tenant['bic'] == 'number'


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_cannot_edit_settings(app, set_db, login):
    """master user cannot edit fields that are not on the whitelist"""
    app.get('/tenants/tenant2/tenants/edit?data={settings:{bla:bla}}', status=400)


@pytest.mark.parametrize('login', [('master_user', 'blah')], indirect=True)
def test_edit_whitelisted_and_not_whitelisted(app, set_db, db, login):
    """fields that are not whitelisted are skipped"""
    data = '{settings:{bla:bla}, bic:number}'
    response = app.get(
        '/tenants/tenant2/tenants/edit?&data={}'.format(data), status=200
    )
    assert response.json['affected_fields'] == ['bic']
    tenant = db.tenants.find_one({'_id': 'tenant2'})
    assert tenant['bic'] == 'number'


@pytest.mark.parametrize(
    'login', [('user1', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_get_only_current_tenant(app, set_db, add_roles, login):
    """test that get only gets the current tenant when acl is monkeypatched"""
    response = app.get('/tenants')
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['_id'] == 'tenant1'


@pytest.mark.parametrize(
    'login', [('user1', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_try_to_get_wrong_tenant(app, set_db, add_roles, login):
    """test that get only gets the current tenant when acl is monkeypatched"""
    response = app.get('/tenants/tenant3/tenants', status=403)
    assert 'You cannot access this endpoint for shared data' in response.json['message']


@pytest.mark.parametrize(
    'login', [('user1', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_edit_wrong_tenant(app, set_db, add_roles, login):
    """
    user 1 is not allowed to edit tenant2 when logged in for tenant1 when
    acl is monkeypatched
    """
    response = app.get('/tenants/tenant2/tenants/edit?data={vat:number}', status=403)
    assert response.json['type'] == 'HTTPForbidden'
    assert 'You cannot access this endpoint for shared data' in response.json['message']


@pytest.mark.parametrize('login', [('user1', 'blah')], indirect=True)
def test_normal_user_can_edit(app, set_db, db, add_roles, login):
    """normal user can edit a tenant when acl is monkeypatched"""
    response = app.get('/tenants/tenant1/tenants/edit?data={bic:number}', status=200)
    assert 'Updated account tenant1' in response.json['message']
    assert response.json['affected_fields'] == ['bic']
    tenant = db.tenants.find_one({'_id': 'tenant1'})
    assert tenant['bic'] == 'number'
