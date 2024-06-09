import re
import uuid
from itertools import groupby

from babel import numbers
from bson.objectid import InvalidId, ObjectId
from marshmallow import EXCLUDE
from marshmallow import Schema as MarshmallowSchema
from marshmallow import (
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates,
    validates_schema,
)

from spynl_schemas.fields import Nested
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.utils import (
    BAD_CHOICE_MSG,
    cast_percentage,
    validate_unique_list,
    validate_warehouse_id,
)


class Schema(MarshmallowSchema):
    """base class for shared meta settings"""

    class Meta:
        ordered = True
        unknown = EXCLUDE


class TimestampUser(Schema):
    username = fields.String(
        metadata={
            'description': 'The username of the user who triggered the creation/edit '
            'of this record.'
        }
    )
    _id = fields.String(
        metadata={
            'description': 'The _id of the user who triggered the creation/edit of '
            'this record.'
        }
    )


# TODO: actually use this for BaseSchema (and fix errors that occur)
class Timestamp(Schema):
    action = fields.String(metadata={'description': 'The source of the record'})
    date = fields.DateTime(metadata={'description': 'Timestamp of creation/edit'})
    user = Nested(
        TimestampUser,
        metadata={
            'description': 'The user who triggered the creation/edit of this record'
        },
    )


class BaseSchema(Schema):
    # if you change created and modified, please also change it in the Tenant
    # schema
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
    # For collections that have public documents, we should allow None
    # TODO: add validation for minimum 1 length.
    tenant_id = fields.List(
        fields.String,
        required=True,
        validate=validate_unique_list,
        metadata={
            'description': "An array of tenant_id's that denote the tenants of the "
            'document. For a user document, the first tenant in the list is treated '
            'as the default tenant.',
            'UniqueItems': True,
        },
    )

    active = fields.Boolean(
        load_default=True,
        metadata={
            'description': 'Determines whether the document is considered active or '
            'not.'
        },
    )

    @pre_load
    def set_tenant(self, data, **kwargs):
        if 'tenant_id' in self.context:
            data['tenant_id'] = [self.context['tenant_id']]
        return data

    @validates('tenant_id')
    def check_if_tenants_exists(self, value):
        """
        Check if all the tenants in the tenant_id list exist.
        A list of allowed tenants can be provided (for e.g. account
        provisioning, where new tenants and other documents are added to the
        db at the same time). Existing tenants are also added to the allowed
        tenants, so less db calls are needed when multiple documents are
        checked at the same time.
        """
        if self.context.get('check_if_tenants_exist') and 'db' in self.context:
            if not self.context.get('allowed_tenants'):
                self.context['allowed_tenants'] = set()

            query = {
                '$or': [
                    {'_id': i}
                    for i in value
                    if i not in self.context['allowed_tenants']
                ]
            }
            if query['$or']:
                existing = list(self.context['db'].tenants.find(query, {'_id': 1}))
                if not len(existing) == len(query['$or']):
                    raise ValidationError(
                        'Non-existing tenant(s): {}'.format(
                            ', '.join(
                                i['_id'] for i in query['$or'] if i not in existing
                            )
                        )
                    )
                else:
                    self.context['allowed_tenants'].update(value)


class Property(Schema):
    name = fields.String(
        required=True, metadata={'description': 'The key of the property.'}
    )
    value = fields.String(
        required=True, metadata={'description': 'The value of the property.'}
    )


class BaseSkuSchema(Schema):
    size = fields.String(required=True, metadata={'description': 'Sku size.'})
    sizeIndex = fields.Integer(metadata={'description': 'Sku size index.'})
    color = fields.String(
        required=True,
        metadata={
            'description': 'Human readable color. This color is often populated '
            'automatically by putting in the colorSupplier, but it can be changed to '
            'suit the needs of the retailer/wholesaler. In practice, depending on '
            'where data is coming from and what context, either this field is used, '
            'or both the colorCode and colorDescription.'
        },
    )
    qty = fields.Int(
        metadata={'description': 'Number of items.'},
        load_default=0,
    )
    barcode = fields.String(
        required=True, metadata={'description': 'Barcode of the sku.'}
    )
    colorCode = fields.String(
        dump_default='',
        metadata={'description': 'Concatenation of mainColorCode and subColorCode.'},
    )
    colorDescription = fields.String(
        dump_default='',
        metadata={
            'description': 'Concatenation of mainColorDescription and '
            'subColorDescription.'
        },
    )
    mainColorCode = fields.String(metadata={'description': 'Code of the main color.'})
    mainColorDescription = fields.String(
        metadata={
            'description': 'Human readable description corresponding to the main '
            'color code.'
        }
    )
    subColorCode = fields.String(metadata={'description': 'Code of the sub color.'})
    subColorDescription = fields.String(
        metadata={
            'description': 'Human readable description corresponding to the sub color '
            'code.'
        }
    )
    colorSupplier = fields.String(
        metadata={'description': 'Human readable color used by the supplier.'}
    )
    colorCodeSupplier = fields.String()
    colorFamily = fields.String(
        metadata={
            'description': 'The color family is the generic name for a specific '
            'color. For example Burnt sienna" and "Deep saffron" could have the '
            'colorfamily of "orange"'
        }
    )
    remarks = fields.String(
        metadata={
            'description': 'A description of the sku, will mostly be the same for '
            'skus with the same color code but different sizes'
        }
    )
    # Used only in sales orders:
    salesOrder = fields.UUID(
        metadata={
            'description': 'Refers back to original sales order (e.g. when part of a '
            'sales order is converted into a packing list when it contains items for '
            'direct delivery).'
        }
    )
    # Used only in receivings:
    purchaseOrder = fields.UUID(
        metadata={'description': 'Refers back to the purchase order.'}
    )


class ProductSchema(Schema):
    articleCode = fields.String(required=True)
    articleCodeSupplier = fields.String()
    articleGroup = fields.String(dump_default='')
    articleDescription = fields.String(dump_default='')
    supplierName = fields.String()
    brand = fields.String(dump_default='')
    collection = fields.String()
    season = fields.String()
    year = fields.String()
    skus = Nested(BaseSkuSchema, many=True, required=True)
    price = fields.Float(
        required=True,
        metadata={'description': "Price in the seller's (tenant's) currency"},
    )
    suggestedRetailPrice = fields.Float(
        required=True,
        metadata={'description': "Suggested retail price in the tenant's currency"},
    )
    valuePrice = fields.Float(
        metadata={
            'description': 'The full price needed for the product to land in the '
            'warehouse (buyPrice + shipping costs + duty fees etc). This is also the '
            'price used to determine the value of the stock. The same product will '
            'have a different valuePrice for a wholesaler than for a retailer.'
        }
    )
    buyPrice = fields.Float(
        metadata={
            'description': 'The price that that was paid for the product. In '
            'receivings this is the price that the retailer paid the '
            'wholesaler.'
        }
    )
    cbs = fields.String(
        metadata={
            'description': 'Central Bureau of Statistics code used for international '
            'trade'
        }
    )
    sizes = fields.List(
        fields.String,
        dump_default=list,
        metadata={
            'description': 'List of available sizes, ordered as they should appear. '
            'This is used to make sure that e.g. both S M L and 40 42 44 appear in the '
            'correct order in tables etc.'
        },
    )
    properties = Nested(
        Property,
        many=True,
        dump_default=list,
        metadata={
            'description': 'Additional properties (groups) to be added to the pdf.'
        },
    )
    warehouseLocation = fields.String(
        metadata={'description': 'Physical location of the sku in the warehouse.'}
    )

    @post_load
    def remove_zero_qty_items(self, data, **kwargs):
        data['skus'] = [sku for sku in data['skus'] if sku['qty']]
        return data

    @classmethod
    def convert_properties_to_dict(cls, product):
        if 'properties' not in product:
            return
        product['properties'] = {
            item['name']: item['value'] for item in product['properties']
        }

    @classmethod
    def generate_sku_table(cls, product, price_key='price', row_color_definition=None):
        """
        Generate the data for the sku table.
        price: the localized price
        available_sizes: available sizes in order they should appear in the table
        """
        sku_table = {
            'available_sizes': product.get('sizes', []),
            'totalPrice': 0,
            'totalQuantity': 0,
            'skuRows': [],
        }
        sku_table['sizeTotals'] = {key: 0 for key in sku_table['available_sizes']}

        def get_row_color(sku):
            return sku.get('colorFamily', '') + sku.get('subColorDescription', '')

        if not row_color_definition:
            row_color_definition = get_row_color

        data = sorted([sku for sku in product['skus']], key=row_color_definition)
        for color_id, skus in groupby(data, row_color_definition):
            skus = list(skus)
            row = {
                'remarks': skus[0].get('remarks', ''),
                'totalPrice': 0,
                'totalQuantity': 0,
                'price': product.get(price_key),
            }
            for key in (
                'colorSupplier',
                'colorCodeSupplier',
                'colorFamily',
                'colorCode',
                'colorDescription',
                'subColorDescription',
            ):
                if skus[0].get(key) and not re.match(r'^\*\*', skus[0][key]):
                    row[key] = skus[0][key]
            row['quantities'] = {key: 0 for key in sku_table['available_sizes']}
            for sku in skus:
                # This should not happen, but it does from time to time:
                if sku['size'] not in sku_table['available_sizes']:
                    sku_table['available_sizes'].append(sku['size'])
                    sku_table['sizeTotals'][sku['size']] = 0
                row['quantities'][sku['size']] = sku['qty']
                sku_table['sizeTotals'][sku['size']] += sku['qty']
                row['totalQuantity'] += sku['qty']

            if row['price'] is not None:
                row['totalPrice'] = row['totalQuantity'] * row['price']
            sku_table['skuRows'].append(row)
            sku_table['totalQuantity'] += row['totalQuantity']
            sku_table['totalPrice'] += row['totalPrice']

        product['skuTable'] = sku_table


class SkuSchema(ProductSchema, BaseSkuSchema):
    @post_load
    def remove_zero_qty_items(self, data, **kwargs):
        """overwrite unneeded function"""
        return data

    class Meta(Schema.Meta):
        exclude = ('skus',)


class Address(Schema):
    """A schema for all addresses"""

    street = fields.String(
        required=True,
        metadata={
            'description': 'First line of street directions, should in principal only '
            'contain the street, but will sometimes also include the houseno. In that '
            'case, houseno is most likely empty, so street + houseno can be safely '
            'used.'
        },
    )
    street2 = fields.String(
        metadata={'description': 'Second line of street directions'}
    )
    houseno = fields.String(required=True, metadata={'description': 'House number'})
    houseadd = fields.String(metadata={'description': 'House number suffix'})
    zipcode = fields.String(required=True, metadata={'description': 'Zip code'})
    city = fields.String(required=True, metadata={'description': 'City name'})
    country = fields.String(
        required=True, metadata={'description': 'Country name. Language non-specified'}
    )

    fax = fields.String(metadata={'description': 'Fax number. Format non-specified'})
    phone = fields.String(
        metadata={'description': 'Phone number. Format non-specified'}
    )

    primary = fields.Boolean(
        required=True, metadata={'description': "'true' if this is the primary address"}
    )

    type = fields.String(
        load_default='billing',
        validate=validate.OneOf(
            choices=[
                'main',
                'headquarters',
                'warehouse',
                'store',
                'office',
                'home',
                'billing',
                'other',
                '',
                'delivery',
            ],
            error=BAD_CHOICE_MSG,
        ),
        metadata={
            'description': 'Address type. Describes the application of the value. '
            'Allowed values are: main, headquarters, warehouse, store, office, home, '
            'billing, other'
        },
    )

    company = fields.String(
        metadata={'description': 'Usually empty string, meaning unclear'}
    )

    @post_load
    def strip_postcode(self, data, **kwargs):
        if 'zipcode' in data:
            data['zipcode'] = re.sub(r'\s+', '', data['zipcode'])
        return data

    @post_load
    def uppercase(self, data, **kwargs):
        for key in ['houseadd', 'zipcode']:
            if key in data:
                data[key] = data[key].upper()
        return data


class Contact(Schema):
    """Email and phone contacts"""

    type = fields.String(
        validate=validate.OneOf(
            choices=['private', 'work', 'other', ''], error=BAD_CHOICE_MSG
        ),
        load_default='',
        metadata={
            'description': 'The type of contact, can be private or work contact '
            'information.'
        },
    )
    primary = fields.Boolean(
        required=True, metadata={'description': "'true' if this is the primary contact"}
    )
    name = fields.String(metadata={'description': 'The name of the contact.'})
    email = fields.String(metadata={'description': 'The email address of the contact.'})
    phone = fields.String(
        metadata={'description': 'The landline phone number for the contact.'}
    )
    mobile = fields.String(
        metadata={'description': 'The mobile phone number for the contact.'}
    )

    @validates('email')
    def validate_email(self, value):
        """Validate email except if it has empty string."""
        if value != '':
            validate.Email()(value)


class BaseSettingsSchema(Schema):
    @validates_schema
    def validate_roles(self, data, **kwargs):
        if 'user_roles' not in self.context:
            return

        unauthorized_fields = []
        user_roles = set(self.context['user_roles'])

        for fieldname, field in self.declared_fields.items():
            if fieldname not in data or 'roles' not in field.metadata:
                continue
            if not user_roles & field.metadata['roles']:
                unauthorized_fields.append(fieldname)

        if unauthorized_fields:
            raise ValidationError(
                {
                    field: 'You do not have rights to edit this setting'
                    for field in unauthorized_fields
                }
            )


class Currency(Schema):
    code = fields.String(
        metadata={'description': 'ISO code that is recognizable by babel'}
    )
    description = fields.String(
        metadata={'description': 'Human readable description of the currency'}
    )
    label = fields.String(
        required=True,
        validate=validate.Length(min=1),
        metadata={
            'description': 'Label for the currency, needs to be unique for the tenant.'
        },
    )
    purchaseFactor = fields.Float(
        load_default=1,
        metadata={
            'description': 'Factor by which the prices should be multiplied '
            '(complicated way of giving e.g. discounts), for '
            'purshases.'
        },
    )
    saleFactor = fields.Float(
        load_default=1,
        metadata={
            'description': 'Factor by which the prices should be multiplied '
            '(complicated way of giving e.g. discounts), for sales.'
        },
    )
    cbs = fields.String(
        metadata={
            'description': 'Code used by backend for automatically updating '
            'currency factors.'
        }
    )
    uuid = fields.UUID(
        load_default=uuid.uuid4, metadata={'description': 'Unique key per tenant.'}
    )

    @staticmethod
    def generate_fpqueries(currencies, *common):
        queries = []

        for currency in currencies:
            queries.append(
                (
                    'updatecurrencies',
                    [
                        *common,
                        ('uuid', resolve(currency, 'uuid')),
                        ('label', resolve(currency, 'label')),
                        ('description', resolve(currency, 'description')),
                        ('isocode', resolve(currency, 'code')),
                        (
                            'salefactor',
                            cast_percentage(resolve(currency, 'saleFactor')),
                        ),
                        (
                            'purchasefactor',
                            cast_percentage(resolve(currency, 'purchaseFactor')),
                        ),
                        ('cbs', resolve(currency, 'cbs')),
                    ],
                )
            )

        return serialize(queries)

    @validates('code')
    def validate_currency(self, value):
        if value != '' and not numbers.is_currency(value):
            raise ValidationError('{} is not a valid currency'.format(value))


class ShopSchema(Schema):
    """Redundant data, used for printing."""

    id = fields.String(
        validate=validate_warehouse_id,
        required=True,
        metadata={
            'description': 'The unique identifier of the shop/location which is a '
            'numerical string between 33 and 254.'
        },
    )
    city = fields.String(allow_none=True)
    houseno = fields.String(allow_none=True)
    houseadd = fields.String(allow_none=True)
    name = fields.String(allow_none=True)
    street = fields.String(allow_none=True)
    zipcode = fields.String(allow_none=True)
    phone = fields.String(allow_none=True)

    @post_load
    def populate_values(self, data, **kwargs):
        """Replace data with the ones from the warehouse in the database."""
        if 'id' in data and 'db' in self.context and 'tenant_id' in self.context:
            warehouse = self.context['db'].warehouses.find_one(
                {'tenant_id': self.context['tenant_id'], 'wh': data['id']}
            )
            if warehouse:
                data.update(
                    {
                        k: warehouse[k]
                        for k in self.fields.keys()
                        if k != 'id' and k in warehouse
                    }
                )
                for add in warehouse.get('addresses', []):
                    if add.get('primary'):
                        data.update({k: add[k] for k in self.fields.keys() if k in add})
                        break
        return data


class CashierSchema(Schema):
    """Redundant data, used for printing."""

    id = fields.String(
        required=True, metadata={'description': 'The unique identifier of the cashier.'}
    )
    name = fields.String(allow_none=True)
    fullname = fields.String(allow_none=True)

    @pre_load
    def fetch_cashier_data(self, data, **kwargs):
        if data.get('id') and 'db' in self.context and 'tenant_id' in self.context:
            try:
                _id = ObjectId(data['id'])
            except (InvalidId, TypeError):
                _id = data['id']

            cashier = self.context['db'].cashiers.find_one(
                {'_id': _id, 'tenant_id': self.context['tenant_id']}
            )
            if cashier:
                data.setdefault('name', cashier.get('name'))
                data.setdefault('fullname', cashier.get('fullname'))
        return data


class Logo(BaseSettingsSchema):
    """The logo of the client"""

    # The validation of URL does not allow empty strings. We can either
    # change the validation, or preprocess to remove empty strings.
    fullsize = fields.URL(
        allow_none=True,
        metadata={
            'description': 'Absolute URL for the full size logo image. Not bigger '
            'then 512px in any dimension'
        },
    )
    medium = fields.URL(
        allow_none=True,
        metadata={
            'description': 'Absolute URL for the resized medium logo image. Not '
            'bigger then 256px in any dimension'
        },
    )
    thumbnail = fields.URL(
        allow_none=True,
        metadata={
            'description': 'Absolute URL for the resized thumbnail logo image. Not '
            'bigger then 64px in any dimension'
        },
    )

    # this needs to be tested properly!!! this works, but now we need to allow
    # None as well, different solution would be to remove the field entirely
    # But if you remove the field, and a document will be saved, the entire
    # field will be removed from the document.
    @pre_load
    def remove_empty_strings(self, in_data, **kwargs):
        for field in in_data:
            if in_data[field] == '':
                in_data[field] = None
        return in_data


class DeleteSettings(Schema):
    settings = fields.List(
        fields.String(), required=True, validate=validate.Length(min=1)
    )

    @post_load
    def postprocess(self, data, **kwargs):
        data['settings'] = self.validate_delete_settings(data['settings'])
        return data

    def validate_delete_settings(self, settings):
        """
        Return a list of settings to delete

        Validate based on the roles and a schema. Expects flat list of settings.
        Nested settings are provided in dot notation.
        """
        roles = self.context['roles']
        schema = self.context['schema']

        CANNOT_DELETE = object()
        MAY_NOT_DELETE = object()

        def validate_setting(setting, schema=schema):
            try:
                fields = schema._declared_fields

                if '.' in setting:
                    parent_setting, nested_setting = setting.split('.', 1)
                    required_roles = fields[parent_setting].metadata.get('roles', roles)

                    if required_roles & roles:
                        return validate_setting(
                            nested_setting, fields[parent_setting].nested
                        )

                elif not fields[setting].metadata.get('roles', roles) & roles:
                    return MAY_NOT_DELETE
                elif not fields[setting].metadata.get('can_delete', True):
                    return CANNOT_DELETE
                return True
            except (AttributeError, KeyError):
                pass

        to_delete = []
        errors = {}
        for s in settings:
            delete = validate_setting(s)
            if delete is True:
                to_delete.append(s)
            elif delete == CANNOT_DELETE:
                errors[s] = 'This setting cannot be deleted'
            elif delete == MAY_NOT_DELETE:
                errors[s] = 'You do not have rights to edit this setting'

        if errors:
            raise ValidationError(errors)

        return to_delete
