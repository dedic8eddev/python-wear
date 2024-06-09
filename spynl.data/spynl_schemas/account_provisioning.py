from marshmallow import (
    ValidationError,
    fields,
    post_load,
    pre_load,
    validates,
    validates_schema,
)

from spynl_schemas.cashier import Cashier as BaseCashier
from spynl_schemas.fields import Nested
from spynl_schemas.shared_schemas import Schema
from spynl_schemas.tenant import Tenant as BaseTenant
from spynl_schemas.user import User as BaseUser
from spynl_schemas.warehouse import Warehouse as BaseWarehouse

VAT = {
    # http://www.cijfernieuws.nl/btw-in-eu/
    # accessed 2019-01-16
    'NL': {'high': 21.0, 'low': 9.0, 'zero': 0.0},
    # 'BE': {'high': 21.0, 'low': 12.0, 'zero': 0.0},
    # 'BG': {'high': 20.0, 'low':  9.0, 'zero': 0.0},
    # 'CY': {'high': 19.0, 'low':  9.0, 'zero': 0.0},
    # 'DK': {'high': 25.0, 'low':  0.0, 'zero': 0.0},
    # 'DE': {'high': 19.0, 'low':  6.0, 'zero': 0.0},
    # 'EE': {'high': 20.0, 'low':  9.0, 'zero': 0.0},
    # 'FI': {'high': 24.0, 'low': 14.0, 'zero': 0.0},
    # 'FR': {'high': 20.0, 'low': 10.0, 'zero': 0.0},
    # 'GR': {'high': 24.0, 'low': 13.0, 'zero': 0.0},
    # 'GB': {'high': 20.0, 'low':  5.0, 'zero': 0.0},
    # 'HU': {'high': 27.0, 'low': 18.0, 'zero': 0.0},
    # 'IE': {'high': 23.0, 'low': 13.5, 'zero': 0.0},
    # 'IT': {'high': 22.0, 'low': 10.0, 'zero': 0.0},
    # 'HR': {'high': 25.0, 'low': 13.0, 'zero': 0.0},
    # 'LV': {'high': 21.0, 'low': 12.0, 'zero': 0.0},
    # 'LT': {'high': 21.0, 'low':  9.0, 'zero': 0.0},
    # 'LU': {'high': 17.0, 'low': 14.0, 'zero': 0.0},
    # 'MT': {'high': 18.0, 'low':  7.0, 'zero': 0.0},
    # 'AT': {'high': 20.0, 'low': 10.0, 'zero': 0.0},
    # 'PL': {'high': 23.0, 'low':  8.0, 'zero': 0.0},
    # 'PT': {'high': 23.0, 'low': 13.0, 'zero': 0.0},
    # 'RO': {'high': 19.0, 'low':  9.0, 'zero': 0.0},
    # 'SI': {'high': 22.0, 'low':  9.5, 'zero': 0.0},
    # 'SK': {'high': 20.0, 'low': 10.0, 'zero': 0.0},
    # 'ES': {'high': 21.0, 'low':  4.0, 'zero': 0.0},
    # 'CZ': {'high': 21.0, 'low': 10.0, 'zero': 0.0},
    # 'SE': {'high': 25.0, 'low': 12.0, 'zero': 0.0},
    # https://www.avalara.com/vatlive/en/country-guides/asia/turkey/turkey-vat-compliance-and-rates.html
    # accessed 2019-01-16
    # 'TR': {'high': 18.0, 'low':  8.0, 'zero': 0.0},
    # http://taxsummaries.pwc.com/ID/Morocco-Corporate-Other-taxes
    # accessed 2019-01-16
    # 'MA': {'high': 20.0, 'low':  8.0, 'zero': 0.0},
    # 'SG': {'high':  0.0, 'low':  0.0, 'zero': 0.0},
    # 'NO': {'high':  0.0, 'low':  0.0, 'zero': 0.0},
}


class StripTopLevel(Schema):
    """
    At this point, all values for all fields read from the csv are strings,
    and not nested values. This means we only have to loop over top level
    fields.

    This needs to be done because otherwise marshmallow won't fill in
    missing values and email fields will complain about invalid emails.
    """

    @pre_load
    def remove_empty_strings(self, data, **kwargs):
        for key, value in data.copy().items():
            if value == '':
                data.pop(key)
        return data


class Tenant(BaseTenant, StripTopLevel):
    """
    Use the basic tenant schema, but do some account provisioning specific
    things
    """

    @pre_load
    def account_provisioning(self, data, **kwargs):
        """Data processing needed for account provisioning"""
        if data.get('applications'):
            data['applications'] = sorted(set(data['applications'].split(',')))
        if 'uploadDirectory' in data:
            if 'settings' not in data:
                data['settings'] = {}
            data['settings']['uploadDirectory'] = data['uploadDirectory']
        return data

    @validates_schema(skip_on_field_errors=False)
    def check_retail_wholesale_flags(self, data, **kwargs):
        """Either wholesale or retail needs to be true (or both)"""
        if not (data.get('retail') or data.get('wholesale')):
            raise ValidationError(
                'A tenant needs to be flagged as retail or wholesale or both'
            )

    @post_load
    def set_vat(self, data, **kwargs):
        country_code = data.get('countryCode')
        if not country_code:
            return data

        try:
            data['settings']['vat'] = VAT[country_code]
        except KeyError:
            pass

        return data


class User(BaseUser, StripTopLevel):
    """
    Use the basic user schema, but do some account provisioning specific
    things
    """

    @pre_load()
    def account_provisioning(self, data, **kwargs):
        """Set defaults and preform checks for new users"""

        try:
            if 'tenant_id' in data:
                self.context['tenant_id'] = data['tenant_id']

            # needs to be done pre_load because fullname is required
            if 'username' in data and not data.get('fullname'):
                data['fullname'] = data['username'].capitalize()

            if data.get('roles'):
                data['roles'] = {
                    self.context['tenant_id']: {
                        'tenant': sorted(set(data['roles'].split(',')))
                    }
                }
            if data.get('type') == 'owner':
                data['type'] = 'standard'
        except Exception as e:
            raise ValidationError("Input schema wrong format key: {}".format(str(e)))

        return self.set_device_defaults(data)

    @pre_load
    def set_tenant(self, data, **kwargs):
        """Overwrite set_tenant of the user schema, if it's there"""
        if 'tenant_id' in data:
            data['tenant_id'] = [data['tenant_id']]
        return data

    def set_device_defaults(self, data):
        """Set defaults for devices"""
        if data.get('type') == 'device':
            # set context var for nested schemas to use
            self.context['device'] = True
            if 'db' in self.context and 'tenant_id' in self.context:
                if 'deviceId' not in data:
                    data['deviceId'] = self.get_new_device_id(
                        self.context['db'], self.context['tenant_id']
                    )
                if 'default_application' not in data:
                    data['default_application'] = {self.context['tenant_id']: 'pos'}
        return data

    @validates_schema(skip_on_field_errors=False, pass_original=True)
    def check_password(self, data, original_data, **kwargs):
        """Validate the password"""
        password = original_data.get('password')
        if self.context.get('password_validator') and password:
            self.context['password_validator'](password)


class Cashier(BaseCashier, StripTopLevel):
    """
    Use the basic cashier schema, but do some account provisioning specific
    things
    """

    @pre_load
    def set_tenant(self, data, **kwargs):
        """
        In account provisioning, tenant_id's are provided as single strings.
        """
        if 'tenant_id' in data:
            data['tenant_id'] = [data['tenant_id']]

        return data

    @validates_schema(skip_on_field_errors=False)
    def validate_uniqueness(self, data, **kwargs):
        if 'tenant_id' not in data or 'password_hash' not in data:
            return
        self.context['tenant_id'] = data['tenant_id'][0]
        super().validate_uniqueness(data['password_hash'])


class Warehouse(BaseWarehouse, StripTopLevel):
    """
    Use the basic warehouse schema, but do some account provisioning specific
    things
    """

    @pre_load
    def set_tenant(self, data, **kwargs):
        """
        In account provisioning, tenant_id's are provided as single strings.
        (Overwrite set_tenant method of BaseWarehouse)
        """
        if 'tenant_id' in data:
            data['tenant_id'] = [data['tenant_id']]

        return data

    @validates_schema(skip_on_field_errors=False)
    def validate_uniqueness(self, data, **kwargs):
        if 'tenant_id' not in data or 'wh' not in data:
            return
        self.context['tenant_id'] = data['tenant_id'][0]
        super().validate_uniqueness(data, **kwargs)


class AccountProvisioning(Schema):
    """Schema for storing all data from the import into one schema"""

    tenants = Nested(Tenant, many=True)
    users = Nested(User, many=True)
    cashiers = Nested(Cashier, many=True)
    warehouses = Nested(Warehouse, many=True)
    owners = fields.Dict()
    devices = fields.Dict()
    warnings = fields.List(fields.String, load_default=list)

    @pre_load
    def get_list_of_new_tenants(self, data, **kwargs):
        """
        To be able to check if all the tenant_id's in users cashiers and
        warehouses are valid, we need a list of tenant_ids that are being
        added now.
        """
        self.context['allowed_tenants'] = set(
            item['_id'] for item in data.get('tenants', []) if '_id' in item
        )
        return data

    # Functions for checking uniqueness within the import. Uniqueness with
    # respect to db is checked in the nested schemas.
    @validates('tenants')
    def check_uniqueness_within_import_tenants_ids(self, value):
        """Check if there are duplicate _ids within import."""
        check_uniqueness(value, '_id')

    @validates('tenants')
    def check_uniqueness_within_import_tenants_names(self, value):
        """Check if there are duplicate names within import."""
        check_uniqueness(value, 'name')

    @validates('users')
    def check_uniqueness_within_import_users_usernames(self, value):
        """Check if there are duplicates usernames within import."""
        check_uniqueness(value, 'username')

    @validates('users')
    def check_uniqueness_within_import_users_emails(self, value):
        """Check if there are duplicates emails within import."""
        check_uniqueness(value, 'email', allow_none=True)

    @validates('warehouses')
    def check_uniqueness_within_import_warehouses(self, value):
        """Wh should be unique per tenant."""
        tenant_ids = set(
            warehouse['tenant_id'][0] for warehouse in value if 'tenant_id' in warehouse
        )
        validation_errors = []
        for tid in tenant_ids:
            whs = [
                warehouse['wh']
                for warehouse in value
                if 'wh' in warehouse and tid in warehouse.get('tenant_id', [])
            ]
            duplicates = [item for item in set(whs) if whs.count(item) > 1]
            if duplicates:
                validation_errors.append(
                    'There are duplicate wh numbers in the'
                    ' import for tenant_id {}: {}'.format(tid, duplicates)
                )
        if validation_errors:
            raise ValidationError(validation_errors)

    @validates_schema(skip_on_field_errors=False, pass_original=True)
    def check_uniqueness_within_import_cashiers(self, data, original_data, **kwargs):
        """The password_hash should be unique per tenant."""
        if 'cashiers' not in data:
            return
        tenant_ids = set(
            cashier['tenant_id'][0]
            for cashier in original_data['cashiers']
            if 'tenant_id' in cashier
        )
        validation_errors = []
        for tid in tenant_ids:
            pwds = [
                cashier['password']
                for cashier in original_data['cashiers']
                if tid in cashier.get('tenant_id', []) and 'password' in cashier
            ]
            duplicates = [item for item in set(pwds) if pwds.count(item) > 1]
            if duplicates:
                validation_errors.append(
                    'There are duplicate passwords in the '
                    'import for tenant_id {}'.format(tid)
                )
        if validation_errors:
            raise ValidationError(validation_errors, 'cashiers')

    @pre_load
    def prepare_owners_and_devices(self, data, **kwargs):
        """
        Set owners and devices ('owner' type will be replaced by 'standard' in
        user pre load)
        """
        data['devices'] = {}
        data['owners'] = {}
        for i, user in enumerate(data.get('users', [])):
            if user.get('type') == 'owner':
                data['owners'][i] = user['tenant_id']
            elif user.get('type') == 'device':
                data['devices'][i] = user['tenant_id']
        return data

    @post_load
    def check_new_tenants_have_owners(self, data, **kwargs):
        """warn if a tenant does not have an owner"""
        for tenant in data.get('tenants', []):
            if tenant['_id'] not in data['owners'].values():
                data['warnings'].append(
                    'Tenant {} does not have an owner. Please add one as soon '
                    'as possible.'.format(tenant['_id'])
                )
        return data

    @post_load(pass_original=True)
    def warn_non_device_passwords(self, data, original_data, **kwargs):
        """
        Passwords for non-device users will are ignored. Warn when this happens.
        """
        for user in original_data.get('users', []):
            if 'password' in user and user['type'] != 'device':
                data['warnings'].append(
                    'Password for user {} was not set. You can only set a '
                    'password for device users'.format(user['username'])
                )
        return data

    @post_load
    def check_if_tenant_has_correct_applications(self, data, **kwargs):
        """
        For each user, check if the tenant has the applications corresponding
        to the roles of that user.
        """
        warnings = {}
        applications = {
            tenant['_id']: tenant.get('applications', [])
            for tenant in data.get('tenants', [])
        }
        for user in data.get('users', []):
            tenant_id = user['tenant_id'][0]
            if tenant_id not in applications and 'db' in self.context:
                tenant = self.context['db'].tenants.find_one({'_id': tenant_id})
                applications[tenant_id] = tenant.get('applications', [])
            for role in user.get('roles', {}).get(tenant_id, {}).get('tenant', []):
                app = role.split('-')[0]
                if (
                    app != 'account'
                    and app not in applications.get(tenant_id, [])
                    and app not in warnings.get(tenant_id, [])
                ):
                    if tenant_id in warnings:
                        warnings[tenant_id].append(app)
                    else:
                        warnings[tenant_id] = [app]

        for tenant_id, apps in warnings.items():
            data['warnings'].append(
                'Tenant {} misses apps needed for user '
                'roles: {}. Add the apps for the user to be '
                'able to use them.'.format(tenant_id, apps)
            )
        return data


def check_uniqueness(value, field_name, allow_none=False):
    """
    Standard function for checking uniqueness within a list for a certain field.
    If allow_none is True, None values are allowed to be duplicated.
    """
    field_values = [
        item[field_name]
        for item in value
        if field_name in item and not (allow_none and item[field_name] is None)
    ]
    duplicates = [item for item in set(field_values) if field_values.count(item) > 1]
    if duplicates:
        # The value is provided as valid_data, so the validation of this field
        # does not stop after this validation. (multiple fields can have
        # duplicates)
        raise ValidationError(
            'There are duplicate {}s in the import:'
            ' {}'.format(field_name, duplicates),
            valid_data=value,
        )
