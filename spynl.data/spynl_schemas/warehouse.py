from bson.objectid import InvalidId, ObjectId
from marshmallow import ValidationError, fields, post_load, validates, validates_schema

from spynl_schemas.fields import Nested
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.shared_schemas import Address, BaseSchema
from spynl_schemas.utils import contains_one_primary, validate_warehouse_id


class Warehouse(BaseSchema):
    """The schema for a location which can be a warehouse or a retail store"""

    _id = fields.String(
        metadata={
            'description': '_id for the location, should be an ObjectId for new '
            "locations, but existing locations can have string _id's"
        }
    )
    name = fields.String(
        required=True, metadata={'description': 'Human readable name of the location.'}
    )
    ean = fields.String(
        allow_none=True,
        load_default='',
        metadata={'description': 'GLN for the location.'},
    )
    wh = fields.String(
        required=True,
        validate=validate_warehouse_id,
        metadata={'description': 'Legacy Id of 2 or 3 digits.'},
    )
    fullname = fields.String(
        allow_none=True,
        load_default='',
        metadata={'description': 'Location full name.'},
    )
    email = fields.String(
        metadata={'description': 'Email address associated with the location.'}
    )
    addresses = Nested(
        Address,
        many=True,
        validate=contains_one_primary,
        load_default=list,
        metadata={'description': 'Physical address of the location.'},
    )
    sendcloudSenderAddressId = fields.Int(
        metadata={
            'description': "The sender address id for this location in the tenant's "
            'Sendcloud account.'
        }
    )

    @validates_schema
    def validate_uniqueness(self, data, **kwargs):
        if (
            'wh' not in data
            or 'db' not in self.context
            or 'tenant_id' not in self.context
        ):
            return

        try:
            _id = ObjectId(data['_id'])
        except InvalidId:
            _id = data['_id']
        except KeyError:
            _id = None

        warehouse = self.context['db'].warehouses.count(
            {
                '_id': {'$ne': _id},
                'wh': data['wh'],
                'tenant_id': self.context['tenant_id'],
            }
        )
        if warehouse:
            raise ValidationError('This wh number already exists for this tenant', 'wh')

    @validates('_id')
    def validate_id(self, value):
        try:
            value = ObjectId(value)
        except InvalidId:
            pass
        # new warehouses should have an ObjectId as _id
        if (
            'db' in self.context
            and not self.context['db'].warehouses.count({'_id': value})
            and not isinstance(value, ObjectId)
        ):
            raise ValidationError('Not a valid ObjectId', '_id')

    @validates('email')
    def validate_email(self, value):
        # We only validate in case it's not an empty string.
        if value:
            fields.Email()._validate(value)

    @post_load
    def cast_to_objectid(self, data, **kwargs):
        try:
            data['_id'] = ObjectId(data['_id'])
        except (InvalidId, KeyError):
            pass
        return data

    @staticmethod
    def generate_fpqueries(warehouse, *common):
        warehouse['inactive'] = not warehouse['active']
        query = [
            *common,
            ('locationid', resolve(warehouse, 'wh')),
            ('name', resolve(warehouse, 'name')),
            ('gln', resolve(warehouse, 'ean')),
            ('email', resolve(warehouse, 'email')),
            ('inactive', resolve(warehouse, 'inactive')),
        ]

        for address in warehouse['addresses']:
            if address['primary']:
                query.extend(
                    [
                        ('street', resolve(address, 'street')),
                        ('housenum', resolve(address, 'houseno')),
                        ('houseadd', resolve(address, 'houseadd')),
                        ('zipcode', resolve(address, 'zipcode')),
                        ('city', resolve(address, 'city')),
                        ('country', resolve(address, 'country')),
                        ('telephone', resolve(address, 'phone')),
                        ('fax', resolve(address, 'fax')),
                    ]
                )

                break

        return serialize([('setwarehouse', query)])
