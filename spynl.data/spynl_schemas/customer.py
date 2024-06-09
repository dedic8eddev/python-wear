import datetime
import re
import uuid

from marshmallow import ValidationError, fields, post_load, pre_load

from spynl_schemas.fields import Nested
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.shared_schemas import Address, BaseSchema, Contact, Property
from spynl_schemas.utils import contains_one_primary


class RetailCustomerSchema(BaseSchema):
    """A consumer who purchases in stores."""

    _id = fields.UUID(load_default=uuid.uuid4)
    addresses = Nested(Address, many=True, required=True, validate=contains_one_primary)
    contacts = Nested(Contact, many=True, required=True, validate=contains_one_primary)
    properties = Nested(Property, many=True)
    newsletter_subscribe = fields.Boolean(load_default=False)
    first_name = fields.String()
    middle_name = fields.String()
    last_name = fields.String(required=True)
    points = fields.Int(load_default=0)
    dob = fields.String()
    loyalty_no = fields.String()
    cust_id = fields.String()
    origin = fields.String()
    currency = fields.String()
    lang = fields.String()
    title = fields.String()
    customer_zipcode = fields.String()
    customer_city = fields.String()
    customer_street = fields.String()
    company = fields.String()
    remarks = fields.String()
    agent_id = fields.String()

    class Meta(BaseSchema.Meta):
        additional = ('company', 'remarks', 'agent_id')

    @post_load
    def set_dob(self, data, **kwargs):
        if 'dob' in data:
            dob = ''
            for fmt in ('%Y%m%d', '%Y-%m-%d', '%d-%m-%Y'):
                try:
                    dob = datetime.datetime.strptime(data['dob'].strip(), fmt)
                    dob = datetime.datetime.strftime(dob, '%Y-%m-%d')
                except ValueError:
                    pass
            data['dob'] = dob
        return data

    @staticmethod
    def generate_fpqueries(data, *common):
        setclient = [
            *common,
            ('uuid', data['_id']),
            ('custnum', resolve(data, 'cust_id')),
            ('loyaltynr', resolve(data, 'loyalty_no')),
            ('newsletter', resolve(data, 'newsletter_subscribe')),
            ('title', resolve(data, 'title')),
            ('firstname', resolve(data, 'first_name')),
            ('middlename', resolve(data, 'middle_name')),
            ('lastname', resolve(data, 'last_name')),
            ('warehouse', resolve(data, 'origin')),
            (
                'remarks',
                re.sub(r"[&\/\\#()$~%'\"?<>{}\^]", '', resolve(data, 'remarks')),
            ),
        ]

        born = data.get('dob', '')
        try:
            born = datetime.datetime.strptime(born, '%Y-%m-%d').strftime('%d-%m-%Y')
        except ValueError:
            pass
        setclient.append(('born', born))

        for contact in data['contacts']:
            if contact['primary']:
                setclient.extend(
                    [
                        ('email', resolve(contact, 'email')),
                        ('fax', resolve(contact, 'mobile')),
                        ('telephone', resolve(contact, 'phone')),
                    ]
                )
                break

        for address in data['addresses']:
            if address['primary']:
                setclient.extend(
                    [
                        ('street', resolve(address, 'street')),
                        ('housenum', resolve(address, 'houseno')),
                        ('houseadd', resolve(address, 'houseadd')),
                        ('zipcode', resolve(address, 'zipcode')),
                        ('city', resolve(address, 'city')),
                        ('country', resolve(address, 'country')),
                    ]
                )
                break

        setclient.extend(
            [
                ('zgrp' + prop['name'], prop['value'])
                for prop in data.get('properties', [])
            ]
        )

        return serialize(
            [('setclient', setclient)],
            whitelist=[('setclient', 'born')],
            pass_empty=True,
        )

    @post_load
    def set_top_level_fields(self, data, **kwargs):
        if 'addresses' in data:
            if len(data['addresses']) > 0:
                if 'zipcode' in data['addresses'][0]:
                    data['customer_zipcode'] = data['addresses'][0]['zipcode']
                if 'city' in data['addresses'][0]:
                    data['customer_city'] = data['addresses'][0]['city'].upper()
                if 'street' in data['addresses'][0]:
                    data['customer_street'] = data['addresses'][0]['street'].upper()
        return data


class SyncRetailCustomerSchema(RetailCustomerSchema):
    """A consumer who purchases in stores."""

    _id = fields.UUID(load_default=uuid.uuid4, data_key='uuid')
    last_name = fields.String(data_key='name')
    dob = fields.String(data_key='birthDate')
    loyalty_no = fields.String(data_key='clientNumber')
    cust_id = fields.String(data_key='id')
    lang = fields.String(data_key='language')
    balance = fields.Float(load_default=0)
    creditLimit = fields.Float(load_default=0)
    middle_name = fields.String(data_key='middleName')
    first_name = fields.String(data_key='firstName')
    tenant_id = fields.List(fields.String, required=True)
    properties = Nested(Property, many=True, data_key='groups')

    class Meta(RetailCustomerSchema.Meta):
        additional = ('company', 'remarks', 'agent_id')

    @post_load
    def strip_cust_id(self, data, **kwargs):
        if 'cust_id' in data:
            data['cust_id'] = data['cust_id'].strip()
        return data

    @post_load
    def set_points(self, data, **kwargs):
        data['points'] = data.pop('balance', 0) - data.pop('creditLimit', 0)
        return data

    @pre_load
    def set_active(self, data, **kwargs):
        """Determine active from fields provided by FoxPro."""
        active = not (data.pop('blocked', False) or data.pop('inactive', False))
        data.setdefault('active', active)
        return data

    @pre_load
    def set_addresses_and_contacts(self, data, **kwargs):
        """Put the address and contact fields in nested objects.

        FoxPro provided a dump with flat objects. We pick out the fields and
        address fields and put them in an object under 'address'. We pick out
        the delivery address fields and put them in an object under
        'deliveryAddress'.
        """

        address_fields = [
            ('address', 'street'),
            ('houseNumber', 'houseno'),
            ('houseNumberAddition', 'houseadd'),
            ('zipcode', 'zipcode'),
            ('city', 'city'),
            ('country', 'country'),
        ]

        contact_fields = [
            ('telephone', 'phone'),
            ('name', 'name'),
            ('email', 'email'),
            ('fax', 'mobile'),
        ]

        updated = {**data, 'addresses': [{}], 'contacts': [{}]}

        for data_key, key in address_fields:
            updated['addresses'][0][key] = data.get(data_key, '')
        updated['addresses'][0]['primary'] = True

        for data_key, key in contact_fields:
            updated['contacts'][0][key] = data.get(data_key, '')
        updated['contacts'][0]['primary'] = True

        if 'email' in updated['contacts'][0]:
            try:
                fields.Email()._validate(updated['contacts'][0]['email'])
            except ValidationError:
                updated['contacts'][0].pop('email')

        return updated
