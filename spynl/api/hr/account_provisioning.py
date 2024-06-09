"""
CSV format:

(order of tables and columns does not matter)

[TENANTS]
_id*|name*|legalname*|uploadDirectory*|applications|retail|wholesale|countryCode*
# fields with *'s cannot be empty
# applications should be a comma separated list without any spaces
# differences with previous structure:
# * datafeed -> uploadDirectory
# * added applications, retail and wholesale

[USERS]
tenant_id*|username*|fullname|email|password|tz|type*|roles|wh|language
# fields with *'s cannot be empty
# roles should be a comma separated list without any spaces
# email is required if type is 'standard'
# passwords can only be set for device users
# differences with previous structure:
# * role -> roles
# * removed: applications, name

[CASHIERS]
tenant_id*|name*|fullname*|password*
# fields with *'s cannot be empty
# differences with previous version:
# fullname cannot be empty
# differences with previous structure:
# * names for cashier types are now: 'normal', 'manager' and 'admin'
#   (default: 'normal')

[WAREHOUSES]
tenant_id*|name*|fullname|ean|email|wh*
# fields with *'s cannot be empty
# differences with previous structure:
# * removed: datafeed

other changes from previous csv structure:
* Removed [POS_REASONS], will be added automatically for each tenant with a device
user.
* tenant_id should always be given, even if the whole csv contains only one!

To get the linenumber for the error, add index of error to linenumber of first
entry

"""
import csv
import re
from copy import deepcopy

from marshmallow import ValidationError

from spynl_schemas import account_provisioning

from spynl.main.utils import required_args

from spynl.api.auth.apps_and_roles import APPLICATIONS, ROLES
from spynl.api.auth.authentication import set_password
from spynl.api.auth.exceptions import SpynlPasswordRequirementsException
from spynl.api.auth.utils import validate_password
from spynl.api.hr.exceptions import AccountImportValidationError
from spynl.api.hr.utils import validate_username


@required_args('account_data_string')
def import_new_accounts(request):
    """
    import new accounts.

    ---

    post:
      description: >

        This endpoint can be used to import *new* accounts. You can import new
        tenants, users, cashiers and warehouses.

        If there are any validation errors for the provided csv, an
        AccountImportValidationError will be raised. The message will be a
        markdown formatted string. If the structure of the error is not as
        expected, the message will be a json object instead.\n

        If a tenant is added without an owner, or roles are added to users
        without the tenant having the corresponding applications, the status
        of the response will be 'warning' and the message will contain the
        warning(s) in addition to the normal message.\n

        If the status is 'ok' the message will say how many of each document
        were added, it's important that the user can easily see this message.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        account_data_string | string  | &#10004; | csv string (see csv format below)\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error' or 'warning'\n
        message   | string | succes or error description
        (see implementation notes)\n

        ### CSV format

        (order of tables and columns does not matter)\n

        [TENANTS]<br/>
        **_id**|**name**|**legalname**|**uploadDirectory**|applications|retail|
        wholesale\n
        * **bold** fields are required\n
        * applications should be a comma separated list without any spaces\n
        * retail and wholesale should be booleans and at least one of them needs
        to be true\n
        ---\n
        [USERS]<br/>
        **tenant_id**|**username**|fullname|email|password|tz|**type**|roles|wh|
        **countryCode**\n
        * **bold** fields are required\n
        * roles should be a comma separated list without any spaces\n
        * email is required if type is 'standard'\n
        * passwords can only be added for 'device' users\n
        ---\n
        [CASHIERS]<br/>
        **tenant_id**|**name**|**fullname**|**password**\n
        * **bold** fields are required\n

        ---\n
        [WAREHOUSES]<br/>
        **tenant_id**|**name**|fullname|ean|email|**wh**\n
        * **bold** fields are required\n
      tags:
        - account provisioning
    """
    # We need to make sure that the data for this endpoint is never send to
    # sentry, because it may contain sensitive data. To be able to blacklist the
    # variable, we use a long, specific name.
    data = get_data_from_csv(request.args['account_data_string'])
    if not data:
        raise AccountImportValidationError('Empty or invalid data provided.')

    db = request.db

    # first load all the data into the schemas so any validation errors are
    # caught before saving
    restricted_roles = ('sww-api', 'spynl-developer', 'owner')
    context = {
        'db': db,
        'check_if_tenants_exist': True,
        'allowed_roles': list(
            role
            for role in ROLES
            if (
                ROLES[role]['type'] == 'tenant'
                and ('sw-' not in role and role not in restricted_roles)
            )
        ),
        'allowed_applications': [
            app for app in APPLICATIONS if not APPLICATIONS[app].get('internal')
        ],
        'username_validator': username_validator,
        'password_validator': password_validator,
    }
    validated_data = Data(context=context).load(deepcopy(data))

    # start saving
    message = ''
    if validated_data.get('tenants'):
        tenants_result = db.tenants.insert_many(validated_data['tenants'])
        message += '{} tenant(s) added, '.format(len(tenants_result.inserted_ids))

    if validated_data.get('users'):
        # save users
        users_result = db.users.insert_many(validated_data['users'], ordered=True)
        message += '{} user(s) added, '.format(len(users_result.inserted_ids))

        # add owners to tenants
        for owner_index, tid in validated_data['owners'].items():
            setter = {'$addToSet': {'owners': users_result.inserted_ids[owner_index]}}
            db.tenants.update_one({'_id': tid}, setter)

        devices = validated_data['devices']
        for device_index, tenant_id in devices.items():
            # we do not have to check if documents already exist, because only
            # new devices can be added in this endpoint.
            info = {
                'user_id': str(users_result.inserted_ids[device_index]),
                'tenant_id': [tenant_id],
            }
            POS_SETTINGS.update(info)
            db.pos_settings.insert_one(deepcopy(POS_SETTINGS))
            PAYMENT_METHODS.update(info)
            db.payment_methods.insert_one(deepcopy(PAYMENT_METHODS))
            password = data['users'][device_index].get('password')
            if password:
                set_password(request, validated_data['users'][device_index], password)

        # only add pos_reasons for each tenant with a device once (even if they
        # have more than one device)
        for tenant_id in set(devices.values()):
            # check for existing, the tenant might already have a device
            result = db.pos_reasons.find_one({'tenant_id': tenant_id})
            if not result:
                POS_REASONS.update({'tenant_id': [tenant_id]})
                db.pos_reasons.insert_one(deepcopy(POS_REASONS))

    if validated_data.get('cashiers'):
        cashiers_result = db.cashiers.insert_many(validated_data['cashiers'])
        message += '{} cashier(s) added, '.format(len(cashiers_result.inserted_ids))

    if validated_data.get('warehouses'):
        warehouses_result = db.warehouses.insert_many(validated_data['warehouses'])
        message += '{} warehouse(s) added, '.format(len(warehouses_result.inserted_ids))

    # TODO if necessary: try except on saves to be able to tell user which
    # records were saved in case of error for all insert_many saves

    if validated_data.get('warnings'):
        message += 'warnings: {}'.format(validated_data['warnings'])
        return {'status': 'warning', 'message': message}
    return {'message': message}


def get_data_from_csv(raw_data):
    """
    Get the data from a csv string

    * split the string using the table names (e.g. [TENANTS])
    * if an entry in the split data is one of the collections, the next
      entry will be the corresponding table
    * read in the table as a list of dictionaries, the first row will be used
      for keys (ignoring empty lines and comment lines)
    """
    data = {}
    tables = re.split(r'\[([A-Z_]+)\]', raw_data)
    table_names = ('TENANTS', 'USERS', 'CASHIERS', 'WAREHOUSES')

    for i, value in enumerate(tables):
        if value in table_names:
            data[value.lower()] = list(
                csv.DictReader(
                    (
                        line
                        for line in tables[i + 1].splitlines()
                        if line and not line.startswith('#')
                    ),
                    delimiter='|',
                )
            )
    return data


class Data(account_provisioning.AccountProvisioning):
    """Raise a spynl error (maybe should be try execpt)"""

    def handle_error(self, exc, data, **kwargs):
        """Raise a SpynlError"""
        raise AccountImportValidationError(exc.normalized_messages())


def password_validator(password):
    """Wrapper around validate_password to make it raise a ValidationError"""
    try:
        validate_password(password)
    except SpynlPasswordRequirementsException as e:
        # The translate means that the message will be in the users language,
        # even though all the other messages will be in English (this could be
        # avoided by using make_localizer to force an English translation)
        raise ValidationError(e.message.translate(), 'password')


def username_validator(username):
    """
    Wrapper that makes sure that the message gets translated (string conversion
    adds the translation key).
    """
    try:
        validate_username(username)
    except ValueError as e:
        raise ValidationError(e.args[0].translate())


POS_SETTINGS = {
    'active': True,
    'setting_header': 'Printer',
    'settings': [
        {
            'selection': '_id',
            'resource': 'templates',
            'filters': '{"tags": {"$all": ["transactions", "receipt", "sale"]}}',
            'value': 'receipt-tm20-plain.mustache',
            'label': 'Layout kassabon',
            'key': 'printer_layout',
            'type': 'dropdown',
            'display': 'name',
        },
        {
            'selection': '_id',
            'resource': 'templates',
            'filters': '{"tags": {"$all": ["transactions", "coupon"]}}',
            'value': 'coupon-plain.mustache',
            'label': 'Layout tegoedbon',
            'key': 'printer_coupon_layout',
            'type': 'dropdown',
            'display': 'name',
        },
        {
            'selection': '_id',
            'resource': 'templates',
            'filters': '{"tags": {"$all": ["transactions", "transit"]}}',
            'value': 'transit.mustache',
            'label': 'Layout transitorder',
            'key': 'printer_transit_layout',
            'type': 'dropdown',
            'display': 'name',
        },
        {
            'type': 'checked',
            'value': 'true',
            'key': 'printer_cutter',
            'label': 'Kassabon afsnijden',
        },
        {
            'type': 'checked',
            'value': 'false',
            'key': 'printer_drawerkick',
            'label': 'Kassalade openen',
        },
        {
            'type': 'checked',
            'value': 'false',
            'key': 'double_receipt',
            'label': 'Dubbele kassabon',
        },
        {
            'type': 'checked',
            'value': 'false',
            'key': 'printer_extendedreceipt',
            'label': 'Extra artikelinfo',
        },
        {
            'type': 'textarea',
            'value': 'Bedankt en tot ziens.',
            'key': 'receipt_footer',
            'label': 'Tekst onder bon',
        },
        {
            'selection': '_id',
            'resource': 'templates',
            'filters': '{"tags": {"$all": ["transactions", "withdrawal"]}}',
            'value': 'pos-withdrawal-plain.mustache',
            'label': 'Layout kasopname',
            'key': 'printer_withdrawal_layout',
            'type': 'dropdown',
            'display': 'name',
        },
        {
            'selection': '_id',
            'resource': 'templates',
            'filters': '{"tags": "eos"}',
            'value': 'eos-plain',
            'label': 'Layout EOS',
            'key': 'printer_eos_layout',
            'type': 'dropdown',
            'display': 'name',
        },
        {
            'type': 'checked',
            'value': 'true',
            'key': 'receipt_printpoints',
            'label': 'Print sparenpunten',
        },
    ],
}

PAYMENT_METHODS = {
    'active': True,
    'rules': {
        'cash': {
            'active': True,
            'allow_neg': True,
            'allow_pos': True,
            'article': True,
            'coupled': False,
            'customer': False,
            'display': 'Contant',
            'readOnly': False,
            'reason': False,
            'turnover': '+',
            'type': 'cash',
        },
        'consignment': {
            'active': True,
            'allow_neg': False,
            'allow_pos': True,
            'article': True,
            'coupled': False,
            'customer': True,
            'display': 'Op zicht',
            'readOnly': False,
            'reason': False,
            'turnover': 'none',
            'type': 'other',
        },
        'creditcard': {
            'active': True,
            'allow_neg': False,
            'allow_pos': True,
            'article': True,
            'coupled': False,
            'customer': False,
            'display': 'Creditcard',
            'readOnly': False,
            'reason': False,
            'turnover': '+',
            'type': 'electronic',
        },
        'creditreceipt': {
            'active': True,
            'allow_neg': True,
            'allow_pos': True,
            'article': True,
            'coupled': False,
            'customer': False,
            'display': 'Tegoedbon',
            'readOnly': True,
            'reason': False,
            'turnover': '+',
            'type': 'other',
        },
        'pin': {
            'active': True,
            'allow_neg': False,
            'allow_pos': True,
            'article': True,
            'coupled': False,
            'customer': False,
            'display': 'PIN',
            'readOnly': False,
            'reason': False,
            'turnover': '+',
            'type': 'electronic',
        },
        'storecredit': {
            'active': True,
            'allow_neg': True,
            'allow_pos': True,
            'article': True,
            'coupled': False,
            'customer': True,
            'display': 'Op rekening',
            'readOnly': True,
            'reason': False,
            'turnover': '+',
            'type': 'other',
        },
        'withdrawel': {
            'active': True,
            'allow_neg': True,
            'allow_pos': True,
            'article': False,
            'coupled': False,
            'customer': False,
            'display': 'Kasopname',
            'readOnly': True,
            'reason': True,
            'turnover': '+',
            'type': 'cash',
        },
    },
}

POS_REASONS = {
    'active': True,
    'OpenDrawerReasons': [
        'Geen reden',
        'Geld wisselen',
        'Correctie betaalwijze',
        'Kasopmaak',
        'Diverse',
    ],
    'WithdrawalTypes': ['1. Maaltijdvergoeding', '2. Kantoorbenodigdheden', '3. Porto'],
    'DiscountReasons': [
        {'key': '1', 'desc': '1. Uitverkoop'},
        {'key': '2', 'desc': '2. Vaste klanten korting'},
        {'key': '3', 'desc': '3. Personeelskorting'},
        {'key': '4', 'desc': '4. Kadobon'},
        {'key': '5', 'desc': '5. Setprijs'},
        {'key': '6', 'desc': '6. Klacht'},
    ],
}
