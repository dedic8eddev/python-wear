import uuid

import pytest
from marshmallow import ValidationError

from spynl_schemas import RetailCustomerSchema, SyncRetailCustomerSchema
from spynl_schemas.foxpro_serialize import escape


def make_address(primary):
    return {
        'city': '',
        'country': '',
        'zipcode': '',
        'street': '',
        'houseno': '',
        'primary': primary,
    }


def make_contact(primary):
    return {'type': 'other', 'primary': primary}


@pytest.mark.parametrize(
    'dob,key, schema',
    [
        ('sdfsdf', 'dob', RetailCustomerSchema),
        ('sdfsdf', 'birthDate', SyncRetailCustomerSchema),
        ('', 'dob', RetailCustomerSchema),
        ('', 'birthDate', SyncRetailCustomerSchema),
        ('      ', 'dob', RetailCustomerSchema),
        ('      ', 'birthDate', SyncRetailCustomerSchema),
        ('2018121221', 'dob', RetailCustomerSchema),
        ('2018121221', 'birthDate', SyncRetailCustomerSchema),
    ],
)
def test_dob_invalid(dob, key, schema):
    """Should not raise but set empty string"""
    schema = schema(only=('dob',))
    data = schema.load({key: dob})
    assert data['dob'] == ''


@pytest.mark.parametrize(
    'dob,key, schema',
    [
        ('20181212', 'dob', RetailCustomerSchema),
        ('20181212', 'birthDate', SyncRetailCustomerSchema),
        ('2018-12-12', 'dob', RetailCustomerSchema),
        ('2018-12-12', 'birthDate', SyncRetailCustomerSchema),
        ('  2018-12-12   ', 'dob', RetailCustomerSchema),
        ('  2018-12-12   ', 'birthDate', SyncRetailCustomerSchema),
    ],
)
def test_dob_valid(dob, key, schema):
    schema = schema(only=('dob',))
    data = schema.load({key: dob})
    assert data['dob'] == '2018-12-12'


def test_validate_single_primary_address():
    schema = RetailCustomerSchema(only=('addresses',))
    with pytest.raises(ValidationError):
        schema.load({'addresses': [make_address(True), make_address(True)]})


def test_validate_single_primary_address_no_primaries():
    schema = RetailCustomerSchema(only=('addresses',))
    with pytest.raises(ValidationError):
        schema.load({'addresses': [make_address(False), make_address(False)]})


def test_validate_single_primary_address_one_primary():
    schema = RetailCustomerSchema(only=('addresses',))
    try:
        schema.load({'addresses': [make_address(True), make_address(False)]})
    except ValidationError as e:
        pytest.fail(str(e.normalized_messages()))


def test_validate_single_primary_contact():
    schema = RetailCustomerSchema(only=('contacts',))
    with pytest.raises(ValidationError):
        schema.load({'contacts': [make_contact(True), make_contact(True)]})


def test_validate_single_primary_contact_no_primaries():
    schema = RetailCustomerSchema(only=('contacts',))
    with pytest.raises(ValidationError):
        schema.load({'contacts': [make_contact(False), make_contact(False)]})


def test_validate_single_primary_contact_one_primary():
    schema = RetailCustomerSchema(only=('contacts',))
    try:
        schema.load({'contacts': [make_contact(True), make_contact(False)]})
    except ValidationError as e:
        pytest.fail(str(e.normalized_messages()))


def test_dob_loading():
    schema = RetailCustomerSchema(only=('dob',))
    data = schema.load({'dob': '22-12-2017'})
    assert data['dob'] == '2017-12-22'


def test_event():
    id = str(uuid.uuid4())
    customer = {
        '_id': id,
        'cust_id': '1',
        'loyalty_no': '1',
        'points': 0,
        'currency': '',
        'dob': '13-1-1989',
        'addresses': [
            {
                'country': 'Nederland',
                'houseadd': 'b',
                'primary': True,
                'street': 'Zomerweg 52',
                'street2': '',
                'type': 'billing',
                'houseno': '13',
                'zipcode': '9251mh',
                'city': 'Burgum',
            }
        ],
        'first_name': 'S.',
        'remarks': '',
        'lang': 'nl',
        'contacts': [
            {
                'primary': True,
                'email': 'sytskehoekstra@icloud.com',
                'phone': '0511463014',
                'type': 'private',
                'mobile': '',
                'name': 'Dhr. S. Bouius',
            }
        ],
        'last_name': 'Bouius',
        'tenant_id': ['91078'],
        'title': 'Mr',
        'properties': [{'value': 'val', 'name': 'nm'}],
        'newsletter_subscribe': False,
        'middle_name': '',
        'active': True,
        'company': '',
    }
    data = RetailCustomerSchema().load(customer)
    event = RetailCustomerSchema.generate_fpqueries(data)

    assert event == [
        (
            'setclient',
            (
                'setclient/uuid__{id}/custnum__1/loyaltynr__1/newsletter__false/'
                'title__Mr/firstname__S./middlename__/lastname__Bouius/warehouse__/'
                'remarks__/born__13-01-1989/email__sytskehoekstra%40icloud.com/fax__/'
                'telephone__0511463014/street__Zomerweg%2052/housenum__13/houseadd__B/'
                'zipcode__9251MH/city__Burgum/country__Nederland/zgrpnm__val'
            ).format(id=escape(id)),
        )
    ]


def test_event_without_properties():
    id = str(uuid.uuid4())
    customer = {
        '_id': id,
        'cust_id': '1',
        'loyalty_no': '1',
        'points': 0,
        'currency': '',
        'dob': '13-1-1989',
        'addresses': [
            {
                'country': 'Nederland',
                'houseadd': 'B',
                'primary': True,
                'street': 'Zomerweg 52',
                'street2': '',
                'type': 'billing',
                'houseno': '13',
                'zipcode': '9251MH',
                'city': 'Burgum',
            }
        ],
        'first_name': 'S.',
        'remarks': '',
        'lang': 'nl',
        'contacts': [
            {
                'primary': True,
                'email': 'sytskehoekstra@icloud.com',
                'phone': '0511463014',
                'type': 'private',
                'mobile': '',
                'name': 'Dhr. S. Bouius',
            }
        ],
        'last_name': 'Bouius',
        'tenant_id': ['91078'],
        'title': 'Mr',
        'newsletter_subscribe': False,
        'middle_name': '',
        'active': True,
        'company': '',
    }
    data = RetailCustomerSchema().load(customer)
    event = RetailCustomerSchema.generate_fpqueries(data)

    assert event == [
        (
            'setclient',
            (
                'setclient/uuid__{id}/custnum__1/loyaltynr__1/newsletter__false/'
                'title__Mr/firstname__S./middlename__/lastname__Bouius/warehouse__/'
                'remarks__/born__13-01-1989/email__sytskehoekstra%40icloud.com/fax__/'
                'telephone__0511463014/street__Zomerweg%2052/housenum__13/houseadd__B/'
                'zipcode__9251MH/city__Burgum/country__Nederland'
            ).format(id=escape(id)),
        )
    ]


def test_sync_schema():
    customer = {
        "id": " 7979",
        "name": "Winia",
        "legalName": "",
        "inactive": False,
        "type": "F",
        "blocked": True,
        "agent": "WEBSHOP",
        "carrier": "",
        "carrierRemark": "",
        "balance": 902.0,
        "preSaleDiscount": 0,
        "discountTerm1": 0,
        "discountTerm2": 0,
        "discountPercentage1": 0,
        "discountPercentage2": 0,
        "creditSqueeze": 0,
        "shippingCost": 0,
        "nettTerm": 0,
        "cashOnDelivery": False,
        "moneyOrder": False,
        "creditLimit": 879.0,
        "paymentMethod": 0,
        "shippingMethod": 0,
        "address": "Noordermeer 11",
        "houseNumber": "",
        "houseNumberAddition": "",
        "zipcode": "9251LS",
        "city": "BURGUM",
        "country": "NL",
        "telephone": "0511-48 28 84",
        "fax": "06-20750353",
        "title": "Mevr.",
        "firstName": "E.J.",
        "middleName": "",
        "birthDate": "19630402",
        "remarks": "",
        "currency": "",
        "language": "",
        "markup": 0,
        "retailServiceOrganisation": "",
        "headQuarterNumber": "",
        "copyDocumentsToHeadQuarter": False,
        "retailServiceOrganisationMemberNumber": "",
        "vatNumber": "",
        "clientNumber": "0000007347",
        "chamberOfCommerceNumber": "",
        "bankAccountNumber2": "",
        "bankAccountNumber": "",
        "bankName": "",
        "GLN": "",
        "email": "elskewinia@gmail.com",
        "region": "",
        "uuid": "f4dabbb2-778b-4fac-99ad-3b6fefed155e",
        "lastUpdate": "20180625162037",
        "groups": [{"name": "Mailing", "value": "Nee"}],
    }
    data = SyncRetailCustomerSchema(context={'tenant_id': '123213'}).load(customer)
    assert data['addresses'] == [
        {
            'type': 'billing',
            'primary': True,
            'zipcode': customer['zipcode'],
            'street': customer['address'],
            'houseadd': customer['houseNumberAddition'],
            'houseno': customer['houseNumber'],
            'city': customer['city'],
            'country': customer['country'],
        }
    ]
    assert data['contacts'] == [
        {
            'type': '',
            'primary': True,
            'name': customer['name'],
            'email': customer['email'],
            'phone': customer['telephone'],
            'mobile': customer['fax'],
        }
    ]
    assert not data['active']


def test_drop_invalid_email_sync_schema():
    data = SyncRetailCustomerSchema(context={'tenant_id': '123213'}, partial=True).load(
        {'email': 'bla'}
    )
    assert 'email' not in data['contacts'][0]
