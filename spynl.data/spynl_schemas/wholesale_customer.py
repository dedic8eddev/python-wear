import uuid

from marshmallow import ValidationError, fields, post_load, pre_load, validates_schema

from spynl_schemas.fields import Nested, ObjectIdField
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.shared_schemas import BaseSchema, Property, Schema


class Address(Schema):
    """An address schema particular to wholesale customers."""

    address = fields.String()
    zipcode = fields.String()
    city = fields.String()
    country = fields.String()
    telephone = fields.String()
    fax = fields.String()
    houseno = fields.String()
    houseadd = fields.String()


class WholesaleCustomerSchema(BaseSchema):
    _id = fields.UUID(load_default=uuid.uuid4)
    cust_id = fields.String()

    blocked = fields.Boolean(load_default=False)
    points = fields.Float()

    balance = fields.Int()
    preSaleDiscount = fields.Float()
    creditSqueeze = fields.Int()
    shippingCost = fields.Int()
    creditLimit = fields.Int()
    shippingMethod = fields.Int()
    markup = fields.Int()

    paymentMethod = fields.Float()
    nettTerm = fields.Float()
    discountTerm1 = fields.Float()
    discountTerm2 = fields.Float()
    discountPercentage1 = fields.Float()
    discountPercentage2 = fields.Float()
    paymentTerms = fields.String(
        metadata={
            'description': 'Identification string of the payment terms that apply for '
            'this customer.'
        }
    )

    cashOnDelivery = fields.Boolean()
    moneyOrder = fields.Boolean()
    copyDocumentsToHeadQuarter = fields.Boolean()

    name = fields.String()
    legalName = fields.String()
    type = fields.String()
    agent = fields.String()
    carrier = fields.String()
    carrierRemark = fields.String()

    address = Nested(Address)
    deliveryAddress = Nested(Address)

    remarks = fields.String()
    # TODO: depending on migration, we could validate that this is actually
    # the label of one of the currencies.
    currency = fields.String(
        metadata={
            'description': "Label of one of the currencies in the tenant's "
            'settings.sales.currencies'
        }
    )
    language = fields.String(
        metadata={
            'description': 'Language of the wholesale customer, two letter code or '
            'empty string.'
        }
    )
    retailServiceOrganisation = fields.String()
    headQuarterNumber = fields.String()
    retailServiceOrganisationMemberNumber = fields.String()
    vatNumber = fields.String()
    clientNumber = fields.String()
    chamberOfCommerceNumber = fields.String()
    bankAccountNumber2 = fields.String()
    bankAccountNumber = fields.String()
    bankName = fields.String()
    gln = fields.String()
    email = fields.Email()
    region = fields.String()

    agentEmail = fields.String()
    agentId = ObjectIdField()

    properties = Nested(Property, many=True)

    customer_zipcode = fields.String()
    customer_city = fields.String()
    customer_street = fields.String()
    employee = fields.Boolean(load_default=False)

    @pre_load
    def handle_email(self, data, **kwargs):
        """remove empty emails."""
        if data.get('email') == '':
            data.pop('email')
        return data

    @post_load
    def set_top_level_fields(self, data, **kwargs):
        if 'address' in data:
            if 'zipcode' in data['address']:
                data['customer_zipcode'] = data['address']['zipcode']
            if 'city' in data['address']:
                data['customer_city'] = data['address']['city'].upper()
            if 'address' in data['address']:
                data['customer_street'] = data['address']['address'].upper()
        return data

    @validates_schema
    def validate_region(self, data, **kwargs):
        if not data.get('region') or 'db' not in self.context:
            return

        tenant = self.context['db'].tenants.find_one({'_id': data['tenant_id'][0]})
        regions = tenant.get('settings', {}).get('sales', {}).get('regions')
        if regions and data['region'] not in regions:
            raise ValidationError(
                'Region is unavailable on the active tenant', 'region'
            )

    @staticmethod
    def generate_fpqueries(customer, *common):
        query = [
            *common,
            ('uuid', resolve(customer, '_id')),
            ('active', resolve(customer, 'active')),
            ('blocked', resolve(customer, 'blocked')),
            ('custnum', resolve(customer, 'cust_id')),
            ('lastname', resolve(customer, 'name')),
            ('legalname', resolve(customer, 'legalName')),
            ('city', resolve(customer, 'address.city')),
            ('street', resolve(customer, 'address.address')),
            ('country', resolve(customer, 'address.country')),
            ('sales', resolve(customer, 'agent')),
            ('zipcode', resolve(customer, 'address.zipcode')),
            ('email', resolve(customer, 'email')),
            ('limiet', resolve(customer, 'creditLimit')),
            ('cocnr', resolve(customer, 'chamberOfCommerceNumber')),
            ('vatnr', resolve(customer, 'vatNumber')),
            ('banknr', resolve(customer, 'bankAccountNumber')),
            ('telephone', resolve(customer, 'address.telephone')),
            ('currency', resolve(customer, 'currency')),
            ('nettTerm', resolve(customer, 'nettTerm')),
            ('discountTerm1', resolve(customer, 'discountTerm1')),
            ('discountTerm2', resolve(customer, 'discountTerm2')),
            ('discountPercentage1', resolve(customer, 'discountPercentage1')),
            ('discountPercentage2', resolve(customer, 'discountPercentage2')),
            ('preSaleDiscount', resolve(customer, 'preSaleDiscount')),
            ('VOKORT', resolve(customer, 'preSaleDiscount')),
            ('creditSqueeze', resolve(customer, 'creditSqueeze')),
            ('cashOnDelivery', resolve(customer, 'cashOnDelivery')),
            ('moneyOrder', resolve(customer, 'moneyOrder')),
            ('deliveryaddress', resolve(customer, 'deliveryAddress.address')),
            ('deliveryzipcode', resolve(customer, 'deliveryAddress.zipcode')),
            ('deliverycity', resolve(customer, 'deliveryAddress.city')),
            ('deliverycountry', resolve(customer, 'deliveryAddress.country')),
            ('deliverytelephone', resolve(customer, 'deliveryAddress.telephone')),
            ('rayon', resolve(customer, 'region')),
            ('remarks', resolve(customer, 'remarks')),
            ('languagecode', resolve(customer, 'language')),
        ]

        return serialize([('setclient', query)])


class SyncWholesaleCustomerSchema(WholesaleCustomerSchema):
    """
    Like WholesaleCustomerSchema but for foxpro database.

    In foxpro the _id is replaced with the uuid name and the tenant_id is a string
    instead of list of strings.
    """

    _id = fields.UUID(load_default=uuid.uuid4, data_key='uuid')
    cust_id = fields.String(data_key='id')
    gln = fields.String(data_key='GLN')
    properties = Nested(Property, many=True, data_key='groups')

    @post_load
    def set_agent_id(self, data, **kwargs):
        if not ('db' in self.context and 'agentEmail' in data):
            return data

        agent = self.context['db'].users.find_one(
            {'email': data['agentEmail']}, {'_id': 1}
        )
        if agent:
            data['agentId'] = agent['_id']
        return data

    @pre_load
    def remove_invalid_email(self, data, **kwargs):
        if 'email' not in data:
            return data
        try:
            fields.Email()._validate(data['email'])
        except ValidationError:
            data.pop('email')
        return data

    @pre_load
    def set_addressess(self, data, **kwargs):
        """Put the address fields in nested objects.

        FoxPro provided a dump with flat objects. We pick out the normal
        address fields and put them in an object under 'address'. We pick out
        the delivery address fields and put them in an object under
        'deliveryAddress'.
        """

        fields = [
            'address',
            'houseNumber',
            'houseNumberAddition',
            'zipcode',
            'city',
            'country',
            'telephone',
            'fax',
            'deliveryAddress',
            'deliveryZipcode',
            'deliveryCity',
            'deliveryCountry',
            'deliveryTelephone',
            'deliveryFax',
        ]

        updated = {**data, 'address': {}, 'deliveryAddress': {}}

        for key in fields & data.keys():
            if key.startswith('delivery'):
                updated['deliveryAddress'][key.lower().replace('delivery', '')] = data[
                    key
                ]
            else:
                updated['address'][key] = data[key]
        return updated

    @pre_load
    def set_active(self, data, **kwargs):
        """Determine active from fields provided by FoxPro."""
        active = not data.pop('inactive', False)
        data.setdefault('active', active)
        return data
