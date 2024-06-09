import csv_strings
import pytest
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.api.auth.authentication import challenge
from spynl.api.auth.testutils import login, mkuser
from spynl.api.hr.account_provisioning import get_data_from_csv


@pytest.fixture()
def set_db(db):
    """fill the db"""
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    db.tenants.insert_one({'_id': 'existing', 'name': 'Existing tenant'})
    mkuser(
        db,
        'master_user',
        'blah4',
        ['master'],
        custom_id=ObjectId(),
        tenant_roles={'master': ['sw-account_manager', 'pos-device']},
    )


@pytest.fixture
def request_(spynl_data_db):
    DummyRequest.db = spynl_data_db
    return DummyRequest


def test_get_data_from_csv_get_all_tables():
    data = get_data_from_csv(csv_strings.csv_2)
    assert len(data) == 4
    assert len(data['tenants']) == 2
    assert len(data['users']) == 2
    assert len(data['cashiers']) == 3
    assert len(data['warehouses']) == 0


def test_get_data_from_csv_get_some_tables():
    data = get_data_from_csv(csv_strings.csv_1)
    assert len(data['tenants']) == 2
    assert 'warehouses' not in data


def test_import_validation_errors(app, set_db):
    """validation errors in correct format"""
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_lots_of_errors},
        status=400,
    )
    assert csv_strings.markdown_errors in response.json['message']


def test_import_validation_wrong_csv_schema_format(app, set_db):
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_3},
        status=400,
    )
    print(response.json['message'])
    assert response.json['message'].find('Input schema wrong format key') != -1
    assert "users" in response.json['developer_message']
    assert "_schema" in response.json['developer_message']['users']
    assert (
        'Input schema wrong format key: \'tenant_id\''
        in response.json['developer_message']['users']['_schema']
    )


def test_add_owner_new_tenant(app, set_db, db):
    """Test that a tenant and an owner get added properly."""
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_tenant_and_owner},
        status=200,
    )
    owner = db.users.find_one({'username': 'owner_user'})
    tenant = db.tenants.find_one({'_id': '91539'})
    assert tenant['owners'] == [owner['_id']]
    assert owner['type'] == 'standard'
    assert '1 tenant(s) added, 3 user(s) added, ' in response.json['message']


def test_add_owner_existing_tenant(app, set_db, db):
    """Test that an owner gets added properly to an existing tenant."""
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_owner_existing_tenant},
        status=200,
    )
    owner = db.users.find_one({'username': 'owner_user'})
    tenant = db.tenants.find_one({'_id': 'existing'})
    assert tenant['owners'] == [owner['_id']]
    assert owner['type'] == 'standard'
    assert '1 user(s) added, ' in response.json['message']


def test_import_standard_user(app, db, set_db):
    login(app, 'master_user', 'blah4')
    app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_standard_user},
        status=200,
    )
    user = db.users.find_one({'username': 'username'})
    # delete keys we don't want to compare (also tests that they're there)
    for key in ('_id', 'created', 'modified', 'modified_history'):
        user.pop(key, None)
    assert user == csv_strings.standard_user


def test_import_device_user_correct_in_db(app, db, set_db):
    login(app, 'master_user', 'blah4')
    app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_device_user},
        status=200,
    )
    user = db.users.find_one({'username': 'device'})
    # delete keys we don't want to compare (also tests that they're there)
    for key in (
        '_id',
        'created',
        'modified',
        'modified_history',
        'oldPasswords',
        'password_hash',
        'password_salt',
        'hash_date',
        'hash_type',
    ):
        user.pop(key, None)
    assert len(user['deviceId']) == 5
    del user['deviceId']
    assert user == csv_strings.device_user


def test_import_device_user_working_password(app, db, set_db, config, request_):
    login(app, 'master_user', 'blah4')
    app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_device_user},
        status=200,
    )
    assert challenge(request_, 'saarlem1234', username='device')


def test_import_device_user_correct_extra_documents(app, db, set_db):
    login(app, 'master_user', 'blah4')
    app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_device_user},
        status=200,
    )
    user = db.users.find_one({'username': 'device'})
    assert (
        db.pos_settings.count_documents(
            {'user_id': str(user['_id']), 'tenant_id': 'existing'}
        )
        == 1
    )
    assert (
        db.payment_methods.count_documents(
            {'user_id': str(user['_id']), 'tenant_id': 'existing'}
        )
        == 1
    )
    assert db.pos_reasons.count_documents({'tenant_id': 'existing'}) == 1


def test_password_validator(app, set_db):
    """test that it is properly set"""
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_validate_pwd},
        status=400,
    )
    assert (
        'The password should be at least 10 characters long.'
        in response.json['message']
    )
    assert (
        'password-does-not-meet-requirements-min-length' not in response.json['message']
    )


def test_username_validator(app, set_db):
    """test that it is properly set"""
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_validate_username},
        status=400,
    )
    assert (
        'A username may not begin with any of these characters:'
        in response.json['message']
    )
    assert 'may-not-start-with' not in response.json['message']


@pytest.mark.parametrize(
    'role,status',
    [
        ('sw-admin', 400),
        ('sww-api', 400),
        ('owner', 400),
        ('bla', 400),
        ('pos-device', 200),
    ],
)
def test_allowed_roles(app, set_db, role, status):
    login(app, 'master_user', 'blah4')
    csv = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|haarlem|maddoxx.haarlem|bla@email.com||Europe/Amsterdam|standard|{}|53
'''.format(
        role
    )
    app.post_json(
        '/account-provisioning/import', {'account_data_string': csv}, status=status
    )


@pytest.mark.parametrize(
    'application,status', [('admin', 400), ('bla', 400), ('pos', 200)]
)
def test_allowed_applications(app, set_db, application, status):
    login(app, 'master_user', 'blah4')
    csv = '''
[TENANTS]
_id|name|legalname|uploadDirectory|applications|retail|countryCode
91539|MaddoxB Beta|MaddoxB Beta|915393216602765948177|{}|True|NL
'''.format(
        application
    )
    app.post_json(
        '/account-provisioning/import', {'account_data_string': csv}, status=status
    )


def test_add_a_lot_of_documents(app, set_db, db):
    """Check that all documents are added"""
    login(app, 'master_user', 'blah4')

    # do a request to an endpoint that would set our database callbacks,
    # to test that they do get reset for each request, and they do not carry over.
    app.get('/sales/get')

    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_lots_of_documents},
        status=200,
    )

    message = (
        '4 tenant(s) added, 5 user(s) added, 9 cashier(s) added, '
        '11 warehouse(s) added'
    )
    assert message in response.json['message']  # also contains warnings
    assert db.tenants.count_documents({}) == 6  # 4 + existing tenant + master tenant
    assert db.users.count_documents({'tenant_id': {'$ne': 'master'}}) == 5
    assert db.cashiers.count_documents({'tenant_id': {'$ne': 'master'}}) == 9
    assert db.warehouses.count_documents({'tenant_id': {'$ne': 'master'}}) == 11


def test_warn_tenant_without_owner(app, set_db):
    """Test that you get a warning if a tenant is added without an owner"""
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_tenant_no_owner},
        status=200,
    )
    assert response.json['status'] == 'warning'
    assert 'Tenant 91538 does not have an owner.' in response.json['message']


def test_warn_about_tenant_not_having_appropriate_applications(app, set_db):
    """
    Test that a warning is given if a user is added with roles without the
    tenant having the correspongding applications.
    """
    login(app, 'master_user', 'blah4')
    response = app.post_json(
        '/account-provisioning/import',
        {'account_data_string': csv_strings.csv_wrong_applications},
        status=200,
    )
    assert response.json['status'] == 'warning'
    assert (
        "Tenant existing misses apps needed for user roles: ['dashboard']"
        in response.json['message']
    )


def test_warn_set_non_device_password(app, set_db):
    """
    You should get a warning when you try to set a password for a non-device
    user.
    """
    login(app, 'master_user', 'blah4')
    user = '''
[USERS]
tenant_id|username|fullname|email|password|tz|type|roles|wh
existing|peter4|Peter|peter.steenbergen@bla.be|abcdef1234||standard|sales-user|
'''
    response = app.post_json(
        '/account-provisioning/import', {'account_data_string': user}, status=200
    )
    assert response.json['status'] == 'warning'
    assert 'Password for user peter4 was not set.'
