"""Schema for a cashier."""

import hashlib

from marshmallow import ValidationError, fields, pre_load, validate, validates

from spynl_schemas.fields import Nested, ObjectIdField
from spynl_schemas.shared_schemas import BaseSchema, Schema


class ACLS(Schema):
    # ACLS (in alphabetical order):
    pos_2for1 = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a 2 for 1 '
            'discount on a sales transaction.'
        }
    )
    pos_3for2 = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a 3 for 2 '
            'discount on a sales transaction.'
        }
    )
    pos_4for3 = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a 4 for 3 '
            'discount on a sales transaction.'
        }
    )
    pos_discount = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a discount '
            'per scanned item on a sales transaction.'
        }
    )
    pos_discount_percentage = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a discount '
            'percentage on a scanned item on a sales transaction.'
        }
    )
    pos_drop = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to drop a sales '
            'transaction and start a new one.'
        }
    )
    pos_eos_edit = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to edit the EOS '
            'figures before submitting them.'
        }
    )
    pos_menu_acl = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the ACL menu '
            'which gives a user the ability to toggle these ACLs. This access is '
            'usually only given to an administrator of the POS.'
        }
    )
    pos_menu_buffer = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to view the unfinished '
            'transactions in the POS.'
        }
    )
    pos_menu_dashboard = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to see the POS '
            'dashboard which contains various sales figures for the store.'
        }
    )
    pos_menu_deposit = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the '
            'Deposit menu in the POS.'
        }
    )
    pos_menu_discountsettings = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to change the '
            'automatic discount rules.'
        }
    )
    pos_menu_eod = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the legacy '
            'End Of Day menu in the POS.'
        }
    )
    pos_menu_eod_divider = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to see the End Of Day '
            'divider in the more menu. This is only a display item with no function.'
        }
    )
    pos_menu_eos = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the End Of '
            'Shift menu in the POS.'
        }
    )
    pos_menu_opendrawer = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the Open '
            'Drawer menu in the POS.'
        }
    )
    pos_menu_paymentrules = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to configure the '
            'payment settings (cash, pin, creditcard, etc) of the POS. This ACL is '
            'usually only given to administrators of the POS.'
        }
    )
    pos_menu_print = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to adjust the '
            'printer settings in the POS.'
        }
    )
    pos_menu_reasoneditor = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the '
            'reasons used for giving discounts and opening the cash drawer.'
        }
    )
    pos_menu_reprintpinreceipt = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the PIN '
            'Reprint Receipt function. This access is only given to '
            'users who use a coupled PIN device.'
        }
    )
    pos_menu_reprintreceipt = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to reprint the last '
            'sales transaction.'
        }
    )
    pos_menu_selectreceipt = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the Select '
            'Receipt menu in the POS.'
        }
    )
    pos_menu_settings = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the '
            'settings menu in the POS. This access is usually only '
            'given to an administrator of the POS.'
        }
    )
    pos_menu_sscms = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the Second '
            'Screen CMS to upload new images and edit existing '
            'images. This access is usually only given to an '
            'administrator of the POS.'
        }
    )
    pos_menu_stock_divider = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to see the Stock '
            'divider in the more menu. This is only a display item '
            'with no function.'
        }
    )
    pos_menu_system_divider = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to view the System '
            'divider. This is only a display item with no function.'
        }
    )
    pos_menu_transitin = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to process transit '
            'orders coming into the store.'
        }
    )
    pos_menu_transitout = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to process transit '
            'orders going out of the store.'
        }
    )
    pos_menu_withdrawal = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to access the '
            'Withdrawal menu in the POS.'
        }
    )
    pos_price = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to change the price '
            'of a scanned item.'
        }
    )
    pos_qty = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to change the '
            'quantity of a scanned item.'
        }
    )
    pos_reason_categories = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to edit the reasons '
            'used in the POS. This access is usually only given to '
            'an administrator of the POS.'
        }
    )
    pos_return = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to add an item to be '
            'returned on a sales transaction.'
        }
    )
    pos_total_discount = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a monetary '
            'discount over the whole sales transaction. Example: A '
            'cashier can give a 5 EUR discount over the total amount '
            'due.'
        }
    )
    pos_total_discount_percentage = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to give a percentage '
            'discount over the whole sales transaction. Example: A cashier can give a '
            '10% discount over the total amount due.'
        }
    )
    pos_unblock_coupons = fields.Boolean(
        metadata={
            'description': 'This gives the cashier the ability to unblock a coupon.'
        }
    )


class Cashier(BaseSchema):
    """Schema for the person that stands behind a POS."""

    _id = ObjectIdField(
        required=True,
        dump_only=True,
        metadata={'description': 'The primary identifier for a cashier.'},
    )
    name = fields.String(
        required=True,
        validate=[
            validate.Length(max=8),
            validate.Regexp(
                regex='^[A-Z0-9]+$',
                error='cashier name can only contain letters and numbers',
            ),
        ],
        metadata={
            'description': 'This is usually a short name for the cashier such as '
            'first name or just a numeric code. All letters will be capitalized. '
            'Example: 01 or JOHN.'
        },
    )
    fullname = fields.String(
        required=True,
        metadata={
            'description': "The cashier's fullname including surname. Example: John "
            'Smith'
        },
    )
    password_hash = fields.String(
        required=True,
        data_key='password',
        metadata={
            'description': 'The passcode of the cashier used in the POS PIN pad. This '
            'is stored as a MD5 hash but is not seen as truly secure passcode.'
        },
    )
    acls = Nested(ACLS)

    @pre_load()
    def standard_acls(self, data, **kwargs):
        """Add standard ACLs for the given cashier_type"""
        cashier_type = data.get('type', 'normal')
        if cashier_type in ('normal', 'manager', 'admin'):
            data.setdefault('acls', {})
            data['acls'].update(
                {
                    key: value[cashier_type]
                    for key, value in DEFAULT_CASHIER_ACLS.items()
                }
            )
        else:
            raise ValidationError(
                "Unknown cashier type. Allowed types: 'normal', 'manager', " "'admin'",
                'type',
            )
        return data

    @pre_load()
    def hash_password(self, data, **kwargs):
        """
        md5 is not secure, but cashier passwords do not need to be secure.
        """
        if 'password' not in data:
            return data
        m = hashlib.new('md5')
        m.update(data['password'].encode('utf-8'))
        data['password'] = m.hexdigest()
        return data

    @pre_load()
    def upper_case_name(self, data, **kwargs):
        """all letters of the name should be upper case"""
        if 'name' in data:
            data['name'] = data['name'].upper()
        return data

    @validates('password_hash')
    def validate_uniqueness(self, value):
        if 'db' in self.context and 'tenant_id' in self.context:
            cashier = self.context['db'].cashiers.count(
                {'password_hash': value, 'tenant_id': self.context['tenant_id']}
            )
            if cashier:
                raise ValidationError('This password already exists for this tenant')


# fmt: off
DEFAULT_CASHIER_ACLS = {
    'pos_2for1'                    : {'normal': True,  'manager': True,  'admin': True },
    'pos_3for2'                    : {'normal': True,  'manager': True,  'admin': True },
    'pos_4for3'                    : {'normal': True,  'manager': True,  'admin': True },
    'pos_discount'                 : {'normal': True,  'manager': True,  'admin': True },
    'pos_discount_percentage'      : {'normal': True,  'manager': True,  'admin': True },
    'pos_drop'                     : {'normal': True,  'manager': True,  'admin': True },
    'pos_eos_edit'                 : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_acl'                 : {'normal': False, 'manager': True,  'admin': True },
    'pos_menu_buffer'              : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_dashboard'           : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_deposit'             : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_discountsettings'    : {'normal': False, 'manager': True,  'admin': True },
    'pos_menu_eod'                 : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_eod_divider'         : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_eos'                 : {'normal': False, 'manager': False, 'admin': False},
    'pos_menu_opendrawer'          : {'normal': False, 'manager': True,  'admin': True },
    'pos_menu_paymentrules'        : {'normal': False, 'manager': True,  'admin': True },
    'pos_menu_print'               : {'normal': False, 'manager': False, 'admin': True },
    'pos_menu_reasoneditor'        : {'normal': False, 'manager': True,  'admin': True },
    'pos_menu_reprintpinreceipt'   : {'normal': False, 'manager': False, 'admin': True },
    'pos_menu_reprintreceipt'      : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_selectreceipt'       : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_settings'            : {'normal': False, 'manager': False, 'admin': True },
    'pos_menu_sscms'               : {'normal': False, 'manager': False, 'admin': True },
    'pos_menu_stock_divider'       : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_system_divider'      : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_transitin'           : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_transitout'          : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_turnover'            : {'normal': True,  'manager': True,  'admin': True },
    'pos_menu_withdrawal'          : {'normal': True,  'manager': True,  'admin': True },
    'pos_price'                    : {'normal': True,  'manager': True,  'admin': True },
    'pos_qty'                      : {'normal': True,  'manager': True,  'admin': True },
    'pos_reason_categories'        : {'normal': False, 'manager': False, 'admin': True },
    'pos_return'                   : {'normal': True,  'manager': True,  'admin': True },
    'pos_total_discount'           : {'normal': True,  'manager': True,  'admin': True },
    'pos_total_discount_percentage': {'normal': True,  'manager': True,  'admin': True },
    'pos_unblock_coupons'          : {'normal': False, 'manager': True,  'admin': True },
}
# fmt: on
