import datetime
import uuid
from itertools import combinations

from marshmallow import (
    ValidationError,
    fields,
    post_dump,
    validate,
    validates,
    validates_schema,
)

from spynl_schemas.fields import LenientDateTimeField, Nested, ObjectIdField
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.shared_schemas import (
    Address,
    BaseSettingsSchema,
    Contact,
    Currency,
    Logo,
    Property,
)
from spynl_schemas.utils import (
    BAD_CHOICE_MSG,
    COUNTRIES,
    cast_percentage,
    contains_one_primary,
    obfuscate,
    validate_unique_list,
)

ADMIN_ROLES = {'sw-servicedesk', 'sw-admin', 'sw-consultant'}
ADMIN_MY_ROLES = ADMIN_ROLES | {'owner', 'account-admin'}


class LoyaltyException(Exception):
    pass


def to_date(value):
    """helper function to check campaign dates"""
    try:
        return datetime.date(*[int(i) for i in value.split('-')])
    except (TypeError, ValueError, AttributeError) as err:
        raise ValueError(str(err))


class Campaign(BaseSettingsSchema):
    """Schema for a loyalty campaign"""

    startDate = fields.String(
        required=True,
        metadata={
            'description': 'The start date of the campaign in this format: '
            "'YYYY-MM-DD'. Campaigns are measured in full days."
        },
    )
    endDate = fields.String(
        required=True,
        metadata={
            'description': 'The end date of the campaign in this format: '
            "'YYYY-MM-DD'. Campaigns are measured in full days."
        },
    )
    factor = fields.Float(
        required=True, metadata={'description': 'The value to use as a campaign value.'}
    )

    @validates_schema
    def all_fields_required(self, data, **kwargs):
        """
        Partial is propagated to all nested schemas. However, this schema should
        never be partially loaded.
        """
        for field in self.fields:
            if field not in data:
                raise ValidationError('All fields are required for campaigns')

    @validates_schema
    def check_dates(self, data, **kwargs):
        for key in ('startDate', 'endDate'):
            # missing data will be caught by other checks
            if key not in data:
                return
            # check startDate, endDate conform with <Y-m-d> format
            try:
                to_date(data[key])
            except ValueError:
                raise ValidationError('Invalid date format', key)

        if to_date(data['endDate']) < to_date(data['startDate']):
            raise LoyaltyException('Start date should be before end date.')


class Cashback(BaseSettingsSchema):
    """settings for the cashback coupon"""

    text = fields.String(
        load_default='',
        dump_default='',
        metadata={
            'description': 'Text which will be added to the printed coupon, '
            'specifying for instance validity and conditions.'
        },
    )
    # The foxpro event for validity is generated in the Loyalty schema
    validity = fields.Integer(
        load_default=0,
        dump_default=0,
        metadata={
            'description': 'Period in days after which a coupon expires. If 0, the '
            'coupon does not expire.'
        },
    )
    giveCashbackOnDiscounts = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Controls whether cashback is handed out on discounted '
            'products'
        },
    )


class Loyalty(BaseSettingsSchema):
    """Loyalty program settings (retail only)"""

    cashback = Nested(
        Cashback,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'Settings for the cashback coupon.',
        },
    )
    customerCashback = fields.Float(
        load_default=0,
        dump_default=0,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'Cashback is a percentage of the total owed by a customer '
            'per sales transaction. This percentage is given back to the consumer in '
            'the form of a coupon which can be used on the next transaction. This '
            'percentage is variable and is stored in the couponWorth property '
            '(presently not implemented).',
        },
    )
    suppressPointsOnDiscount = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'The flag that decides if points should be calculated when '
            'a sales transaction has other discounts added. Default to false.',
        },
    )
    calculatePointsPerReceipt = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'The flag that turns the Softwear provided loyalty program '
            'on or off. Default to true.',
        },
    )

    # for now these fields are not needed yet, but they should be added back
    # eventually
    # When couponWorth is implemented, change customerCashback description.
    # calculatePercentageCoupons = fields.Boolean(default=False)
    # couponWorth = fields.Integer(default=0)

    pointValue = fields.Float(
        load_default=1,
        dump_default=1,
        validate=validate.Range(min=1),
        metadata={
            'roles': ADMIN_ROLES,
            'minimum': 0,
            'exclusiveMinimum': True,
            'description': 'The value of a point. Example: if pointFactor is 1 and '
            'pointValue is 10, then for every 1 EUR purchased, 10 points are '
            'calculated.',
        },
    )
    pointFactor = fields.Float(
        load_default=1, dump_default=1, metadata={'roles': ADMIN_ROLES}
    )
    campaigns = Nested(
        Campaign,
        many=True,
        load_default=list,
        dump_default=list,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Used to store sets of loyalty campaigns. This usually '
            'occurs during special occasions such as a holiday or seasonal sale where '
            'a retailer wishes to give more points as a bonus to shoppers.',
        },
    )

    @validates('campaigns')
    def campaigns_cannot_overlap(self, value):
        for left, right in combinations(value, 2):
            # Get the latest, and earliest start and end dates respectively from
            # the left and right campaigns
            latest_start = max(
                [to_date(d) for d in (left['startDate'], right['startDate'])]
            )
            earliest_end = min(
                [to_date(d) for d in (left['endDate'], right['endDate'])]
            )

            # count the number of overlapping days (inclusive)
            if ((earliest_end - latest_start).days) >= 0:
                raise LoyaltyException('Campaign overlap.')

    @staticmethod
    def generate_fpqueries(data, *common):
        queries = []

        if 'pointValue' in data:
            queries.append(
                (
                    'setLoyaltyPointValue',
                    [
                        *common,
                        ('setting', 'pointValue'),
                        ('value', cast_percentage(resolve(data, 'pointValue'))),
                    ],
                )
            )
        if 'suppressPointsOnDiscount' in data:
            queries.append(
                (
                    'setLoyaltynoPointsonDiscount',
                    [*common, ('value', resolve(data, 'suppressPointsOnDiscount'))],
                )
            )
        if 'campaigns' in data:
            campaigns = []
            for campaign in data['campaigns']:
                campaigns.extend(
                    [
                        ('startdate', campaign['startDate'].replace('-', '')),
                        ('enddate', campaign['endDate'].replace('-', '')),
                        ('factor', cast_percentage(campaign['factor'])),
                    ]
                )
            queries.append(('setLoyaltyCampaigns', [*common, *campaigns]))

        if 'validity' in data.get('cashback', {}):
            queries.append(
                (
                    'setsetting',
                    [
                        *common,
                        ('key', 'InKadobonAge'),
                        ('value', resolve(data, 'cashback.validity')),
                        ('type', 'N'),
                    ],
                )
            )

        return serialize(queries)


class VAT(BaseSettingsSchema):
    """VAT percentages"""

    highvalue = fields.Float(
        load_default=21.0,
        dump_default=21.0,
        metadata={
            'description': 'The VAT high amount. This tax percentage is usually added '
            'to luxury items and clothing.'
        },
    )
    lowvalue = fields.Float(
        load_default=9.0,
        dump_default=9.0,
        metadata={
            'description': 'The VAT low amount. This tax percentage is usually added '
            'to food items and medicine.'
        },
    )
    zerovalue = fields.Float(
        load_default=0.0,
        dump_default=0.0,
        metadata={
            'description': 'The VAT zero amount. Used on items which should be '
            'charged no VAT such as for products and services that are already taxed '
            'in other countries or systems.'
        },
    )


class OrderTemplate(BaseSettingsSchema):
    """The configurable order template settings"""

    agentName = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'The name of the agent.'},
    )
    discountLine1 = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Show the first discount line of the payment terms or not. '
            '(this line includes discountTerm1 and '
            'discountPercentage1)'
        },
    )
    discountLine2 = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Show the second discount line of the payment terms or '
            'not. (this line includes discountTerm2 and discountPercentage2)'
        },
    )
    nettTerm = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Show the third line of the payment terms (nettTerm) or not'
        },
    )
    remarks = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Remarks on the order.'},
    )
    shippingCarrier = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the shippingCarrier or not.'},
    )

    fixDate = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the fixDate on the product or not.'},
    )
    reservationDate = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the reservationDate on the product or not.'},
    )
    productPhoto = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show product photos or not.'},
    )
    brand = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the brand of the product or not.'},
    )
    collection = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the collection of the product or not.'},
    )
    articleGroup = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the articleGroup of the product or not.'},
    )
    suggestedRetailPrice = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'description': 'Show the suggested retail price of the product or not.'
        },
    )
    colorDescription = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={'description': 'Show the color description of a SKU or not.'},
    )
    propertiesOnOrder = fields.List(
        fields.String,
        load_default=[],
        dump_default=[],
        metadata={
            'description': 'A list of the sku properties that should be shown on the '
            'sales order. Each string refers to an article group in the sku feed.'
        },
    )


class SalesCustomerFields(BaseSettingsSchema):
    """
    List of fields that controll the fields that are shown/editable for
    wholesale customers.
    """

    name = fields.Boolean(load_default=False, dump_default=False)
    legalName = fields.Boolean(load_default=False, dump_default=False)
    address = fields.Boolean(load_default=False, dump_default=False)
    zipcode = fields.Boolean(load_default=False, dump_default=False)
    city = fields.Boolean(load_default=False, dump_default=False)
    country = fields.Boolean(load_default=False, dump_default=False)
    telephone = fields.Boolean(load_default=False, dump_default=False)
    deliveryAddress = fields.Boolean(load_default=False, dump_default=False)
    deliveryZipcode = fields.Boolean(load_default=False, dump_default=False)
    deliveryCity = fields.Boolean(load_default=False, dump_default=False)
    deliveryCountry = fields.Boolean(load_default=False, dump_default=False)
    deliveryTelephone = fields.Boolean(load_default=False, dump_default=False)
    currency = fields.Boolean(load_default=False, dump_default=False)
    limit = fields.Boolean(load_default=False, dump_default=False)
    vatNumber = fields.Boolean(load_default=False, dump_default=False)
    cocNumber = fields.Boolean(load_default=False, dump_default=False)
    bankNumber = fields.Boolean(load_default=False, dump_default=False)
    email = fields.Boolean(load_default=False, dump_default=False)
    remarks = fields.Boolean(load_default=False, dump_default=False)
    discountPercentage1 = fields.Boolean(load_default=False, dump_default=False)
    discountPercentage2 = fields.Boolean(load_default=False, dump_default=False)
    discountTerm1 = fields.Boolean(load_default=False, dump_default=False)
    discountTerm2 = fields.Boolean(load_default=False, dump_default=False)
    language = fields.Boolean(load_default=False, dump_default=False)
    nettTerm = fields.Boolean(load_default=False, dump_default=False)
    preSaleDiscount = fields.Boolean(load_default=False, dump_default=False)
    region = fields.Boolean(load_default=False, dump_default=False)


class SalesSettings(BaseSettingsSchema):
    """The configurable sales application settings"""

    allowed_roles = ADMIN_MY_ROLES | {'sales-admin'}

    orderTemplate = Nested(
        OrderTemplate,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': allowed_roles,
            'description': 'Visual settings for the order templates used to change '
            'the look of the order template which is generated.',
        },
    )
    filterByProperties = fields.List(
        fields.String,
        load_default=list,
        dump_default=list,
        metadata={
            'roles': allowed_roles,
            'description': 'The properties which can be used during filtering '
            'products.',
        },
    )
    confirmationEmail = fields.List(
        fields.String,
        load_default=list,
        dump_default=list,
        metadata={
            'roles': allowed_roles,
            'description': 'Email addresses to send order emails.',
        },
    )
    hiddenFields = Nested(
        SalesCustomerFields,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': allowed_roles,
            'description': 'Wholesale customer fields that are hidden for '
            'registration or when viewing customers.',
        },
    )
    readOnlyFields = Nested(
        SalesCustomerFields,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': allowed_roles,
            'description': 'Wholesale customer fields that are read only for '
            'registration or when viewing customers.',
        },
    )
    paymentTermsViewOnly = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': allowed_roles,
            'description': 'If this is True, agents cannot change the order terms '
            'in the sales order summary',
        },
    )
    regions = fields.List(
        fields.String,
        load_default=list,
        dump_default=list,
        metadata={
            'can_delete': False,
            'roles': allowed_roles,
            'description': 'List of region codes',
        },
    )
    defaultReservationDate = LenientDateTimeField(
        metadata={
            'roles': allowed_roles,
            'description': 'Default date for reservation date, will have to be '
            'changed every season.',
        }
    )
    defaultFixDate = LenientDateTimeField(
        metadata={
            'roles': allowed_roles,
            'description': 'Default date for reservation date, will have to be '
            'changed every season.',
        }
    )
    allowAgentModifyReservationDate = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': allowed_roles,
            'description': 'If true agents can change reservation dates.',
        },
    )
    allowAgentModifyFixDate = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': allowed_roles,
            'description': 'If true agents can change fix dates.',
        },
    )
    imageRoot = fields.String(
        dump_default='',
        metadata={
            'roles': allowed_roles,
            'description': 'Base url for the product images',
        },
    )
    directDeliveryPackingList = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'roles': allowed_roles,
            'description': 'If this is True, when a sales order with direct '
            'delivery items is created, a packing list document is created '
            'automatically.',
        },
    )


def generate_regions_fp_query(regions, *common):
    query = [*common, ('key', 'gcRayons'), ('value', ','.join(regions)), ('type', 'M')]
    return serialize([('setsetting', query)])


def generate_modify_price_receivings_fp_query(settings, *common):
    query = [
        *common,
        ('key', 'llChangePricesReceiving'),
        ('type', 'L'),
        ('value', resolve(settings, 'allowModifyPriceReceivings')),
    ]
    return serialize([('setsetting', query)])


class CustomLabels(BaseSettingsSchema):
    # TODO: ask if this is ok, adds account-admin in addition to what was implemented
    # as privileged.
    allowed_roles = ADMIN_MY_ROLES
    customGroupBy = fields.String(
        metadata={'roles': allowed_roles, 'description': 'Custom group by'}
    )
    articleGroup1 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 1',
        }
    )
    articleGroup2 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 2',
        }
    )
    articleGroup3 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 3',
        }
    )
    articleGroup4 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 4',
        }
    )
    articleGroup5 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 5',
        }
    )
    articleGroup6 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 6',
        }
    )
    articleGroup7 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 7',
        }
    )
    articleGroup8 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 8',
        }
    )
    articleGroup9 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for article group 9',
        }
    )
    customerGroup1 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for customer group 1',
        }
    )
    customerGroup2 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for customer group 2',
        }
    )
    customerGroup3 = fields.String(
        metadata={
            'roles': allowed_roles,
            'description': 'Custom label for customer group 3',
        }
    )


class LogisticsSettings(BaseSettingsSchema):
    allowModifyPriceReceivings = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'description': 'Determines whether users can change prices during the '
            'receivings process'
        },
    )


class PickingSettings(BaseSettingsSchema):
    packageLabelPrintq = fields.String(
        metadata={
            'description': 'Print queue id for the print queue used for printing the '
            'labels that will go on the packages.'
        }
    )
    packingListPrintq = fields.String(
        metadata={
            'description': 'Print queue id for the print queue used for printing the '
            'packing list.'
        }
    )


class Settings(BaseSettingsSchema):
    """The configurable account settings"""

    logoUrl = Nested(
        Logo,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': set(),  # should be set by logo endpoints
            'description': 'Property maintained by /uploads/add-logo. Default value '
            'is empty object.',
        },
    )
    vat = Nested(
        VAT,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'The value-added tax (VAT) percentage used primarily in '
            'business to consumer transactions. VAT or goods and services tax (GST) '
            'is a popular way of implementing a consumption tax in Europe, Japan, and '
            'many other countries. Softwear supports three levels of VAT percentages '
            'known as high, low, and zero.',
        },
    )
    loyalty = Nested(
        Loyalty,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'Used by retail to store settings relating to the Softwear '
            'provided customer loyalty program.',
        },
    )
    sales = Nested(
        SalesSettings,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': ADMIN_MY_ROLES | {'sales-admin'},
            'can_delete': False,
            'description': 'Used by wholesale to store settings relating to the Sales '
            'application.',
        },
    )
    logistics = Nested(
        LogisticsSettings,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'Settings for the logistics app.',
        },
    )
    # TODO rename to picking & double check it merges with same key on user
    piking = Nested(
        PickingSettings,
        load_default=dict,
        dump_default=dict,
        metadata={'roles': ADMIN_ROLES, 'description': 'Settings for the picking app'},
    )
    shippingCarriers = fields.List(
        fields.String,
        load_default=list,
        dump_default=list,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'List of shipping carriers used by the tenant.',
        },
    )
    sendcloudApiToken = fields.String(
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'sendcloud api token for this tenant.',
        }
    )
    sendcloudApiSecret = fields.String(
        metadata={
            'roles': ADMIN_MY_ROLES,
            'description': 'sendcloud api secret for this tenant.',
        }
    )
    allowSalesOrderEditing = fields.Boolean(
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Allow SalesOrder editing',
        },
    )
    useNewPaymentRules = fields.Boolean(
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Switch POS to new style payment rules',
        },
    )
    currencies = Nested(
        Currency,
        many=True,
        load_default=list,
        dump_default=list,
        metadata={
            'roles': ADMIN_MY_ROLES,
            'can_delete': False,
            'description': 'List of currencies in use by the tenant',
        },
    )
    currency = fields.String(
        load_default='EUR',
        dump_default='EUR',
        validate=validate.Regexp(regex='^[A-Z]{3}$'),
        metadata={
            'description': 'The ISO 4217 currency code used by the tenant as its '
            'currency. Default: EUR',
            'pattern': '[A-Z]{3}',
        },
    )
    payNLToken = fields.String(
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Tenant wide token used for the pay.nl payment provider.',
        }
    )
    closingProcedure = fields.String(
        load_default='eos',
        dump_default='eos',
        validate=validate.OneOf(choices=['eod', 'eos', 'none'], error=BAD_CHOICE_MSG),
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Used by the POS to determine if a tenant should use the '
            'End of Day (EOD) or End of Shift (EOS) closing procedure. Can be none if '
            'a tenant does not want to use either.',
        },
    )
    uploadDirectory = fields.String(
        validate=validate.Length(min=21),
        load_default=uuid.uuid4().hex,
        metadata={
            'roles': set(),  # set by separate endpoint
            'description': 'A unique identifier used as a directory in the Softwear '
            'CDN for storing tenant specific photos and logos.',
        },
    )
    printLogoOnReceipt = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Used by the POS to determine if the logo of the client '
            'should be printed out on POS receipts.',
        },
    )
    roundTotalAmount5cent = fields.Boolean(
        load_default=True,
        dump_default=True,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Used by the POS to determine if change on cash '
            'transactions should be rounded to the nearest five cents. This setting '
            'is used in European countries that do not circulate 1 and 2 cent Euro '
            'coins.',
        },
    )
    customLabels = fields.Nested(
        CustomLabels,
        load_default=dict,
        dump_default=dict,
        metadata={
            'roles': {
                'sw-servicedesk',
                'sw-admin',
                'sw-consultant',
                'owner',
                'account-admin',
            },
            'description': 'Used by retail to store client specific values for generic '
            'labels.',
        },
    )
    fetchBarcodeFromLatestCollection = fields.Boolean(
        load_default=False,
        dump_default=False,
        metadata={
            'roles': ADMIN_ROLES,
            'description': 'Used to specify whether or not use LatestCollection to fetch barcode',
        },
    )

    @validates('currencies')
    def validate_currencies(self, value):
        """labels should be unique"""
        labels = [c.get('label') for c in value]
        validate_unique_list(labels)

    @post_dump
    def obfuscate(self, data, **kwargs):
        """obfuscate sensitive settings"""
        for setting in ['payNLToken', 'sendcloudApiToken', 'sendcloudApiSecret']:
            if data.get(setting):
                data[setting] = obfuscate(data[setting])
        return data


class Counters(BaseSettingsSchema):
    """Counters for the tenant"""

    posInstanceId = fields.Integer(
        validate=validate.Range(min=0),
        metadata={
            'description': 'This is an incremental number that denotes when a new '
            'browser session of the POS is started. This number is used in the '
            'printed receipt number as the middle digit (ie. '
            'warehouse-instanceId-receipt incremental number). Example. 51-1-100 is '
            'warehouse 51, with instance id 1 and receipt number 100.'
        },
    )
    salesOrder = fields.Integer(validate=validate.Range(min=0))
    packingList = fields.Integer(validate=validate.Range(min=0))
    invoice = fields.Integer(validate=validate.Range(min=0))

    @validates_schema
    def validate_counter(self, data, **kwargs):
        counters = self.context.get('old_counters', {})
        errors = []
        for key in ('invoice', 'packingList', 'salesOrder', 'posInstanceId'):
            if key in data and data[key] <= counters.get(key, 0):
                errors.append(key)
        if errors:
            raise ValidationError(
                {field: 'Counters must be incremented.' for field in errors}
            )


class Comment(BaseSettingsSchema):
    """A comment for use of Softwear Staff"""

    comment = fields.String(
        required=True, metadata={'description': 'The actual comment'}
    )
    date = fields.DateTime(
        required=True,
        metadata={'description': 'The date and time when the comment was added'},
    )
    username = fields.String(
        required=True,
        metadata={'description': 'The username of the user who added the comment'},
    )


class Tenant(BaseSettingsSchema):
    """
    Essentially one customer of ours. One tenant would be
    one store or one company using latest collection.
    """

    _id = fields.String(
        required=True,
        metadata={
            'description': 'The account number. Used as a primary identifier for a '
            'tenant account. Also known as the tenant id. Needs to beparsable to int'
        },
    )

    # in other schemas this is in the BaseSchema, but the BaseSchema also
    # includes the tenant_id field, which the tenant of course does not have.
    # modified can be dump_only
    created = fields.Dict(
        required=True,
        dump_only=True,
        metadata={'description': 'Created date & additional information'},
    )
    modified = fields.Dict(
        required=True,
        dump_only=True,
        metadata={'description': 'Modified date & additional information'},
    )
    active = fields.Boolean(
        load_default=True,
        metadata={
            'description': 'Used to set the account to either active or inactive. Is '
            'used by Finance when a tenant cancels its account.'
        },
    )
    name = fields.String(
        required=True,
        metadata={
            'description': "The tenant's common name. This can be the same as "
            'legal_name. No two tenants can have the same name.'
        },
    )
    legalname = fields.String(
        required=True,
        metadata={
            'description': "The tenant's legal name as stated in the articles of "
            'incorporation.'
        },
    )
    cocNumber = fields.String(
        metadata={'description': 'The chamber of commerce number for the tenant'}
    )
    vatNumber = fields.String(
        load_default='', metadata={'description': 'Tenant tax number.'}
    )
    bankAccountName = fields.String(
        metadata={'description': 'The name of the bank account holder.'}
    )
    bankAccountNumber = fields.String(
        metadata={
            'description': 'In Europe this is usually an IBAN, but in other countries '
            'this may vary in size and length.'
        }
    )
    bic = fields.String(
        metadata={
            'description': 'Bank Identifier Code is the SWIFT Address assigned to a '
            'bank in order to send automated payments quickly and accurately to the '
            'banks concerned. It uniquely identifies the name and country, (and '
            'sometimes the branch) of the bank involved. BICs are often called SWIFT '
            'Codes and can be either 8 or 11 characters long.'
        }
    )
    uuid = fields.UUID(
        dump_only=True, metadata={'description': 'Universal unique identifier.'}
    )
    website = fields.String(metadata={'description': "The company's website URL."})
    dimension4 = fields.String(
        metadata={
            'description': 'An additional setting mostly used for FoxPro to determine '
            'if the second set of sizes should be used for cup sizes '
            'or jean lengths'
        },
    )
    gln = fields.String(
        metadata={
            'description': 'Global Location Number (GLN) can be used by companies to '
            'identify their locations, for example, a store, warehouse. The GLN can '
            'also be used to identify an organisation as a corporate entity.'
        },
    )
    comments = Nested(
        Comment, many=True, metadata={'description': 'Comments added by Softwear staff'}
    )
    owners = fields.List(
        ObjectIdField,
        load_default=list,
        metadata={
            'description': 'A list of owners of the tenant. Uses the _id of the user '
            'accounts of the owners'
        },
    )
    addresses = Nested(
        Address,
        many=True,
        validate=contains_one_primary,
        load_default=list,
        metadata={'description': 'Tenant address information'},
    )
    contacts = Nested(
        Contact,
        many=True,
        validate=contains_one_primary,
        load_default=list,
        metadata={'description': 'Tenant contact information'},
    )
    applications = fields.List(
        fields.String,
        load_default=list,
        metadata={
            'description': 'The allowed applications (modules) that a Softwear client '
            'can use. These are usually paid modules such as the POS '
            'or Inventory.'
        },
    )
    settings = Nested(
        Settings, metadata={'description': 'The account settings of the tenant.'}
    )
    retail = fields.Boolean(
        load_default=False, metadata={'description': 'True if the tenant is a retailer'}
    )
    wholesale = fields.Boolean(
        load_default=False,
        metadata={'description': 'True if the tenant is a wholesaler'},
    )
    countryCode = fields.String(
        required=True,
        validate=validate.OneOf(COUNTRIES.keys(), error=BAD_CHOICE_MSG),
        metadata={
            'description': 'The country code of the tenant, important for changes in '
            'VAT etc. examples: NL, DE.'
        },
    )
    counters = Nested(Counters)
    jiraEpicLink = fields.URL(
        metadata={'description': 'The url to a JIRA epic associated to the tenant'}
    )
    properties = Nested(
        Property,
        many=True,
        load_default=list,
        metadata={'description': 'Additional key-value pair items for the tenant.'},
    )

    @validates('_id')
    def validate_id(self, value):
        if 'db' in self.context:
            if self.context['db'].tenants.count({'_id': value}):
                raise ValidationError('Tenant id {} is already in use.'.format(value))

    @validates('name')
    def validate_name(self, value):
        if 'db' in self.context:
            if self.context['db'].tenants.count({'name': value}):
                raise ValidationError('Name {} is already in use.'.format(value))

    @validates('bic')
    def validate_bic(self, value):
        if len(value) not in (8, 11):
            raise ValidationError('Bic should be either 8 or 11 characters long')

    @validates('applications')
    def check_allowed_applications(self, value):
        if 'allowed_applications' in self.context:
            applications = set(value)
            allowed_applications = set(self.context['allowed_applications'])
            if not applications.issubset(allowed_applications):
                raise ValidationError(
                    'Unknown application(s): {}'.format(
                        applications - allowed_applications
                    )
                )
