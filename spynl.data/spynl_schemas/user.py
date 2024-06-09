import random
import string

import pytz
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_dump,
    pre_load,
    validate,
    validates,
    validates_schema,
)

from spynl_schemas.fields import BleachedHTMLField, Nested, ObjectIdField
from spynl_schemas.shared_schemas import BaseSchema, BaseSettingsSchema
from spynl_schemas.utils import BAD_CHOICE_MSG, obfuscate

ADMIN_ROLES = {'sw-servicedesk', 'sw-admin', 'sw-consultant'}
ADMIN_MY_ROLES = ADMIN_ROLES | {'owner', 'account-admin'}


class ReportAcls(Schema):
    """Access keys to give users access to various reports."""

    # NOTE Yes this is for real. The keys are UUIDs, and they contain dashed
    # and can start with a number. So they are invalid python identifiers. For
    # each of these the fieldname is a human readable name. But it will dump
    # to, load from and use the uuid attribute name.
    sales_overview_report = fields.Boolean(
        load_default=False,
        data_key='f0adf069-f964-468f-a089-c2154a7af9fd',
        attribute='f0adf069-f964-468f-a089-c2154a7af9fd',
        metadata={'description': 'Sales Overview report'},
    )

    article_status_retail_including_vat_report = fields.Boolean(
        load_default=False,
        data_key='1ba601c7-b8f6-41e0-8005-62ef23947f7d',
        attribute='1ba601c7-b8f6-41e0-8005-62ef23947f7d',
        metadata={'description': 'Article Status - Retail - Including VAT report'},
    )

    sales_per_client_wholesale_report = fields.Boolean(
        load_default=False,
        data_key='708a0b73-e4dd-4969-b96e-23dbeb4f74ce',
        attribute='708a0b73-e4dd-4969-b96e-23dbeb4f74ce',
        metadata={'description': 'Sales Per Client - Wholesale report'},
    )

    sales_per_client_retail_report = fields.Boolean(
        load_default=False,
        data_key='0845d79e-abbd-41fd-b613-071ac44ea84c',
        attribute='0845d79e-abbd-41fd-b613-071ac44ea84c',
        metadata={'description': 'Sales Per Client - Retail report'},
    )

    article_status_wholesale_report = fields.Boolean(
        load_default=False,
        data_key='f27870b0-107e-11e3-8ffd-0800200c9a66',
        attribute='f27870b0-107e-11e3-8ffd-0800200c9a66',
        metadata={'description': 'Article Status - Wholesale report'},
    )

    sales_report_retail_report = fields.Boolean(
        load_default=False,
        data_key='f42120d1-b97b-45c4-baf4-5c45bd1f1a7e',
        attribute='f42120d1-b97b-45c4-baf4-5c45bd1f1a7e',
        metadata={'description': 'Sales Report - Retail report'},
    )

    article_status_retail_excluding_vat_report = fields.Boolean(
        load_default=False,
        data_key='b5905518-fba9-49ca-9673-cb8a15b891b8',
        attribute='b5905518-fba9-49ca-9673-cb8a15b891b8',
        metadata={'description': 'Article Status - Retail - Excluding VAT report'},
    )

    eos_per_day_report = fields.Boolean(
        load_default=False,
        data_key='5efb9fb1-50a6-4d2b-bc1d-e0cbb531ab82',
        attribute='5efb9fb1-50a6-4d2b-bc1d-e0cbb531ab82',
        metadata={'description': 'EOS Per Day report'},
    )

    end_of_day_report = fields.Boolean(
        load_default=False,
        data_key='f743ebbc-14cc-485d-afaa-bd3b58f8fdf4',
        attribute='f743ebbc-14cc-485d-afaa-bd3b58f8fdf4',
        metadata={'description': 'End-of-day report'},
    )


class SecondScreenSettings(BaseSettingsSchema):
    """Settings for SecondScreen"""

    secondScreenId = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_ROLES | {'secondscreen-admin'},
            'description': 'This is the API key used by the client to communicate '
            'with the printQ service.',
        },
    )
    playlistId = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_MY_ROLES | {'secondscreen-admin'},
            'description': 'The id of the selected playlist for this user. This id '
            'has a one-to-one relationship to the _id of a playlist '
            'document in the playlists collection.',
        },
    )
    duration = fields.Integer(
        load_default=10,
        dump_default=10,
        metadata={
            'roles': ADMIN_MY_ROLES | {'secondscreen-admin'},
            'description': 'This setting controls the amount of seconds an image is '
            'shown on the screen.',
        },
    )
    showCustomer = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_MY_ROLES | {'secondscreen-admin'},
            'description': 'This setting turns on or off the display of customer data '
            'on the second screen. When this setting is turned on the '
            "customer's name and loyalty point balance will be shown.",
        },
    )


class CashPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns cash payment on or off.',
        },
    )
    requireCustomer = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Specifies if a customer is required with this payment.',
        },
    )
    allowNegative = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Specifies if negative payments are allowed.',
        },
    )


class ConsignmentPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns consignment payment on or off.',
        },
    )


class CreditCardPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns creditcard payment on or off.',
        },
    )
    requireCustomer = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Specifies if a customer is required with this payment.',
        },
    )
    allowNegative = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Specifies if negative payments are allowed.',
        },
    )


class CreditReceiptPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns creditreceipt payment on or off.',
        },
    )
    requireCustomer = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Specifies if a customer is required with this payment.',
        },
    )


class PinPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns pin payment on or off.',
        },
    )
    coupled = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Specifies if pin is coupled or not, ie if is '
            'connected to PayPlaza or Pay. or if it works the same as credit '
            'card',
        },
    )
    requireCustomer = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Specifies if a customer is required with this payment.',
        },
    )
    allowNegative = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Specifies if negative payments are allowed.',
        },
    )


class StoreCreditPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns storecredit payment on or off.',
        },
    )
    requireCustomer = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Specifies if a customer is required with this payment.',
        },
    )


class WithdrawalPaymentSettings(BaseSettingsSchema):
    available = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'This setting turns withdrawal payment on or off.',
        },
    )


class PaymentMethodsSettings(BaseSettingsSchema):
    cash = Nested(
        CashPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for cash payment method.'},
    )
    consignment = Nested(
        ConsignmentPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for consignment payment method.'},
    )
    creditCard = Nested(
        CreditCardPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for creditcard payment method.'},
    )
    creditReceipt = Nested(
        CreditReceiptPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for creditreceipt payment method'},
    )
    pin = Nested(
        PinPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for pin payment method.'},
    )
    storeCredit = Nested(
        StoreCreditPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for storecredit payment method.'},
    )
    withdrawal = Nested(
        WithdrawalPaymentSettings,
        dump_default=dict,
        metadata={'description': 'Settings for withdrawal payment method.'},
    )


class EmailSettings(BaseSettingsSchema):
    """Settings for emailing from Softwear applications"""

    active = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'This setting turns on or off the email feature.',
        },
    )
    autoPopup = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'Controls whether the email and reprint popup in the POS '
            'pin login opens automatically after a sale.',
        },
    )
    sender = fields.String(
        load_default='info@uwkassabon.com',
        dump_default='info@uwkassabon.com',
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'The name that will show up as the sender of the email',
        },
    )
    replyTo = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'This is the optional reply-to address to allow a user to '
            'override the reply to address.',
        },
    )
    subject = fields.String(
        load_default='Uw kassabon',
        dump_default='Uw kassabon',
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': "The email subject for receipts.",
        },
    )
    body = BleachedHTMLField(
        load_default='Uw kassabon',
        dump_default='Uw kassabon',
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'The email body for receipts.',
        },
    )

    @validates('replyTo')
    def validate_email(self, value):
        # We only validate in case it's not an empty string.
        if value:
            fields.Email()._validate(value)


class FiscalPrinterSettings(BaseSettingsSchema):
    """Settings for configuring a fiscal printer"""

    active = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'This setting turns on or off the Fiscal printer.',
        },
    )
    printerType = fields.String(
        load_default='Italy',
        dump_default='Italy',
        validate=validate.OneOf(
            choices=['Italy'],
            error=BAD_CHOICE_MSG,
        ),
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'This setting selects one from the supported fiscal'
            ' printers.',
        },
    )
    hostName = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'The IP address or hostname of the printer on the'
            ' local network.',
        },
    )
    printerId = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'Printer ID, to be found at the end of the receipt',
        },
    )


class salesPropertyFilter(Schema):
    property = fields.String(
        required=True, metadata={'description': 'The property name'}
    )
    values = fields.List(
        fields.String(),
        required=True,
        validate=validate.Length(min=1),
        metadata={'description': 'The values the property may be filtered by.'},
    )


class SalesSettings(BaseSettingsSchema):
    """Settings for the sales app"""

    allowed_roles = ADMIN_MY_ROLES | {'sales-admin'}

    agentFilter = Nested(
        salesPropertyFilter,
        allow_none=True,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'A list of settings describing what the agent may filter '
            'by.',
        },
    )

    showStock = fields.Boolean(
        dump_default=False,
        metadata={
            'roles': allowed_roles | {'sales-user'},
            'description': 'Show stock with the article or not',
        },
    )
    barcodeScanning = fields.String(
        dump_default='select',
        validate=validate.OneOf(choices=['favorite', 'select'], error=BAD_CHOICE_MSG),
        metadata={
            'roles': allowed_roles | {'sales-user'},
            'description': "If the setting is 'favorite', the scanned article will be "
            "added to the favorites list. If the setting is 'select' "
            'the scanned article will be selected immediately',
        },
    )
    region = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Region that an agent(!) is allowed to serve',
        }
    )
    # NOTE: this setting might be problematic if a user is a sales agent for
    # multiple tenants. In that case, they should have a separate account for
    # each tenant.
    newCustomerAllowed = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'roles': allowed_roles,
            'description': 'Allow the user to add new customer.',
        },
    )

    @validates('region')
    def validate_region(self, value):
        available_regions = self.context.get('available_regions')
        if not available_regions:
            return

        if value not in available_regions:
            raise ValidationError('Region is unavailable on the active tenant')


class PickingSettings(BaseSettingsSchema):
    """Settings for the picking app"""

    pickingListPrinterId = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Printer identifier. Is used as a printer key for '
            "pickingList in case of 'printer' setting equal to printerQ2.",
        },
    )
    shippingLabelPrinterId = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Printer identifier. Is used as a printer key for '
            "shipping in case of 'printer' setting equal to printerQ2.",
        },
    )


class ApplicationLinkSettings(BaseSettingsSchema):
    ecwid_link = fields.Boolean()
    foxpro_backoffice = fields.Boolean()
    hardwearshop = fields.Boolean()


class Settings(BaseSettingsSchema):
    """Schema for the user settings"""

    TwoFactorAuthEnabled = fields.Boolean(
        metadata={
            # not set via the settings endpoint, but the specific set_2fa endpoint
            'roles': set(),
            'description': 'Enable Two Factor Authentication',
        }
    )
    printer = fields.String(
        load_default='browser',
        dump_default='browser',
        validate=validate.OneOf(
            choices=['printerQ2', 'browser', 'localThermal', 'usb'],
            error=BAD_CHOICE_MSG,
        ),
        metadata={'roles': ADMIN_ROLES, 'description': 'Mechanism used for printing.'},
    )
    printerId = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Printer identifier. Is used as a printer key in case of '
            "'printer' setting equal to printerQ2.",
        },
    )
    # TODO: or should this be done with allow_none?
    pinProvider = fields.String(
        dump_default='none',
        validate=validate.OneOf(
            choices=[None, 'none', 'payPlaza4', 'payNL'], error=BAD_CHOICE_MSG
        ),
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'This setting governs the electronic payment gateway '
            'provider used to make credit card and PIN transactions. Currently we '
            'support only one payment provider who has two versions of its web '
            "service API. Default to 'none'.",
        },
    )
    payNLDeviceId = fields.String(
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Device id used for the pay.nl payment provider. Each '
            'device in a store should have a differen device id.',
        }
    )
    payNLStoreId = fields.String(
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Store id used for the pay.nl payment provider. This '
            'should be the same for every device in the same store.',
        }
    )
    payNLToken = fields.String(
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Tenant wide token used for the pay.nl payment provider.',
        }
    )
    pinId = fields.String(
        dump_default='',
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'This is the AIP key used to access the payment gateway. '
            'Default to empty string.',
        },
    )
    secondScreen = Nested(
        SecondScreenSettings,
        dump_default=dict,
        metadata={
            'roles': ADMIN_ROLES | {'secondscreen-admin'},
            'description': 'Settings for the Second Screen (Play) application. This '
            'application displays the sales transaction and a playlist '
            'of images.',
        },
    )
    paymentMethods = Nested(
        PaymentMethodsSettings,
        dump_default=dict,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Settings for payment methods in POS',
        },
    )
    email = Nested(
        EmailSettings,
        dump_default=dict,
        metadata={
            'description': 'Settings for emailing from Softwear applications. '
            'Primarily these settings control emailing receipts from '
            'the POS application.'
        },
    )
    fiscalPrinter = Nested(
        FiscalPrinterSettings,
        dump_default=dict,
        metadata={'description': 'Settings for the Fiscal printer.'},
    )
    sales = Nested(
        SalesSettings,
        dump_default=dict,
        metadata={'description': 'Settings for the sales application.'},
    )
    picking = Nested(
        PickingSettings,
        dump_default=dict,
        metadata={'description': 'Settings for the picking application.'},
    )
    applicationLinks = Nested(
        ApplicationLinkSettings,
        metadata={
            'description': 'Determines which additional application links should be '
            'shown for this user.'
        },
    )
    noAutoPrint = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'When true, the POS will not automatically print '
            'receipts upon checkout.'
        },
    )
    displayAndPrintDiscountReason = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'When true, the POS will display and print discount reason.'
        },
    )
    dashboardAllowedLocations = fields.List(
        fields.String(),
        load_default=[],
        dump_default=[],
        metadata={
            'description': 'Locations that are available for viewing to the user.'
        },
    )

    @pre_load()
    def default_device_settings(self, data, **kwargs):
        """add defaults for a device"""
        if self.context.get('device'):
            if 'email' not in data:
                data['email'] = {}
            if 'secondScreen' not in data:
                data['secondScreen'] = {}

        return data

    @post_dump
    def obfuscate(self, data, **kwargs):
        """obfuscate sensitive settings"""
        for setting in ['payNLToken']:
            if data.get(setting):
                data[setting] = obfuscate(data[setting])
        return data


class Roles(Schema):
    """Schema for the roles of a user"""

    tenant = fields.List(fields.String, metadata={'description': 'List of roles.'})

    @validates('tenant')
    def check_allowed_roles(self, value):
        if 'allowed_roles' in self.context:
            roles = set(value)
            allowed_roles = set(self.context['allowed_roles'])
            if not roles.issubset(allowed_roles):
                raise ValidationError(
                    'Unknown role(s): {}'.format(roles - allowed_roles)
                )


class User(BaseSchema):
    """Schema for users"""

    _id = ObjectIdField(required=True, dump_only=True)
    email = fields.Email(
        allow_none=True,
        load_default=None,
        metadata={
            'description': "The user's email. This can be empty or not present at "
            'all, e.g. in the case of an device account. If a user has '
            'no email, any emails will be sent to the owners of the '
            'tenant the user belongs to. The email is unique if not '
            'empty.'
        },
    )
    username = fields.String(
        required=True,
        metadata={'description': 'The username field. This is a unique field.'},
    )
    fullname = fields.String(
        required=True, metadata={'description': "User's full name. Ex. 'John Smith'."}
    )
    roles = fields.Dict(
        keys=fields.String(),
        values=Nested(Roles),
        load_default=dict,
        metadata={
            'description': 'Roles for the user. The structure of the dictionary is: '
            "{tenant_id: {'tenant': [list of roles]}}. A user can have "
            'roles for multiple tenants, for now the only type of role '
            "possible is 'tenant'."
        },
    )
    settings = Nested(
        Settings, load_default=dict, metadata={'description': 'Settings for the user'}
    )
    reportacls = Nested(
        ReportAcls,
        load_default=dict,
        metadata={
            'description': 'Access keys to give users access to various reports.'
        },
    )
    type = fields.String(
        required=True,
        validate=validate.OneOf(choices=['standard', 'device'], error=BAD_CHOICE_MSG),
        metadata={
            'description': 'The type of user. The current supported types are '
            "'standard', or 'device'. A device user is used by a "
            'physical POS device to log into to our system. These '
            'device users use the POS. Finally, a standard user is any '
            'user that does not fit into the device or api user '
            'categories. Note: for now we do not allow api yet.'
        },
    )
    tz = fields.String(
        load_default='Europe/Amsterdam',
        validate=validate.OneOf(choices=pytz.all_timezones_set, error=BAD_CHOICE_MSG),
        metadata={
            'description': "User's timezone name. The value should be recognized by "
            'http://momentjs.com/timezone/.'
        },
    )
    language = fields.String(
        load_default='nl-nl',
        validate=validate.OneOf(
            choices=['nl-nl', 'en-gb', 'fr-fr', 'de-de', 'it-it', 'es-es'],
            error=BAD_CHOICE_MSG,
        ),
        metadata={'description': 'Preferred language for the user.'},
    )
    default_application = fields.Dict(
        keys=fields.String(),
        values=fields.String(),
        load_default=dict,
        metadata={
            'description': 'Dictionary for default applications. Keys are tenantids, '
            'values the corresponding default applications.'
        },
    )
    wh = fields.String(
        allow_none=True,
        metadata={
            'description': 'The default warehouse for the user. This is used for '
            'users who log in to the POS.'
        },
    )
    deviceId = fields.String(
        metadata={
            'description': 'The id of the device if user is used for logging into the '
            'POS. The id should be unique for the tenant and usually '
            'is a set of 5 alphanumeric digits.'
        }
    )

    @validates('username')
    def validate_username(self, value):
        """
        Use the validator provided in the context to validate the username and
        check for uniqueness.
        """
        if 'username_validator' in self.context:
            self.context['username_validator'](value)
        if 'db' in self.context:
            if self.context['db'].users.count({'username': value}):
                raise ValidationError('Username is already in use.')

    @validates('email')
    def validate_email_uniqueness(self, value):
        """validate that email is unique if an email is given"""
        if 'db' in self.context and value:
            if self.context['db'].users.count({'email': value}):
                raise ValidationError('Email is already in use.')

    @validates_schema(skip_on_field_errors=False)
    def validate_schema(self, data, **kwargs):
        try:
            tenant_id = self.context.get('tenant_id', data['tenant_id'][0])
        # because we do not skip on field errors, tenant id might not be in data
        except KeyError:
            tenant_id = None
        roles = set(data.get('roles', {}).get(tenant_id, {}).get('tenant', []))

        if data.get('type') == 'device':
            if len(data.get('tenant_id', [])) > 1:
                msg = ('A device is only allowed to have one tenant',)
                raise ValidationError(msg, 'type')

        # standard user without email
        elif not data.get('email'):
            if not roles <= {'inventory-user', 'pos-device'}:
                msg = ('An email is required for standard users',)
                raise ValidationError(msg, 'email')

            elif len(data.get('tenant_id', [])) > 1:
                msg = (
                    'A non device user without email is only allowed to have'
                    ' one tenant'
                )
                raise ValidationError(msg, 'email')

    @staticmethod
    def get_new_device_id(db, tenant_id):
        """
        Provide a device id of 5 alphanumeric digits that is unique for the tenant.
        """

        def random_string():
            return ''.join(
                random.choice(string.ascii_uppercase + string.digits) for _ in range(5)
            )

        for i in range(100):
            device_id = random_string()
            if not db.users.find_one({'tenant_id': tenant_id, 'deviceId': device_id}):
                return device_id
        raise ValidationError('Could not generate a new deviceId')
