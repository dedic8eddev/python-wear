import json
import os
from copy import deepcopy
from uuid import UUID

import pytest
from bson import ObjectId

from spynl_schemas import RetailCustomerSchema
from spynl_schemas.foxpro_serialize import escape

from spynl.api.auth.testutils import DummyRequest, make_auth_header, mkuser
from spynl.api.hr.exceptions import ExistingCustomer
from spynl.api.hr.resources import RetailCustomers
from spynl.api.hr.retail_customer import add, save

PATH = os.path.dirname(os.path.abspath(__file__))
USERID = ObjectId()
USERNAME = 'user1'
PASSWORD = 'password'
TENANT_ID = '12345'


@pytest.fixture()
def patch_spynl_settings(db, monkeypatch):
    """Prevent spynl from accessing application settings."""

    class Registry:
        settings = {'spynl.mongo.db': db}

    monkeypatch.setattr('pyramid.threadlocal.get_current_registry', lambda: Registry())


@pytest.fixture(scope='module', autouse=True)
def customer():
    """Return the loaded json customer test data."""
    with open(f'{PATH}/data/customer.json') as fob:
        data = fob.read()
    return json.loads(data)


@pytest.fixture(scope='module')
def foxpro_event():
    """Return the loaded json customer test data."""
    with open(f'{PATH}/data/foxpro_event.json') as fob:
        data = fob.read()
    return json.loads(data)


@pytest.fixture
def request_(customer, spynl_data_db):
    """Return a ready pyramid fake request."""
    request = DummyRequest()
    request.db = spynl_data_db
    request.requested_tenant_id = '12345'
    request.session = {'auth.userid': 'test_user_id', 'username': 'test_user_username'}
    request.cached_user = {'_id': ObjectId(), 'username': 'a user'}
    request.headers = {'sid': '123123123123'}
    request.session_or_token_id = '123123123123'
    request.args = {'data': [deepcopy(customer)]}
    return request


@pytest.fixture
def ctx(request_):
    ctx = RetailCustomers(request_)
    return ctx


@pytest.fixture(scope='function')
def setup_db(app, spynl_data_db):
    db = spynl_data_db
    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['pos'], 'settings': {}})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'pos-device'},
    )
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))


def test_customer_document_is_the_expected_one(
    customer, ctx, request_, db, patch_spynl_settings
):
    """Ensure new customer is saved correctly."""
    response = add(ctx, request_)
    db_customer = db.customers.find_one(
        {'_id': UUID(response['data'][0])},
        dict(_id=0, cust_id=0, loyalty_no=0, created=0, modified=0, modified_history=0),
    )
    customer['tenant_id'] = [request_.requested_tenant_id]
    assert db_customer == customer


def test_save_with_updated_data_for_the_customer(
    ctx, request_, db, patch_spynl_settings
):
    """Ensure customer is updated."""
    customer_id = add(ctx, request_)['data'][0]
    original = db.customers.find_one({'_id': UUID(customer_id)})
    # alter all values by adding _ as prefix except 2 values that need to stay the same:
    # the primary field of addresses and contacts as each needs at least one primary
    update_customer = {
        'active': False,
        'addresses': [
            {
                'city': '_Test city',
                'country': '_Test country',
                'houseadd': '_TEST HOUSE ADDRESS',
                'houseno': '_99',
                'primary': True,
                'street': '_Test street name',
                'street2': '_Test street name 2',
                'type': 'billing',
                'zipcode': '1111CE',
            }
        ],
        'agent_id': '_',
        'company': '_test company',
        'contacts': [
            {
                'email': '_mail@mail.com',
                'mobile': '_1234567890',
                'name': '_Test name',
                'phone': '_0123 456 789',
                'primary': True,
                'type': 'private',
            }
        ],
        'currency': '_test currency',
        'first_name': '_first test name',
        'lang': '_english',
        'last_name': '_last test name',
        'middle_name': '_middle test name',
        'newsletter_subscribe': False,
        'properties': [{'name': '_test_name_1', 'value': '_3'}],
        'remarks': '_Test remarks',
        'title': '_Mr. test title',
        'origin': '_',
    }
    # below ensures that this test gets updated with new fields as all "editable" fields
    # should be included in the above dictionary(update_customer)
    unmodifiable = {
        '_id',
        'created',
        'modified',
        'modified_history',
        'tenant_id',
        'cust_id',
        'loyalty_no',
        'points',
        'dob',
    }
    postloaded_keys = [
        'customer_zipcode',
        'customer_city',
        'customer_street',
    ]
    assert set(RetailCustomerSchema().fields.keys() - unmodifiable) == set(
        list(update_customer.keys()) + postloaded_keys
    )

    request_.args['data'][0] = dict(_id=original['_id'], **update_customer)
    save(ctx, request_)

    new_customer = db.customers.find_one(
        {'_id': UUID(customer_id)}, {'modified': 0, 'modified_history': 0}
    )
    for key, new_value in new_customer.items():
        if key in postloaded_keys:
            pass
        elif key in unmodifiable:
            assert new_value == original[key]
        else:
            assert new_value == update_customer[key]
    assert db.events.count_documents({}) == 2


def test_adding_duplicate_user(db, ctx, request_, patch_spynl_settings):
    uuid = add(ctx, request_)['data'][0]
    request_.args['data'][0]['_id'] = uuid
    with pytest.raises(ExistingCustomer) as error:
        add(ctx, request_)
    assert 'id' in error.value.developer_message


@pytest.mark.parametrize('endpoint', [add, save])
def test_changing_cust_id_field_that_is_not_allowed_to_be_changed(
    db, ctx, request_, endpoint, patch_spynl_settings
):
    if endpoint == save:
        add(ctx, request_)
    request_.args['data'][0]['cust_id'] = 'foo'
    endpoint(ctx, request_)
    cust_id = db.customers.find_one()['cust_id']
    assert cust_id != 'foo'
    assert len(cust_id) == 5
    event = db.events.find_one()
    assert 'custnum__' + escape(cust_id) in event['fpquery']


@pytest.mark.parametrize('endpoint', [add, save])
def test_changing_loyalty_no_field_that_is_not_allowed_to_be_changed(
    db, ctx, request_, endpoint, patch_spynl_settings
):
    if endpoint == save:
        add(ctx, request_)
    request_.args['data'][0]['loyalty_no'] = 'foo'
    endpoint(ctx, request_)
    loyalty_no = db.customers.find_one()['loyalty_no']
    assert loyalty_no != 'foo'
    assert len(loyalty_no) == 10
    event = db.events.find_one()
    assert 'loyaltynr__' + escape(loyalty_no) in event['fpquery']


@pytest.mark.parametrize('endpoint', [add, save])
def test_changing_tenant_id_field_that_is_not_allowed_to_be_changed(
    db, ctx, request_, endpoint, patch_spynl_settings
):
    if endpoint == save:
        add(ctx, request_)
    request_.args['data'][0]['tenant_id'] = ['foo']
    endpoint(ctx, request_)
    customer = db.customers.find_one()
    assert customer['tenant_id'] == [request_.requested_tenant_id]


def test_customer_no_foxpro_event(app, setup_db, spynl_data_db, customer):
    payload = {'data': customer, 'doNotGenerateEvent': True}
    app.post_json('/customers/save', payload, status=200)
    assert not spynl_data_db.events.find_one({})


def test_customer_get_with_token(app, spynl_data_db, monkeypatch):
    """test getting into customers get with a token."""

    # monkeypatch so we skip the indexes check.
    monkeypatch.setattr(
        'spynl.api.hr.resources.RetailCustomers.is_large_collection', False
    )
    mkuser(spynl_data_db.pymongo_db, 'user', '00000000', ['1'], custom_id=USERID)
    spynl_data_db.tenants.insert_one({'_id': '1', 'name': 'I. Tenant', 'active': True})
    spynl_data_db.customers.insert_one({'_id': '2', 'tenant_id': '1'})
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    app.get('/customers/get', headers=headers, status=200)


def test_customer_add_with_token(app, spynl_data_db, customer):
    """test adding a customer with a token."""
    spynl_data_db.tenants.insert_one({'_id': '1', 'name': 'I. Tenant', 'active': True})
    mkuser(spynl_data_db.pymongo_db, 'user', '00000000', ['1'], custom_id=USERID)
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    data = {'data': customer}
    app.post_json('/customers/add', data, headers=headers, status=200)


def test_customer_save_with_token(app, spynl_data_db, customer):
    """test saving a customer with a token."""
    spynl_data_db.tenants.insert_one({'_id': '1', 'name': 'I. Tenant', 'active': True})
    mkuser(spynl_data_db.pymongo_db, 'user', '00000000', ['1'], custom_id=USERID)
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    data = {'data': customer}
    app.post_json('/customers/save', data, headers=headers, status=200)
