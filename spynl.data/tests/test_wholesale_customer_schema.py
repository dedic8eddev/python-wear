import copy

import pytest
from marshmallow import ValidationError

from spynl_schemas import SyncWholesaleCustomerSchema, WholesaleCustomerSchema


@pytest.fixture()
def customer():
    return copy.deepcopy(CUSTOMER)


@pytest.mark.parametrize(
    'val,shouldraise', [('', False), ('sdf', True), ('kareem@softwear.nl', False)]
)
def test_email(val, shouldraise):
    s = WholesaleCustomerSchema(only=('tenant_id', 'email'))
    s.context.update(tenant_id='1')
    if shouldraise:
        with pytest.raises(ValidationError, match='email'):
            s.load({'email': val})
    else:
        s.load({'email': val})


def test_event(customer):
    # use sync schema because customer data is available in fp format:
    data = SyncWholesaleCustomerSchema(context={'tenant_id': '1'}).load(customer)
    data = WholesaleCustomerSchema(context={'tenant_id': '1'}).load(data)
    event = WholesaleCustomerSchema.generate_fpqueries(data)[0][1]
    assert event == (
        'setclient/uuid__462dd47f%2D93b9%2D49c4%2D8083%2D47c40f5510fb/'
        'active__true/blocked__false/custnum__1859/lastname__Aads%20feestjes/'
        'legalname__aads%20legal/city__Amsterdam/street__Herikerbergweg%20293/'
        'country__NL/sales__SOFTWEAR/zipcode__1101%20CT/'
        'email__aadje%40softwear.nl/limiet__0/cocnr__1/vatnr__2/banknr__3/'
        'telephone__123/currency__DDK/nettTerm__60.0/discountTerm1__21.0/'
        'discountTerm2__30.0/discountPercentage1__2.0/discountPercentage2__1.0/'
        'preSaleDiscount__0.0/VOKORT__0.0/creditSqueeze__0/cashOnDelivery__false/'
        'moneyOrder__false/deliveryaddress__Herikerbergweg%20292/'
        'deliveryzipcode__1101%20CT/deliverycity__Amsterdam/deliverycountry__NL/'
        'deliverytelephone__020%2D2292929/rayon__DE1/languagecode__nl'
    )


def test_validate_region(database, customer):
    database.tenants.insert_one(
        {'_id': '1', 'settings': {'sales': {'regions': ['DE1']}}}
    )
    customer_2 = {**customer, 'region': 'DE2'}
    with pytest.raises(ValidationError) as e:
        WholesaleCustomerSchema(
            context={'tenant_id': '1', 'db': database}, only=['tenant_id', 'region']
        ).load([customer, customer_2], many=True)

    # assert we get one validationerror, the second customer with the wrong
    # region
    assert len(e.value.messages) == 1 and 1 in e.value.messages


def test_addresses_sync(customer):
    d = SyncWholesaleCustomerSchema(context={'tenant_id': '1'}).load(customer)
    assert isinstance(d['address'], dict) and isinstance(d['deliveryAddress'], dict)
    assert not any(
        [
            k in d
            for k in [
                'houseNumber',
                'houseNumberAddition',
                'zipcode',
                'city',
                'country',
                'telephone',
                'fax',
                'deliveryZipcode',
                'deliveryCity',
                'deliveryCountry',
                'deliveryTelephone',
                'deliveryFax',
            ]
        ]
    )


@pytest.mark.parametrize(
    'val,active',
    [
        ({'tenant_id': '1', 'inactive': False}, True),
        ({'tenant_id': '2', 'inactive': True}, False),
    ],
)
def test_active_sync_schema(val, active):
    s = SyncWholesaleCustomerSchema(only=('active',))
    d = s.load(val)
    assert d['active'] == active


def test_set_agent_id_sync_schema(database, customer):
    agent_id = database.users.insert_one({'email': 'user@email.com'}).inserted_id
    database.tenants.insert_one({'_id': '1', 'regions': ['DE', 'DE1']})
    s = SyncWholesaleCustomerSchema(context={'tenant_id': '1', 'db': database})
    d = s.load(customer)
    assert d['agentId'] == agent_id


def test_drop_invalid_email_sync_schema():
    data = SyncWholesaleCustomerSchema(partial=True).load({'email': 'bla'})
    assert 'email' not in data


def test_employee_in_schema():
    assert 'employee' in WholesaleCustomerSchema().fields


CUSTOMER = {
    'id': '1859',
    'name': 'Aads feestjes',
    'legalName': 'aads legal',
    'inactive': False,
    'type': 'F',
    'blocked': False,
    'agent': 'SOFTWEAR',
    'carrier': '',
    'carrierRemark': '',
    'balance': 0,
    'preSaleDiscount': 0,
    'discountTerm1': 21.0,
    'discountTerm2': 30.0,
    'discountPercentage1': 2.0,
    'discountPercentage2': 1.0,
    'creditSqueeze': 0,
    'shippingCost': 0,
    'nettTerm': 60.0,
    'cashOnDelivery': False,
    'moneyOrder': False,
    'creditLimit': 0,
    'paymentMethod': 1.0,
    'shippingMethod': 0,
    'address': 'Herikerbergweg 293',
    'houseNumber': '',
    'houseNumberAddition': '',
    'zipcode': '1101 CT',
    'city': 'Amsterdam',
    'country': 'NL',
    'telephone': '123',
    'fax': '',
    'deliveryAddress': 'Herikerbergweg 292',
    'deliveryZipcode': '1101 CT',
    'deliveryCity': 'Amsterdam',
    'deliveryCountry': 'NL',
    'deliveryTelephone': '020-2292929',
    'deliveryFax': '',
    'remarks': '',
    'currency': 'DDK',
    'language': 'nl',
    'markup': 0,
    'retailServiceOrganisation': '',
    'headQuarterNumber': '',
    'copyDocumentsToHeadQuarter': False,
    'retailServiceOrganisationMemberNumber': '',
    'vatNumber': '2',
    'clientNumber': '0198785567',
    'chamberOfCommerceNumber': '1',
    'bankAccountNumber2': '',
    'bankAccountNumber': '3',
    'bankName': '',
    'GLN': '',
    'email': 'aadje@softwear.nl',
    'region': 'DE1',
    'uuid': '462dd47f-93b9-49c4-8083-47c40f5510fb',
    'groups': [],
    'tenant_id': '99999',
    'agentEmail': 'user@email.com',
    'employee': False,
}
