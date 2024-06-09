# -*- coding: utf-8 -*-
"""Tests for settings."""

from datetime import datetime
from uuid import uuid4

import pytest
import pytz
from bson import ObjectId
from marshmallow import fields

from spynl_schemas.shared_schemas import BaseSettingsSchema

from spynl.api import hr
from spynl.api.auth.testutils import mkuser

UID1 = ObjectId()
UID2 = ObjectId()
UID_SALES = ObjectId()
UID_OWNER = ObjectId()
CURRENCY_ID = uuid4()

USER_EXPECTED_SETTINGS = {
    'email': {
        'active': False,
        'autoPopup': False,
        'body': 'Uw kassabon',
        'replyTo': '',
        'sender': 'info@uwkassabon.com',
        'subject': 'Uw kassabon',
    },
    'noAutoPrint': False,
    'displayAndPrintDiscountReason': False,
    'dashboardAllowedLocations': [],
    'paymentMethods': {
        'cash': {'allowNegative': True, 'available': True, 'requireCustomer': False},
        'consignment': {'available': True},
        'creditCard': {
            'allowNegative': True,
            'available': True,
            'requireCustomer': False,
        },
        'creditReceipt': {'available': True, 'requireCustomer': False},
        'pin': {
            'allowNegative': True,
            'available': True,
            'coupled': False,
            'requireCustomer': False,
        },
        'storeCredit': {'available': True, 'requireCustomer': False},
        'withdrawal': {'available': True},
    },
    'pinId': '',
    'pinProvider': 'none',
    'printer': 'browser',
    'printerId': '',
    'payNLToken': '******789',
    'sales': {
        'barcodeScanning': 'select',
        'newCustomerAllowed': True,
        'showStock': False,
    },
    'picking': {'pickingListPrinterId': '', 'shippingLabelPrinterId': ''},
    'fiscalPrinter': {
        'active': False,
        'hostName': '',
        'printerType': 'Italy',
        'printerId': '',
    },
    'secondScreen': {
        'duration': 10,
        'playlistId': '',
        'secondScreenId': '',
        'showCustomer': False,
    },
}
TENANT1_EXPECTED_SETTINGS = {
    "fetchBarcodeFromLatestCollection": False,
    'allowSalesOrderEditing': False,
    'closingProcedure': 'eos',
    'currencies': [
        {
            'label': '2.8 Euro',
            'uuid': str(CURRENCY_ID),
        }
    ],
    'currency': 'euro',
    'customLabels': {},
    'logistics': {'allowModifyPriceReceivings': False},
    'logoUrl': {},
    'loyalty': {
        'calculatePointsPerReceipt': True,
        'campaigns': [],
        'cashback': {
            'giveCashbackOnDiscounts': True,
            'text': '',
            'validity': 0,
        },
        'customerCashback': 0.0,
        'pointFactor': 1,
        'pointValue': 1.0,
        'suppressPointsOnDiscount': False,
    },
    'payNLToken': '******789',
    'piking': {},
    'printLogoOnReceipt': False,
    'roundTotalAmount5cent': True,
    'sales': {
        'allowAgentModifyFixDate': False,
        'allowAgentModifyReservationDate': False,
        'confirmationEmail': [],
        'filterByProperties': [],
        'hiddenFields': {
            'address': False,
            'bankNumber': False,
            'city': False,
            'cocNumber': False,
            'country': False,
            'currency': False,
            'deliveryAddress': False,
            'deliveryCity': False,
            'deliveryCountry': False,
            'deliveryTelephone': False,
            'deliveryZipcode': False,
            'discountPercentage1': False,
            'discountPercentage2': False,
            'discountTerm1': False,
            'discountTerm2': False,
            'email': False,
            'language': False,
            'legalName': False,
            'limit': False,
            'name': False,
            'nettTerm': False,
            'preSaleDiscount': False,
            'region': False,
            'remarks': False,
            'telephone': False,
            'vatNumber': False,
            'zipcode': False,
        },
        'directDeliveryPackingList': True,
        'imageRoot': '',
        'orderTemplate': {
            'agentName': True,
            'articleGroup': True,
            'brand': True,
            'collection': True,
            'colorDescription': True,
            'discountLine1': True,
            'discountLine2': True,
            'fixDate': True,
            'nettTerm': True,
            'productPhoto': True,
            'propertiesOnOrder': [],
            'remarks': True,
            'reservationDate': True,
            'shippingCarrier': True,
            'suggestedRetailPrice': True,
        },
        'paymentTermsViewOnly': False,
        'readOnlyFields': {
            'address': False,
            'bankNumber': False,
            'city': False,
            'cocNumber': False,
            'country': False,
            'currency': False,
            'deliveryAddress': False,
            'deliveryCity': False,
            'deliveryCountry': False,
            'deliveryTelephone': False,
            'deliveryZipcode': False,
            'discountPercentage1': False,
            'discountPercentage2': False,
            'discountTerm1': False,
            'discountTerm2': False,
            'email': False,
            'language': False,
            'legalName': False,
            'limit': False,
            'name': False,
            'nettTerm': False,
            'preSaleDiscount': False,
            'region': False,
            'remarks': False,
            'telephone': False,
            'vatNumber': False,
            'zipcode': False,
        },
        'regions': [],
    },
    'shippingCarriers': [],
    'useNewPaymentRules': False,
    'vat': {'highvalue': 21.0, 'lowvalue': 9.0, 'zerovalue': 0.0},
}


@pytest.fixture(scope='function', autouse=True)
def set_db(db):
    """Add 2 tenants and 2 users before every test runs."""
    db.tenants.insert_one({'_id': 'master', 'name': 'Master Tenant'})

    # admin_only is used in one test by adding it with a monkeypatch,
    # and in another test as a setting that is not in the whitelist
    db.tenants.insert_one(
        {
            '_id': 'tenant1',
            'name': 'Tenant Eins',
            'applications': ['pos', 'account', 'sales'],
            'settings': {
                'loyalty': {'cashback': {'giveCashbackOnDiscounts': True}},
                'currency': 'euro',
                'not_in_schema': 'will not appear',
                'payNLToken': '123456789',
                'currencies': [{'uuid': CURRENCY_ID, 'label': '2.8 Euro'}],
            },
            'owners': [UID_OWNER],
        }
    )

    db.tenants.insert_one(
        {
            '_id': 'tenant2',
            'name': 'Tenant Zwei',
            'applications': ['pos', 'account'],
            'settings': {'currency': 'dollar'},
        }
    )

    mkuser(
        db,
        'blahuser',
        'blah',
        ['tenant1', 'tenant2'],
        custom_id=UID1,
        tenant_roles={'tenant1': ['account-admin'], 'tenant2': ['account-admin']},
        settings={
            'payNLToken': '123456789',
        },
    )

    mkuser(
        db,
        'accountmanager',
        'blah',
        ['master'],
        tenant_roles={'master': ['sw-account_manager']},
    )

    mkuser(
        db,
        'blahuser2',
        'blah',
        ['tenant2'],
        custom_id=UID2,
        tenant_roles={'tenant2': ['account-admin']},
        settings={'user2_setting': True},
    )

    mkuser(
        db,
        'blahuser3',
        'blah',
        ['tenant2'],
        tenant_roles={'tenant2': ['pos-device']},
        settings={'user3_setting': 42},
    )

    mkuser(
        db,
        'blahuser4',
        'blah',
        ['tenant2'],
        tenant_roles={'tenant2': ['pos-user']},
        settings={'user4_setting': 42},
    )

    mkuser(
        db,
        'blahuser5',
        'blah',
        ['tenant2'],
        tenant_roles={'tenant2': []},
        settings={'user5_setting': 42},
    )

    mkuser(
        db,
        'sales_user',
        'blah',
        ['tenant1'],
        custom_id=UID_SALES,
        tenant_roles={'tenant1': ['sales-user']},
        settings={'user5_setting': 42},
    )

    mkuser(db, 'masteruser', 'blah', ['master'], tenant_roles={'master': ['sw-admin']})

    mkuser(db, 'owner_user', 'blah', ['tenant1'], custom_id=UID_OWNER)

    mkuser(
        db,
        'delete-settings-user',
        'password',
        ['tenant1'],
        tenant_roles={'tenant1': ['sales-user']},
        settings={'printer': 'browser', 'sales': {'showStock': True}},
    )


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_get_settings(app, login):
    """Check /settings/get"""
    # blahuser has no settings
    expected_data = {
        'user': {
            'id': str(UID1),
            'settings': USER_EXPECTED_SETTINGS,
            'username': 'blahuser',
        },
        'tenant': {
            'id': 'tenant1',
            'settings': TENANT1_EXPECTED_SETTINGS,
        },
    }

    response = app.get('/settings/get')
    import json

    print('response.json', json.dumps(response.json['data']))
    print('expected_data', json.dumps(expected_data))
    assert response.json['data'] == expected_data


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_get_settings_user(app, login):
    """Check /settings/get"""
    # blahuser has no settings, so gets only the defaults
    response = app.get('/settings/get-user')
    assert response.json['data'] == USER_EXPECTED_SETTINGS


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_get_settings_for_the_tenant_that_has_been_set_upon_login(app, login):
    """each user can only read those tenant's settings which they should"""
    response = app.get('/settings/get-tenant', status=200)

    assert response.json['data'] == TENANT1_EXPECTED_SETTINGS


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_get_settings_for_tenant_that_hasnt_been_set_upon_login(app, login):
    """each user can only read those tenant's settings which they should"""
    app.get('/tenants/tenant2/settings/get-tenant', status=403)


@pytest.mark.parametrize('login', [('masteruser', 'blah')], indirect=True)
def test_master_tenant_can_get_other_tenant_settings(app, login):
    """each user can only read those tenant's settings which they should"""
    # master user can see every tenant's settings
    response = app.get('/tenants/tenant1/settings/get-tenant', status=200)
    assert response.json['data'] == TENANT1_EXPECTED_SETTINGS
    response = app.get('/tenants/tenant2/settings/get-tenant', status=200)
    assert response.json['data']['currency'] == 'dollar'


@pytest.mark.parametrize('login', [('blahuser2', 'blah')], indirect=True)
def test_set_user_settings_doesnt_overwrite_all_settings(app, db, login, monkeypatch):
    """Make sure passed settings were updated and not all settings."""

    class MonkeySettings(BaseSettingsSchema):
        new_setting = fields.String()

    monkeypatch.setattr(hr.settings, 'UserSettings', MonkeySettings)
    settings_before = db.users.find_one({'_id': UID2})['settings']
    payload = {'settings': {'new_setting': 'new_setting_value'}}
    app.post_json('/settings/set-user', payload, status=200)

    settings_after = settings_before.copy()
    settings_after.update(payload['settings'])
    saved_settings = db.users.find_one({'_id': UID2})['settings']
    assert saved_settings == settings_after


@pytest.mark.parametrize('login', [('masteruser', 'blah')], indirect=True)
def test_set_tenant_settings_doesnt_overwrite_all_settings(db, app, login):
    """Make sure passed settings were updated and not all settings."""
    # The nested structure here made sure we found a marshmallow bug (partial
    # was not passed to nested structures, so pointValue was overwritten by the
    # missing value)
    db.tenants.update_one({'_id': 'tenant2'}, {'$set': {'loyalty.pointValue': 2}})
    settings_before = db.tenants.find_one({'_id': 'tenant2'})['settings']
    payload = {
        'settings': {
            'shippingCarriers': ['new_setting_value'],
            'loyalty': {'pointFactor': 2},
        }
    }
    app.post_json('/tenants/tenant2/settings/set-tenant', payload, status=200)

    settings_after = settings_before.copy()
    settings_after.update(payload['settings'])
    saved_settings = db.tenants.find_one({'_id': 'tenant2'})['settings']
    assert saved_settings == settings_after


@pytest.mark.parametrize('login', [('blahuser3', 'blah')], indirect=True)
def test_set_user_settings_unauthorized(app, login):
    """Unauthorized access to user settings"""
    # user3 roles are not included in the allowed ones for
    # Settings.set_user_settings
    response = app.get('/settings/set-user', expect_errors=True)
    assert "Permission to 'edit' Settings was denied" in response.json['message']


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(tenant_id='tenant1'))], indirect=True
)
def test_set_settings_for_user_that_doesnt_belong_to_tenant(app, login):
    """blahuser cannot work on blahuser2 when on tenant1."""
    payload = {'username': 'blahuser2', 'settings': dict(user2_setting=True, bla=1)}
    response = app.post_json('/settings/set-user', payload, expect_errors=True)
    assert (
        response.json['message']
        == 'This user does not belong to the requested tenant (tenant1).'
    )


@pytest.mark.parametrize(
    'login', [('blahuser', 'blah', dict(tenant_id='tenant2'))], indirect=True
)
def test_set_settings_for_user_that_belongs_to_tenant(app, monkeypatch, login):
    """blahuser can work on blahuser2 when on tenant2."""

    class MonkeySettings(BaseSettingsSchema):
        user2_setting = fields.String()
        bla = fields.Integer()

    monkeypatch.setattr(hr.settings, 'UserSettings', MonkeySettings)
    payload = {'username': 'blahuser2', 'settings': dict(user2_setting='bla', bla=1)}
    response = app.post_json('/settings/set-user', payload, status=200)
    assert response.json['data'] == {'user2_setting': 'bla', 'bla': 1}


# test normal user tries to change other user


@pytest.mark.parametrize('login', [('blahuser2', 'blah')], indirect=True)
def test_set_tenant_settings(app, db, monkeypatch, login):
    """Check if user can set the tenant settings he should be setting"""
    payload = {'settings': {'shippingCarriers': ['test']}}
    response = app.post_json('/settings/set-tenant', payload, status=200)
    assert 'Account settings have been updated' in response.json['message']
    assert response.json['data'] == {'shippingCarriers': ['test']}
    response = app.get('/settings/get-tenant')
    assert response.json['data']['shippingCarriers'] == ['test']


@pytest.mark.parametrize('login', [('masteruser', 'blah')], indirect=True)
def test_set_tenant_settings_while_being_logged_in_as_master_tenant(app, login):
    payload = {'settings': {'shippingCarriers': ['test']}}

    app.post_json('/tenants/tenant1/settings/set-tenant', payload, status=200)
    response = app.get('/tenants/tenant1/settings/get-tenant')
    assert response.json['data']['shippingCarriers'] == ['test']


@pytest.mark.parametrize(
    'login', [('masteruser', 'blah', dict(tenant_id='master'))], indirect=True
)
@pytest.mark.parametrize(
    'path,payload,error',
    [
        ('set-user', {}, ('type', 'MissingParameter')),
        ('set-tenant', {}, ('type', 'MissingParameter')),
        (
            'set-tenant',
            {'settings': {'loyalty.pointValue': 'v'}},
            ('type', 'ValidationError'),
        ),
        (
            'set-tenant',
            {
                'settings': {
                    'loyalty.campaigns': [
                        {
                            'facctor': 1.4,
                            'startDate': '2016-12-12',
                            'endDate': '2016-12-14',
                        }
                    ]
                }
            },
            ('type', 'ValidationError'),
        ),
        (
            'set-tenant',
            {
                'settings': {
                    'loyalty.campaigns': [
                        {
                            'factor': 1.4,
                            'startDate': '2016-12-16',
                            'endDate': '2016-12-14',
                        }
                    ]
                }
            },
            (
                'message',
                'End date cannot be before start date. The end date cannot be before '
                'the start date.',
            ),
        ),
        (
            'set-tenant',
            {
                'settings': {
                    'loyalty.campaigns': [
                        {
                            'factor': 1.4,
                            'startDate': '2016-12-1',
                            'endDate': '2016-12-14',
                        },
                        {
                            'factor': 1.5,
                            'startDate': '2016-12-12',
                            'endDate': '2016-12-16',
                        },
                    ]
                }
            },
            ('message', 'Campaigns may not overlap'),
        ),
    ],
)
def test_set_settings_endpoints_with_bad_parameters(app, path, payload, error, login):
    """Ensure exceptions are raised."""
    response = app.post_json(
        '/tenants/tenant1/settings/' + path, payload, expect_errors=True
    )
    assert error[1] in response.json[error[0]]


campaigns = [
    {'startDate': '%s-12-12' % 2016, 'endDate': '%s-12-14' % 2016, 'factor': 1.2},
    {'startDate': '%s-01-01' % 2017, 'endDate': '%s-12-31' % 2017, 'factor': 3},
]


@pytest.mark.parametrize(
    'login', [('masteruser', 'blah', dict(tenant_id='master'))], indirect=True
)
@pytest.mark.parametrize(
    'path,payload,db_match,fpquery_match',
    [
        (
            'set-tenant',
            {'loyalty.pointFactor': 1.2},
            {'loyalty.pointFactor': 1.2},
            None,
        ),
        (
            'set-tenant',
            {'loyalty.pointValue': 9.95},
            {'loyalty.pointValue': 9.95},
            'value__995',
        ),
        (
            'set-tenant',
            {
                'loyalty.campaigns': [
                    {'startDate': '2016-12-12', 'endDate': '2016-12-14', 'factor': 1.2}
                ]
            },
            {
                'loyalty.campaigns': [
                    {'startDate': '2016-12-12', 'endDate': '2016-12-14', 'factor': 1.2}
                ]
            },
            'startdate__20161212/enddate__20161214/factor__120',
        ),
        (
            'set-tenant',
            {'loyalty.campaigns': campaigns},
            {
                'loyalty.campaigns': [
                    {'startDate': '2016-12-12', 'endDate': '2016-12-14', 'factor': 1.2},
                    {'startDate': '2017-01-01', 'endDate': '2017-12-31', 'factor': 3},
                ]
            },
            (
                'startdate__20161212/enddate__20161214/factor__120/'
                'startdate__20170101/enddate__20171231/factor__300'
            ),
        ),
    ],
)
def test_getset_settings_with_custom_functions(
    app, db, path, payload, login, db_match, fpquery_match
):
    """Ensure that dynamic getters and setters work."""
    app.post_json('/tenants/tenant1/settings/' + path, {'settings': payload})
    tenant = db.tenants.find_one(
        {'_id': 'tenant1'}, {'settings.' + key: 1 for key in payload.keys()}
    )
    for path, value in db_match.items():
        tsetting = tenant['settings']
        for step in path.split('.'):
            tsetting = tsetting[step]
        assert tsetting == value
    if fpquery_match:
        new_event = db.events.find_one()
        assert fpquery_match in new_event['fpquery']


NOW = datetime.now(pytz.utc)
campaigns = [
    {
        'startDate': '%s-12-12' % str(NOW.year - 1),
        'endDate': '%s-12-14' % str(NOW.year - 1),
        'factor': 1.2,
    },
    {'startDate': '%s-01-01' % NOW.year, 'endDate': '%s-12-31' % NOW.year, 'factor': 3},
]


@pytest.mark.parametrize(
    'login', [('masteruser', 'blah', dict(tenant_id='master'))], indirect=True
)
def test_dynamic_getter_which_relies_on_a_setting(app, login):
    """With the loyalty campaign example"""
    app.post_json(
        '/tenants/tenant1/settings/set-tenant',
        {'settings': {'loyalty.campaigns': campaigns, 'loyalty.pointFactor': 1}},
    )
    response = app.get('/tenants/tenant1/settings/get-tenant')
    assert response.json['data']['loyalty']['pointFactor'] == 3
    app.post_json(
        '/tenants/tenant1/settings/set-tenant', {'settings': {'loyalty.campaigns': []}}
    )
    response = app.get('/tenants/tenant1/settings/get-tenant')
    assert response.json['data']['loyalty']['pointFactor'] == 1


@pytest.mark.parametrize(
    'login', [('masteruser', 'blah', dict(tenant_id='master'))], indirect=True
)
@pytest.mark.parametrize(
    "value,query",
    [
        (
            True,
            (
                'setLoyaltynoPointsonDiscount/token__{}/tenant_id__tenant2/'
                'username__masteruser/value__true'
            ),
        ),
        (
            False,
            (
                'setLoyaltynoPointsonDiscount/token__{}/tenant_id__tenant2/'
                'username__masteruser/value__false'
            ),
        ),
    ],
)
def test_set_suppressPointsOnDiscount_setting_creates_expected_foxpro_event(
    app, db, value, query, login
):
    """Ensure foxpro event is the expected one."""
    payload = dict(settings={'loyalty.suppressPointsOnDiscount': value})
    response = app.post_json(
        '/tenants/tenant2/settings/set-tenant', payload, status=200
    )
    event = db.events.find_one(dict(method='setLoyaltynoPointsonDiscount'))
    assert event['fpquery'] == query.format(response.request.cookies['sid'])


@pytest.mark.parametrize('login', [('masteruser', 'blah')], indirect=True)
def test_bleach_email_body(app, login):
    """Check if user can update the user settings."""

    evil = 'an <script>evil()</script> example'
    payload = {'settings': {'email': {'body': evil}}}
    response = app.post_json('/settings/set-user', payload)

    clean = 'an &lt;script&gt;evil()&lt;/script&gt; example'
    assert response.json['data'] == {'email': {'body': clean}}


@pytest.mark.parametrize(
    'login', [('masteruser', 'blah', dict(tenant_id='master'))], indirect=True
)
def test_set_settings_cannot_delete_currency(app, db, login):
    """
    currencies cannot be deleted
    """
    payload = {
        'settings': {
            'currencies': [
                {
                    'label': '2.1 Euro',
                    'symbol': 'EUR',
                    'factor': 2.1,
                    'uuid': str(uuid4()),
                }
            ]
        }
    }
    response = app.post_json(
        '/tenants/tenant1/settings/set-tenant', payload, status=400
    )
    assert '2.8 Euro' in response.json['message']


@pytest.mark.parametrize(
    'login', [('masteruser', 'blah', dict(tenant_id='master'))], indirect=True
)
def test_set_settings_cannot_change_currency_label(app, db, login):
    """
    currency labels cannot be changed
    """
    payload = {
        'settings': {
            'currencies': [
                {
                    'label': '2.1 Euro',
                    'symbol': 'EUR',
                    'factor': 2.1,
                    'uuid': str(CURRENCY_ID),
                }
            ]
        }
    }
    response = app.post_json(
        '/tenants/tenant1/settings/set-tenant', payload, status=400
    )
    assert '2.8 Euro' in response.json['message']


@pytest.mark.parametrize(
    'login,tenant',
    [(('masteruser', 'blah', dict(tenant_id='master')), 'tenant1')],
    indirect=['login'],
)
def test_set_settings_currency_event(app, db, login, tenant):
    """
    check an event is added when changing currencies.
    """
    payload = {
        'settings': {
            'currencies': [
                {
                    'label': '2.8 Euro',
                    'symbol': 'EUR',
                    'factor': 2.8,
                    'uuid': str(CURRENCY_ID),
                },
                {'label': '2.1 Euro', 'symbol': 'EUR', 'factor': 2.1},
            ]
        }
    }
    app.post_json('/tenants/{}/settings/set-tenant'.format(tenant), payload, status=200)
    assert db['events'].count_documents({}) == 2


@pytest.mark.parametrize('value,result', [(True, 'true'), (False, 'false')])
def test_set_settings_allow_modify_prices_event(app, db, value, result):
    """
    check an event is added when changing currencies.
    """
    app.post('/login?username=masteruser&password=blah')
    payload = {'settings': {'logistics': {'allowModifyPriceReceivings': value}}}
    app.post_json('/tenants/tenant1/settings/set-tenant', payload, status=200)
    assert (
        f'value__{result}' in db['events'].find_one({'method': 'setsetting'})['fpquery']
    )


@pytest.mark.parametrize(
    # 'login', [('blahuser', 'blah')], indirect=True
    'login,tenant',
    [(('accountmanager', 'blah'), 'tenant1'), (('accountmanager', 'blah'), 'tenant2')],
    indirect=['login'],
)
def test_set_upload_directory(app, db, login, tenant):
    """Check if user can set the sales app settings on the tenant"""
    dir = '0' * 21
    payload = {'settings': {'uploadDirectory': dir}}
    app.post_json(
        '/tenants/%s/account-manager/change-upload-directory' % tenant,
        payload,
        status=200,
    )
    doc = db.tenants.find_one(dict(_id=tenant))
    assert doc['settings']['uploadDirectory'] == dir


@pytest.mark.parametrize('login', [('accountmanager', 'blah')], indirect=True)
def test_duplicate_upload_directory(app, db, login):
    """Check if user can set the sales app settings on the tenant"""
    dir = '0' * 21
    payload = {'settings': {'uploadDirectory': dir}}
    app.post_json(
        '/tenants/%s/account-manager/change-upload-directory' % 'tenant1',
        payload,
        status=200,
    )
    app.post_json(
        '/tenants/%s/account-manager/change-upload-directory' % 'tenant2',
        payload,
        status=400,
    )


@pytest.mark.parametrize(
    'login,tenant',
    [(('masteruser', 'blah', dict(tenant_id='master')), 'tenant1')],
    indirect=['login'],
)
def test_set_settings_regions_event(app, db, login, tenant):
    """
    check an event is added when changing regions.
    """
    payload = {'settings': {'sales': {'regions': ['NL', 'BE', 'DE']}}}
    app.post_json('/tenants/{}/settings/set-tenant'.format(tenant), payload, status=200)
    assert (
        'value__NL%2CBE%2CDE'
        in db['events'].find_one({'method': 'setsetting'})['fpquery']
    )


@pytest.mark.parametrize('login', [('delete-settings-user', 'password')], indirect=True)
def test_delete_user_settings(spynl_data_db, app, login):
    user = spynl_data_db.users.find_one({'username': 'delete-settings-user'})
    assert user['settings']['sales']['showStock']

    app.post_json(
        '/settings/delete-user', {'settings': ['sales.showStock']}, status=200
    )
    app.post_json(
        '/settings/delete-user', {'settings': ['email.autoPopup']}, status=400
    )

    user = spynl_data_db.users.find_one({'username': 'delete-settings-user'})
    with pytest.raises(KeyError):
        user['settings']['sales']['showStock']


@pytest.mark.parametrize('login', [('owner_user', 'blah')], indirect=True)
def test_delete_tenant_settings(spynl_data_db, app, login):
    tenant = spynl_data_db.tenants.find_one({'_id': 'tenant1'})
    assert tenant['settings']['loyalty']['cashback']['giveCashbackOnDiscounts']
    app.post_json(
        '/settings/delete-tenant', {'settings': ['loyalty.cashback']}, status=200
    )
    app.post_json('/settings/delete-tenant', {'settings': ['logoUrl']}, status=400)
    tenant = spynl_data_db.tenants.find_one({'_id': 'tenant1'})
    with pytest.raises(KeyError):
        tenant['settings']['loyalty']['cashback']['giveCashbackOnDiscounts']
