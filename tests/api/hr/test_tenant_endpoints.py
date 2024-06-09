"""Tests for special endpoints for user management."""


from datetime import datetime

import pytest
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl_schemas.tenant import Tenant

from spynl.api.auth.testutils import mkuser
from spynl.api.hr.resources import AccountResource
from spynl.api.hr.tenant_endpoints import (
    OWNER_ALLOWED_EDIT_FIELDS,
    OWNER_ALLOWED_READ_FIELDS,
    get_current,
    save_current,
)

HANS_ID = ObjectId()
JAN_ID = ObjectId()
MASTER_ID = ObjectId()
UNKNOWN_ID = ObjectId()
TENANT_ID = 'existingtenantid'


@pytest.fixture(autouse=True)
def set_db(db):
    """
    Fill in the database with one company, its owner and one employee.

    We are setting up an existing company with one existing user who is
    owner and one existing user who is employee.
    We also note what new user and company names we'll use.
    """
    db.tenants.insert_one(
        dict(
            _id=TENANT_ID,
            name='Old Corp.',
            active=True,
            applications=['account', 'dashboard', 'pos'],
            retail=True,
            # unknown-owner is added to test that application
            # access is still given, even if one of the owners
            # is unkown.
            owners=[HANS_ID, UNKNOWN_ID],
            chamber_no='foo',
            addresses=[
                dict(
                    primary=True,
                    type='other',
                    city='foo',
                    street='foo',
                    zipcode='foo',
                    houseno='foo',
                    country='foo',
                )
            ],
            created=dict(
                user=dict(_id=HANS_ID, username='foo'),
                action='foo',
                date=datetime.utcnow(),
            ),
        )
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    mkuser(
        db,
        'existing-hans',
        'blah',
        [TENANT_ID],
        custom_id=HANS_ID,
        tenant_roles={TENANT_ID: ['account-admin']},
    )
    mkuser(
        db,
        'existing-jan',
        'blah',
        [str(TENANT_ID)],
        custom_id=JAN_ID,
        tenant_roles={TENANT_ID: ['account-admin']},
        user_type='standard',
    )
    mkuser(
        db,
        'master_username',
        'blah4',
        ['master'],
        custom_id=MASTER_ID,
        tenant_roles={'master': ['sw-admin']},
    )
    mkuser(
        db,
        'account_manager',
        'blah4',
        ['master'],
        tenant_roles={'master': ['sw-account_manager']},
    )
    db.spynl_audit_log.delete_many({})


@pytest.fixture
def request_(spynl_data_db):
    """Return a ready pyramid fake request."""
    return DummyRequest(
        json_body={}, json_payload={}, db=spynl_data_db, args={}, current_tenant_id=None
    )


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_ownership(app, db, mailer_outbox, login):
    """Change ownership. Test mail and audit log."""
    payload = {'username': 'existing-jan', 'is_owner': True}
    app.post_json(
        '/tenants/existingtenantid/tenants/change-ownership', payload, status=200
    )
    # check actual tenant list
    tenant = db.tenants.find_one({"_id": "existingtenantid"})
    assert set(tenant.get('owners')) == {HANS_ID, JAN_ID, UNKNOWN_ID}
    # check email sent to owner(s)
    assert len(mailer_outbox) == 2
    recipients = mailer_outbox[0].recipients + mailer_outbox[1].recipients
    recipients.sort()
    assert recipients == ['existing-hans@blah.com', 'existing-jan@blah.com']
    for mail in mailer_outbox:
        assert "User existing-jan is now an owner of Old Corp." in mail.subject
        assert (
            "the user account existing-jan was given ownership of the "
            "account 'Old Corp.'"
        ) in mail.body.data
    # check audit log
    aulog = db.spynl_audit_log.find_one({})
    assert aulog['message'] == (
        "Attempt to change ownership of user " "<existing-jan> to <True>."
    )


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_ownership_nochange(app, db, mailer_outbox, login):
    """Changes to ownership of jan and hans that already are that way."""
    payload = {'username': 'existing-jan', 'is_owner': False}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-ownership', payload, status=200
    )
    assert response.json['message'] == 'User is not among the list of owners.'

    payload = {'username': 'existing-hans', 'is_owner': True}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-ownership', payload, status=200
    )
    assert response.json['message'] == 'User is already an owner.'

    tenant = db.tenants.find_one({"_id": "existingtenantid"})
    assert tenant.get('owners') == [HANS_ID, UNKNOWN_ID]


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_ownership_no_email(app, db, login):
    """Try to change ownership to user that has no email"""
    db.users.update_one({'username': 'existing-jan'}, {'$set': {'email': None}})
    payload = {'username': 'existing-jan', 'is_owner': True}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-ownership', payload, status=400
    )
    assert 'An owner should always have an email address.' in response.json['message']


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_ownership_email_not_verified(app, db, login):
    """Try to change ownership to user that has no email"""
    db.users.update_one(
        {'username': 'existing-jan'}, {'$set': {'email_verify_pending': True}}
    )
    payload = {'username': 'existing-jan', 'is_owner': True}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-ownership', payload, status=400
    )
    assert 'is not verified yet' in response.json['message']


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_change_ownership_nopermission(app, db, login):
    """Hans attempts to remove hans' ownership but is not allowed to."""
    # TODO: for the my app, we might allow owners (like Hans) to do this.
    payload = {'username': 'existing-hans', 'is_owner': False}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-ownership',
        payload,
        expect_errors=True,
    )
    assert response.json['message'] == ("Permission to 'edit' Tenants was " "denied.")
    tenant = db.tenants.find_one({"_id": "existingtenantid"})
    assert tenant.get('owners') == [HANS_ID, UNKNOWN_ID]


@pytest.mark.parametrize('login', [('master_username', 'blah4')], indirect=True)
def test_change_ownership_master_tenant(app, db, login):
    """
    You are not allowed to change the ownership of the master tenant.
    This test is to check that the Tenants resource is correctly marked as a
    restricted resource.
    """
    payload = {'username': 'existing-hans', 'is_owner': False}
    response = app.post_json(
        '/tenants/master/tenants/change-ownership', payload, status=403
    )
    assert (
        'You are not allowed to change this resource for the master tenant'
        in response.json['message']
    )


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_get_owners_no_permissions(db, app, login):
    """You need read permission on the tenants collection"""
    response = app.get(
        '/tenants/existingtenantid/tenants/get-owners', expect_errors=True
    )
    assert "Permission to 'read' Tenants was denied." in response.json['message']


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_get_owners_master(db, app, login):
    """A super user can query the owners of another tenant"""
    response = app.get('/tenants/existingtenantid/tenants/get-owners', status=200)
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['username'] == 'existing-hans'
    assert response.json['data'][0]['active'] is True


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_give_application_access(app, db, mailer_outbox, login):
    """Give access to crm application. Test mail and audit log."""
    payload = {'application': 'crm', 'has_access': True}
    app.post_json(
        '/tenants/existingtenantid/tenants/change-application-access',
        payload,
        status=200,
    )

    # check actual tenant list
    tenant = db.tenants.find_one({"_id": "existingtenantid"})
    assert tenant['applications'] == ['account', 'dashboard', 'pos', 'crm']
    # check email sent to owner (hans)
    assert len(mailer_outbox) == 1
    recipients = mailer_outbox[0].recipients
    assert recipients == ['existing-hans@blah.com']
    mail = mailer_outbox[0]
    assert (
        "Old Corp. has now access to application Customer Relationship" " Management"
    ) in mail.subject
    assert 'Hello Mister existing-hans' in mail.body.data
    assert (
        "the account Old Corp. was given access to the application "
        "'Customer Relationship Management'."
    ) in mail.body.data
    assert (
        'You can now select this application from the Softwear Connect main menu'
    ) in mail.body.data
    # check audit log
    aulog = db.spynl_audit_log.find_one({})
    assert aulog['message'] == (
        "Attempt to change access to application " "'crm' to <True>."
    )


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_revoke_application_access(app, db, login):
    """Revoke application access for dashboard."""
    payload = {'application': 'dashboard', 'has_access': False}
    app.post_json(
        '/tenants/existingtenantid/tenants/change-application-access',
        payload,
        status=200,
    )
    # check actual tenant list
    tenant = db.tenants.find_one({"_id": "existingtenantid"})
    assert tenant.get('applications') == ['account', 'pos']


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_app_access_nochange(app, db, mailer_outbox, login):
    """Changes to application which already are that way."""
    payload = {'application': 'crm', 'has_access': False}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-application-access',
        payload,
        status=200,
    )
    assert response.json['message'] == (
        'This account does not have access to this application.'
    )

    payload = {'application': 'pos', 'has_access': True}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-application-access',
        payload,
        status=200,
    )
    assert response.json['message'] == (
        'This account already has access to this application.'
    )
    tenant = db.tenants.find_one({"_id": "existingtenantid"})
    assert tenant.get('applications') == ['account', 'dashboard', 'pos']
    assert len(mailer_outbox) == 0


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_app_access_default(app, db, login):
    """You cannot change access of default apps."""
    payload = {'application': 'account', 'has_access': True}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-application-access',
        payload,
        status=400,
    )
    assert response.json['message'] == (
        'You cannot change access to a default application.'
    )


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_change_app_access_internal(app, db, login):
    """You cannot change access of default apps."""
    payload = {'application': 'admin', 'has_access': True}
    response = app.post_json(
        '/tenants/existingtenantid/tenants/change-application-access',
        payload,
        status=400,
    )
    assert response.json['message'] == (
        'You cannot change access to an internal application.'
    )


@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_get_applications_master(db, app, login):
    """A super user can query the applications of another tenant"""
    response = app.get('/tenants/existingtenantid/tenants/get-applications', status=200)
    # all apps minus default and internal apps:
    assert len(response.json['data']) == 11
    for app in response.json['data']:
        if app['id'] in ['dashboard', 'pos']:
            assert app['has_access'] is True
        else:
            assert app['has_access'] is False


def test_saving_own_tenant_with_only_the_whitelisted_fields(
    config, request_, spynl_data_db
):
    config.begin(request=request_)  # make aware configurator of our request
    request_.args['data'] = 'foo'  # bypass the @required_args
    request_.current_tenant_id = TENANT_ID

    _address = dict(
        primary=True,
        type='other',
        city='bar',
        street='bar',
        zipcode='BAR',
        houseno='BAR',
        country='bar',
    )
    tenant = dict(name='bar', addresses=[_address])

    request_.json_payload['data'] = tenant
    save_current(AccountResource(request_), request_)
    doc = spynl_data_db.tenants.find_one(dict(_id=TENANT_ID))
    assert all(
        doc[k] == v and k in OWNER_ALLOWED_EDIT_FIELDS for k, v in tenant.items()
    )


def test_saving_own_tenant_leaving_out_fields(config, request_, spynl_data_db):
    config.begin(request=request_)  # make aware configurator of our request
    request_.args['data'] = 'foo'  # bypass the @required_args
    request_.current_tenant_id = TENANT_ID

    payload = {
        'bic': '12345678',
        'name': 'blah',
        'bankAccountName': '1',
        'legalname': 'blah',
        'bankAccountNumber': '1',
        'addresses': [
            dict(
                primary=True,
                type='other',
                city='bar',
                street='bar',
                zipcode='BAR',
                houseno='bar',
                country='bar',
            )
        ],
    }

    request_.json_payload['data'] = payload

    save_current(AccountResource(request_), request_)
    tenant = spynl_data_db.tenants.find_one(dict(_id=TENANT_ID))

    unset = ['bic', 'bankAccountNumber', 'bankAccountName']
    for k in unset:
        request_.json_payload['data'].pop(k)

    save_current(AccountResource(request_), request_)
    tenant_after = spynl_data_db.tenants.find_one(dict(_id=TENANT_ID))

    assert all([tenant[k] == v for k, v in payload.items()]) and all(
        [k not in tenant_after for k in unset]
    )


def test_saving_own_tenant_with_field_that_isnt_in_whitelist(
    config, request_, spynl_data_db
):
    config.begin(request=request_)  # make aware configurator of our request
    request_.args['data'] = 'foo'  # bypass the @required_args
    request_.current_tenant_id = TENANT_ID  # set the tenant in the request

    _address = dict(
        primary=True,
        type='other',
        city='bar',
        street='bar',
        zipcode='bar',
        houseno='bar',
        country='bar',
    )
    # just check that the field isnt in the list but is defined in tenant schema so the
    # test case is valuable
    assert 'retail' not in OWNER_ALLOWED_EDIT_FIELDS and 'retail' in Tenant().fields
    tenant = dict(name='bar', addresses=[_address], retail=False)
    request_.json_payload['data'] = tenant
    save_current(AccountResource(request_), request_)

    tenant = spynl_data_db.tenants.find_one({'_id': TENANT_ID})
    assert tenant['retail'] is not False


def test_saving_own_tenant_with_additional_fields_drops_them(
    config, request_, spynl_data_db
):
    config.begin(request=request_)  # make aware configurator of our request
    request_.args['data'] = 'foo'  # bypass the @required_args
    request_.current_tenant_id = TENANT_ID  # set the tenant in the request

    _address = dict(
        primary=True,
        type='other',
        city='bar',
        street='bar',
        zipcode='bar',
        houseno='bar',
        country='bar',
    )
    tenant = dict(name='bar', addresses=[_address], foo='bar', legalname='123123')
    request_.json_payload['data'] = tenant
    save_current(AccountResource(request_), request_)

    tenant = spynl_data_db.tenants.find_one({'_id': TENANT_ID})
    assert 'foo' not in tenant


def test_getting_own_tenant_document_returns_only_the_whitelisted_allowed_fields(
    request_,
):
    request_.current_tenant_id = TENANT_ID
    data = get_current(AccountResource(request_), request_)['data']
    assert data.keys() <= set(OWNER_ALLOWED_READ_FIELDS)


def test_saving_all_fields(config, request_, spynl_data_db):
    config.begin(request=request_)  # make aware configurator of our request
    request_.args['data'] = 'foo'  # bypass the @required_args
    request_.current_tenant_id = TENANT_ID  # set the tenant in the request

    _address = dict(
        primary=True,
        type='other',
        city='bar',
        street='bar',
        zipcode='bar',
        houseno='bar',
        country='bar',
    )

    tenant = {
        'addresses': [_address],
        'bankAccountName': 'INGG',
        'name': 'MaddoxX DEV TEST3',
        'bankAccountNumber': '',
        'vat': 'hello',
        'gln': '1111111111111',
        'bic': '11111111',
        'legalname': 'blah',
    }
    request_.json_payload['data'] = tenant
    save_current(AccountResource(request_), request_)

    tenant = spynl_data_db.tenants.find_one({'_id': TENANT_ID})
    assert 'foo' not in tenant


@pytest.mark.parametrize(
    "data",
    [
        {},
        {'posInstanceId': 1},
        {'posInstanceId': 1, 'salesOrder': 2},
        {'posInstanceId': 1, 'salesOrder': 2, 'packingList': 3},
        {'posInstanceId': 1, 'salesOrder': 2, 'packingList': 3, 'invoce': 4},
    ],
)
@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_get_tenant_counters(db, app, login, data):
    db.tenants.update_one({'_id': 'master'}, {'$set': {'counters': data}})
    response = app.get('/tenants/get-counters')
    assert response.json['data'] == data


@pytest.mark.parametrize(
    "db_data,data_in",
    [
        ({}, {'salesOrder': 4}),
        ({'salesOrder': 1}, {'salesOrder': 4}),
        ({'posInstanceId': 1, 'salesOrder': 1}, {'salesOrder': 4}),
    ],
)
@pytest.mark.parametrize(
    'login', [('master_username', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_save_tenant_counters(db, app, login, db_data, data_in):
    response = app.post_json('/tenants/existingtenantid/tenants/save-counters', data_in)
    assert response.json['data'] == data_in


@pytest.mark.parametrize(
    'login', [('account_manager', 'blah4', dict(tenant_id='master'))], indirect=True
)
def test_set_country_code(db, app, login):
    data = {'countryCode': 'DE'}
    response = app.post_json(
        '/tenants/existingtenantid/account-manager/set-country-code',
        {'data': data},
        status=200,
    )
    assert response.json['data'] == data

    tenant = db.tenants.find_one({'_id': 'existingtenantid'})
    assert tenant['countryCode'] == 'DE'
