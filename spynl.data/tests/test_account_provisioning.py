import hashlib

import pytest
from marshmallow import ValidationError

from spynl_schemas.account_provisioning import AccountProvisioning as Data
from spynl_schemas.account_provisioning import Cashier, Tenant, User, Warehouse

CONTEXT = {
    'allowed_applications': ['pos', 'reporting'],
    'allowed_roles': ['pos', 'reporting'],
}


def hash_password(password):
    m = hashlib.new('md5')
    m.update(password.encode('utf-8'))
    return m.hexdigest()


# Tenant tests
def test_tenant_every_application_only_gets_added_once():
    data = {'applications': 'pos,reporting,pos,reporting,pos', 'retail': True}
    tenant = Tenant(only=['applications', 'retail'], context=CONTEXT).load(data)
    assert tenant['applications'] == ['pos', 'reporting']


def test_tenant_unknown_application():
    data = {'applications': 'pos,reporting,bla'}
    with pytest.raises(ValidationError) as e:
        Tenant(only=['applications'], context=CONTEXT).load(data)
    assert 'bla' in e.value.messages['applications'][0]


def test_tenant_upload_directory_ends_up_in_settings():
    dir = '0' * 21
    data = {'uploadDirectory': dir, 'retail': True}
    tenant = Tenant(only=['settings', 'retail'], context=CONTEXT).load(data)
    assert tenant['settings']['uploadDirectory'] == dir


def test_tenant_minimally_needed_fields():
    """
    this test is to make sure that the only required fields are the
    ones provided in account provisioning, if this test fails, account
    provisioning will fail
    """
    data = {
        '_id': '123456',
        'name': 'name',
        'legalname': 'legalname',
        'uploadDirectory': '0' * 21,
        'retail': True,
        'countryCode': 'NL',
    }
    Tenant(context=CONTEXT).load(data)


def test_set_country_code():
    """
    this test is to make sure that the only required fields are the
    ones provided in account provisioning, if this test fails, account
    provisioning will fail
    """
    data = {
        '_id': '123456',
        'name': 'name',
        'legalname': 'legalname',
        'uploadDirectory': '0' * 21,
        'retail': True,
        'countryCode': 'NL',
    }
    tenant = Tenant(context=CONTEXT).load(data)
    assert tenant['settings']['vat'] == {'high': 21.0, 'low': 9.0, 'zero': 0.0}


def test_tenant_missing_fields_give_validation_errors():
    """
    test that you only get ValidationErrors if there are fields missing, and
    not e.g. KeyErrors.
    """
    with pytest.raises(ValidationError):
        Tenant(context=CONTEXT).load({})


def test_tenant_validate_retail_wholesale_flag():
    """Retail or wholesale needs to be set to true"""
    data_list = [
        {'retail': True, 'wholesale': False},
        {'retail': False, 'wholesale': True},
        {'retail': True, 'wholesale': True},
    ]
    for data in data_list:
        Tenant(only=['retail', 'wholesale']).load(data)
    with pytest.raises(ValidationError):
        Tenant(only=['retail', 'wholesale']).load({'retail': False, 'wholesale': False})


# Test User
def test_user_every_role_only_gets_added_once():
    data = {
        'roles': 'pos,reporting,pos,reporting,pos',
        'tenant_id': '123456',
        'type': 'device',
    }
    tenant = User(only=['roles', 'type', 'tenant_id'], context=CONTEXT).load(data)
    assert tenant['roles']['123456']['tenant'] == ['pos', 'reporting']


def test_user_unknown_role():
    data = {'roles': 'pos,reporting,bla', 'tenant_id': '123456', 'type': 'device'}
    with pytest.raises(ValidationError) as e:
        User(only=['roles', 'type', 'tenant_id'], context=CONTEXT).load(data)
    assert 'bla' in e.value.messages['roles']['123456']['value']['tenant'][0]


def test_user_minimally_needed_fields():
    """
    this test is to make sure that the only required fields are the
    ones provided in account provisioning, if this test fails, account
    provisioning will fail
    """
    data = {'tenant_id': '123456', 'username': 'username', 'type': 'device'}
    User(context=CONTEXT).load(data)


def test_user_add_multiple_users_multiple_tenants():
    data = [
        {'tenant_id': '123456', 'username': 'username', 'type': 'device'},
        {'tenant_id': '123457', 'username': 'username2', 'type': 'device'},
    ]
    users = User(context=CONTEXT, many=True).load(data)
    assert users[0]['tenant_id'] == ['123456']
    assert users[1]['tenant_id'] == ['123457']


def test_user_missing_fields_give_validation_errors():
    """
    test that you only get ValidationErrors if there are fields missing, and
    not e.g. KeyErrors.
    """
    with pytest.raises(ValidationError):
        User(context=CONTEXT).load({})


# Test Cashier
def test_cashier_minimally_needed_fields():
    """
    this test is to make sure that the only required fields are the
    ones provided in account provisioning, if this test fails, account
    provisioning will fail
    """
    data = {
        'tenant_id': '123456',
        'name': 'name',
        'fullname': 'fullname',
        'password': '45',
    }
    Cashier().load(data)


def test_cashiermissing_fields_give_validation_errors():
    """
    test that you only get ValidationErrors if there are fields missing, and
    not e.g. KeyErrors.
    """
    with pytest.raises(ValidationError):
        Cashier().load({})


# Test Warehouse
def test_warehouse_minimally_needed_fields():
    """
    this test is to make sure that the only required fields are the
    ones provided in account provisioning, if this test fails, account
    provisioning will fail
    """
    data = {'tenant_id': '123456', 'name': 'name', 'wh': '45'}
    warehouse = Warehouse().load(data)
    assert warehouse == {
        'tenant_id': ['123456'],
        'name': 'name',
        'wh': '45',
        'active': True,
        'fullname': '',
        'ean': '',
        'addresses': [],
    }


def test_warehouse_missing_fields_give_validation_errors():
    """
    test that you only get ValidationErrors if there are fields missing, and
    not e.g. KeyErrors.
    """
    with pytest.raises(ValidationError):
        Warehouse().load({})


# Account Provisioning tests
def test_data_uniqueness_within_import_warehouses():
    data = {
        'warehouses': [
            {'tenant_id': '91539', 'name': 'Amsterdam', 'wh': '50'},
            {'tenant_id': '91539', 'name': 'Amstelveen', 'wh': '50'},
            {'tenant_id': '91540', 'name': 'Amsterdam', 'wh': '51'},
            {'tenant_id': '91540', 'name': 'Amstelveen', 'wh': '51'},
        ]
    }
    with pytest.raises(ValidationError) as e:
        Data(context={'account_provisioning': True}).load(data)
    assert (
        'There are duplicate wh numbers in the import for tenant_id 91539: '
        "['50']" in e.value.args[0]['warehouses']
    )
    assert (
        'There are duplicate wh numbers in the import for tenant_id 91540: '
        "['51']" in e.value.args[0]['warehouses']
    )


def test_data_uniqueness_within_import_warehouses_no_error():
    """The same 'wh' for different tenants is allowed."""
    data = {
        'warehouses': [
            {'tenant_id': '91539', 'name': 'Amsterdam', 'wh': '50'},
            {'tenant_id': '91530', 'name': 'Amstelveen', 'wh': '50'},
        ]
    }
    assert Data(context={'account_provisioning': True}).load(data)


def test_data_uniqueness_existing_warehouses(database):
    warehouses = [
        {'wh': '50', 'tenant_id': ['91539']},
        {'wh': '51', 'tenant_id': ['91530']},
    ]
    database.warehouses.insert_many(warehouses)
    data = {
        'warehouses': [
            {'tenant_id': '91539', 'name': 'Amsterdam', 'wh': '50'},
            {'tenant_id': '91530', 'name': 'Amstelveen', 'wh': '51'},
        ]
    }
    with pytest.raises(ValidationError) as e:
        Data(context={'db': database, 'account_provisioning': True}).load(data)
    assert (
        e.value.args[0]['warehouses'][0]['wh'][0]
        == 'This wh number already exists for this tenant'
    )
    assert (
        e.value.args[0]['warehouses'][1]['wh'][0]
        == 'This wh number already exists for this tenant'
    )


def test_data_uniqueness_within_import_cashiers():
    data = {
        'cashiers': [
            {'tenant_id': '91539', 'name': '01', 'fullname': 'One', 'password': '50'},
            {'tenant_id': '91539', 'name': '02', 'fullname': 'Two', 'password': '50'},
            {'tenant_id': '91539', 'name': '01', 'fullname': 'One', 'password': '51'},
            {'tenant_id': '91539', 'name': '02', 'fullname': 'Two', 'password': '51'},
            {'tenant_id': '91540', 'name': '01', 'fullname': 'One', 'password': '51'},
            {'tenant_id': '91540', 'name': '02', 'fullname': 'Two', 'password': '51'},
        ]
    }
    with pytest.raises(ValidationError) as e:
        Data(context={'account_provisioning': True}).load(data)
    assert len(e.value.args[0]['cashiers']) == 2
    for message in e.value.args[0]['cashiers']:
        assert 'There are duplicate passwords in the import for' in message


def test_data_uniqueness_within_import_cashiers_no_error():
    """The same 'password' for different tenants is allowed."""
    data = {
        'cashiers': [
            {'tenant_id': '91539', 'name': '01', 'fullname': 'One', 'password': '50'},
            {'tenant_id': '91530', 'name': '02', 'fullname': 'Two', 'password': '50'},
        ]
    }
    assert Data(context={'account_provisioning': True}).load(data)


def test_data_uniqueness_existing_cashiers(database):
    cashiers = [
        {'password_hash': hash_password('50'), 'tenant_id': ['91539']},
        {'password_hash': hash_password('51'), 'tenant_id': ['91530']},
    ]
    database.cashiers.insert_many(cashiers)
    data = {
        'cashiers': [
            {'tenant_id': '91539', 'name': '01', 'fullname': 'One', 'password': '50'},
            {'tenant_id': '91530', 'name': '02', 'fullname': 'Two', 'password': '51'},
        ]
    }
    with pytest.raises(ValidationError) as e:
        Data(context={'db': database, 'account_provisioning': True}).load(data)
    assert (
        e.value.args[0]['cashiers'][0]['_schema'][0]
        == 'This password already exists for this tenant'
    )
    assert (
        e.value.args[0]['cashiers'][1]['_schema'][0]
        == 'This password already exists for this tenant'
    )
