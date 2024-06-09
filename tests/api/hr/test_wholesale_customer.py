import copy
import uuid

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

CUSTOMER_ID = '1b23fb66-c87a-4a10-8ccf-b59ea493947a'
CUSTOMER_NAME = 'foo_name'
CUSTOMER_LEGALNAME = 'foo_legalname'
TENANT_ID = '12345'


def sample_customer():
    customer = {
        '_id': str(CUSTOMER_ID),
        'region': 'DE1',
        'active': True,
        'address': {
            'address': 'a',
            'city': 'a',
            'country': 'a',
            'telephone': 'a',
            'zipcode': 'a',
        },
        'clientNumber': '',
        'currency': 'USD',
        'cust_id': '-XxEm',
        'deliveryAddress': {
            'address': 'a',
            'city': 'a',
            'country': 'Åland',
            'telephone': 'a',
            'zipcode': 'a',
        },
        'discountPercentage1': 0.0,
        'discountPercentage2': 0.0,
        'discountTerm1': 0.0,
        'discountTerm2': 0.0,
        'email': 'email@email.com',
        'legalName': 'a',
        'name': 'a',
        'nettTerm': 0.0,
        'remarks': 'e',
        'tenant_id': [TENANT_ID],
        'vatNumber': '',
    }

    return copy.deepcopy(customer)


USERNAME = 'user1'
USERNAME_2 = 'user2'
USERNAME_3 = 'user3'
USERNAME_ADMIN = 'admin'
PASSWORD = '0' * 10
USER_ID = ObjectId()
USER_ID_3 = ObjectId()
TENANT_ID = '1'
TENANT_ID_2 = '2'


@pytest.fixture(autouse=True, scope='function')
def setup(app, spynl_data_db):
    db = spynl_data_db
    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['sales'], 'settings': {}})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-user'},
        custom_id=USER_ID,
        settings={'sales': {'region': 'DE'}},
    )
    mkuser(
        db.pymongo_db,
        USERNAME_2,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-user'},
        settings={'sales': {'region': 'DE2'}},
    )
    mkuser(
        db.pymongo_db,
        USERNAME_3,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-user'},
        custom_id=USER_ID_3,
    )
    mkuser(
        db.pymongo_db,
        USERNAME_ADMIN,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-admin'},
    )
    # app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    yield
    db.wholesale_customers.delete_many({})


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_save_customer(app, login):
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'agentId': str(USER_ID)}},
        status=200,
    )


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_save_customer_unauthorized(app, login):
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'agentId': str(ObjectId())}},
        status=403,
    )


@pytest.mark.parametrize('login', [(USERNAME_ADMIN, PASSWORD)], indirect=True)
def test_save_customer_as_admin(app, login):
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'agentId': str(ObjectId())}},
        status=200,
    )


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_cust_id(spynl_data_db, app, login):
    result = app.post_json('/wholesale-customers/save', {'data': {}})

    try:
        spynl_data_db.wholesale_customers.find_one(
            {'_id': uuid.UUID(result.json['data'][0])}
        )['cust_id']
    except KeyError:
        pytest.fail('cust_id not set')


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_saving_existing_customer(app, spynl_data_db, login):
    _id = uuid.uuid4()
    app.post_json(
        '/wholesale-customers/save', {'data': {'cust_id': '1', '_id': str(_id)}}
    )
    app.post_json(
        '/wholesale-customers/save', {'data': {'cust_id': '2', '_id': str(_id)}}
    )

    customers = list(spynl_data_db.wholesale_customers.find())
    assert len(customers) == 1 and customers[0]['cust_id'] == '2'


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_foxpro_query_is_saved(app, spynl_data_db, login):
    app.post_json('/wholesale-customers/save', {'data': sample_customer()})
    assert spynl_data_db.events.count_documents({}) == 1


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_foxpro_query_is_not_saved(app, spynl_data_db, login):
    payload = {'data': sample_customer(), 'doNotGenerateEvent': True}
    app.post_json('/wholesale-customers/save', payload, status=200)
    assert spynl_data_db.events.count_documents({}) == 0


@pytest.mark.parametrize(
    "field,value,count_",
    [
        ('_id', str(CUSTOMER_ID), 1),
        ('name', CUSTOMER_NAME, 1),
        ('legalName', CUSTOMER_LEGALNAME, 1),
    ],
)
@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_get_wholesale_customer(login, app, field, value, count_):
    app.post_json(
        '/wholesale-customers/save', {'data': {**sample_customer(), field: value}}
    )
    response = app.post_json('/wholesale-customers/get', {'filter': {field: value}})
    assert (
        len(response.json['data']) == count_
        and response.json['data'][0][field] == value
    )


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_get_wholesale_customer_regex_name(login, app):
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'name': 'Customer_1', '_id': str(uuid.uuid4())}},
    )
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'name': 'Customer_2'}},
    )
    response = app.post_json('/wholesale-customers/get', {'filter': {'name': 'cust'}})
    assert len(response.json['data']) == 2


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_get_wholesale_customer_regex_name_control_character(login, app):
    # accidental control characters should not give a 500
    app.post_json(
        '/wholesale-customers/get', {'filter': {'name': '+Custom*er_2[]'}}, status=200
    )


@pytest.mark.parametrize(
    'login,success',
    [((USERNAME, PASSWORD), True), ((USERNAME_2, PASSWORD), False)],
    indirect=['login'],
)
def test_get_wholesale_customer_region(login, success, app):
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'name': 'Customer_1', '_id': str(uuid.uuid4())}},
    )
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'name': 'Customer_2'}},
    )
    response = app.post_json('/wholesale-customers/get', {'filter': {'name': 'cust'}})
    if success:
        assert len(response.json['data']) == 2
    else:
        assert not response.json['data']


@pytest.mark.parametrize(
    "field,value,count_",
    [
        ('_id', str(CUSTOMER_ID), 1),
        ('name', CUSTOMER_NAME, 1),
        ('legalName', CUSTOMER_LEGALNAME, 1),
    ],
)
@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_count_wholesale_customer(login, app, field, value, count_):
    app.post_json(
        '/wholesale-customers/save', {'data': {**sample_customer(), field: value}}
    )
    response = app.post_json('/wholesale-customers/count', {'filter': {field: value}})
    assert response.json['count'] == count_


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_count_wholesale_customer_regex_name(login, app):
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'name': 'Customer_1', '_id': str(uuid.uuid4())}},
    )
    app.post_json(
        '/wholesale-customers/save',
        {'data': {**sample_customer(), 'name': 'Customer_2'}},
    )
    response = app.post_json('/wholesale-customers/count', {'filter': {'name': 'cust'}})
    assert response.json['count'] == 2


@pytest.mark.parametrize('login', [(USERNAME_3, PASSWORD)], indirect=True)
def test_auto_filter_by_agent(spynl_data_db, login, app):
    spynl_data_db.wholesale_customers.insert_many(
        [
            {**sample_customer(), '_id': uuid.uuid4(), 'agentId': ObjectId()}
            for _ in range(10)
        ]
    )
    spynl_data_db.wholesale_customers.insert_one(
        {**sample_customer(), 'agentId': USER_ID_3}
    )
    response = app.get('/wholesale-customers/count')
    assert response.json['count'] == 1


@pytest.mark.parametrize('login', [(USERNAME_ADMIN, PASSWORD)], indirect=True)
def test_auto_filter_by_agent_as_admin(spynl_data_db, login, app):
    spynl_data_db.wholesale_customers.insert_many(
        [
            {**sample_customer(), '_id': uuid.uuid4(), 'agentId': ObjectId()}
            for _ in range(10)
        ]
    )
    spynl_data_db.wholesale_customers.insert_one(
        {**sample_customer(), 'agentId': USER_ID}
    )
    response = app.get('/wholesale-customers/count')
    assert response.json['count'] == 11


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_save_count_wholesale_customer(login, app):
    app.post_json(
        '/wholesale-customer/save',
        {'data': {**sample_customer(), 'name': 'Customer_1', '_id': str(uuid.uuid4())}},
    )
    app.post_json(
        '/wholesale-customer/save',
        {'data': {**sample_customer(), 'name': 'Customer_2'}},
    )
    response_1 = app.get('/wholesale-customer/count')
    response_2 = app.get('/wholesale-customers/count')
    assert response_1.json['count'] == response_2.json['count']
