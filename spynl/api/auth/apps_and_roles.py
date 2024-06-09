"""
This file specifies which applications and roles are in use by spynl. These
constants are used for documentation and verification (are apps/roles allowed?)

Note: If you assign APPLICATIONS to a variable, always make sure to assign
APPLICATIONS.copy(), so APPLICATIONS itself doesn't get changed, the same
goes for ROLES.
"""

from spynl.locale import SpynlTranslationString as _

# While admin is a valid application, it is only used by master tenant users
# with sw-roles, and thus is not needed for authorization, for now we do not
# include it in this list.
# Each application has a name (translatable), locale_id (translatable, used for
# urls, e.g. pos vs kassa, can be left out if no standard link is available),
# description (translatable), paid (boolean), options (list of paid options for the
# application), category (list, retail and or wholesale)
APPLICATIONS = {
    'pos': {
        'name': _('pos-app-name'),
        'description': _('pos-app-description'),
        'paid': True,
        'options': {
            'emailReceipt': {
                'name': _('email-receipt-option-name'),
                'description': _('email-receipt-option-description'),
            },
            'integratedPaymentSolution': {
                'name': _('integrated-payment-solution-option-name'),
                'description': _('integrated-payment-solution-option-description'),
            },
        },
        'category': ['retail'],
    },
    'dashboard': {
        'name': _('dashboard-app-name'),
        'description': _('dashboard-app-description'),
        'paid': False,
        'options': {},
        'category': ['retail', 'wholesale'],
    },
    'account': {
        'name': _('account-app-name'),
        'description': _('account-app-description'),
        'paid': False,
        'options': {},
        'category': ['retail', 'wholesale'],
        'default': True,
    },
    'photos': {
        'name': _('photos-app-name'),
        'description': _('photos-app-description'),
        'paid': False,
        'options': {},
        'category': ['retail', 'wholesale'],
        'default': True,
    },
    'products': {
        'name': _('products-app-name'),
        'description': _('products-app-description'),
        'paid': True,
        'options': {},
        'category': ['retail', 'wholesale'],
    },
    'crm': {
        'name': _('crm-app-name'),
        'description': _('crm-app-description'),
        'paid': True,
        'options': {},
        'category': ['retail', 'wholesale'],
    },
    'secondscreen': {
        'name': _('secondscreen-app-name'),
        'description': _('secondscreen-app-description'),
        'paid': False,
        'options': {
            'customerEntry': {
                'name': _('customer-entry-option-name'),
                'description': _('customer-entry-option-description'),
            },
            'customPlaylist': {
                'name': _('custom-playlist-option-name'),
                'description': _('custom-playlist-option-description'),
            },
        },
        'category': ['retail'],
    },
    'inventory': {
        'name': _('inventory-app-name'),
        'description': _('inventory-app-description'),
        'paid': False,
        'options': {},
        'category': ['retail', 'wholesale'],
    },
    'webshop': {
        'name': _('webshop-app-name'),
        'description': _('webshop-app-description'),
        'paid': False,
        'options': {},
        'category': ['wholesale'],
    },
    'sales': {
        'name': _('sales-app-name'),
        'description': _('sales-app-description'),
        'paid': True,
        'options': {},
        'category': ['wholesale'],
    },
    'logistics': {
        'name': _('logistics-app-name'),
        'description': _('logistics-app-description'),
        'paid': True,
        'options': {},
        'category': ['retail', 'wholesale'],
    },
    'picking': {
        'name': _('picking-app-name'),
        'description': _('picking-app-description'),
        'paid': True,
        'options': {},
        'category': ['wholesale'],
    },
    'polytex': {
        'name': 'Polytex',
        'description': 'Logistieke applicaties voor Polytex.',
        'paid': False,
        'options': {},
        'category': ['wholesale'],
    },
    'admin': {
        'name': 'Admin',
        'description': _('admin-app-description'),
        'paid': False,
        'options': {},
        'category': ['internal'],
        'internal': True,
    },
    'ecwid_link': {
        'name': _('ecwid_link-app-name'),
        'description': _('ecwid_link-app-description'),
        'paid': True,
        'options': {},
        'category': ['retail', 'wholesale'],
        'link': True,
    },
    'foxpro_backoffice': {
        'name': _('foxpro_backoffice-app-name'),
        'description': _('foxpro_backoffice-app-description'),
        'paid': True,
        'options': {},
        'category': ['retail', 'wholesale'],
        'link': True,
    },
    'hardwearshop': {
        'name': _('hardwearshop-app-name'),
        'description': _('hardwearshop-app-description'),
        'options': {},
        'category': ['retail', 'wholesale'],
        'link': True,
    },
}

# TODO: should we add Authenticated as a special role (different type, add table
# in roles.jinja2)? Now Authenticated should only show up in the resources table.
ROLES = {
    'pos-device': {'description': _('pos-device-description'), 'type': 'tenant'},
    'account-admin': {'description': _('account-admin-description'), 'type': 'tenant'},
    'dashboard-user': {
        'description': _('dashboard-user-description'),
        'type': 'tenant',
    },
    'dashboard-report_user': {
        'description': _('dashboard-report-user-description'),
        'type': 'tenant',
    },
    'products-admin': {
        'description': _('products-admin-description'),
        'type': 'tenant',
    },
    'products-user': {'description': _('products-admin-user'), 'type': 'tenant'},
    'products-demo': {
        'description': _('products-demo-description'),
        'type': 'tenant',
    },
    'products-brand_owner': {
        'description': _('products-brand-owner-description'),
        'type': 'tenant',
    },
    'products-dataprovider_admin': {
        'description': _('products-dataprovider-admin-description'),
        'type': 'tenant',
    },
    'products-purchase_admin': {
        'description': _('products-purchase-admin-description'),
        'type': 'tenant',
    },
    'products-purchase_user': {
        'description': _('products-purchase-user-description'),
        'type': 'tenant',
    },
    'secondscreen-user': {
        'description': _('secondscreen-user-description'),
        'type': 'tenant',
    },
    'secondscreen-admin': {
        'description': _('secondscreen-admin-description'),
        'type': 'tenant',
    },
    'inventory-user': {
        'description': _('inventory-user-description'),
        'type': 'tenant',
    },
    'sales-user': {'description': _('sales-user-description'), 'type': 'tenant'},
    'sales-admin': {'description': _('sales-admin-description'), 'type': 'tenant'},
    'logistics-inventory_user': {
        'description': _('logistics-inventory-user-description'),
        'type': 'tenant',
    },
    'logistics-receivings_user': {
        'description': _('logistics-receivings-user-description'),
        'type': 'tenant',
    },
    'picking-user': {'description': _('picking-user-description'), 'type': 'tenant'},
    'picking-admin': {'description': _('picking-admin-description'), 'type': 'tenant'},
    'polytex-user': {
        'description': 'Gebruikersrol voor de Polytex applicatie.',
        'type': 'tenant',
    },
    # special tenant roles:
    'owner': {'description': _('owner-description'), 'type': 'tenant'},
    # SW roles:
    'sw-account_manager': {
        'description': _('sw-account_manager-description'),
        'type': 'tenant',
    },
    'sw-admin': {'description': _('sw-admin-description'), 'type': 'tenant'},
    'sw-consultant': {'description': _('sw-consultant-description'), 'type': 'tenant'},
    'sw-developer': {'description': _('sw-developer-description'), 'type': 'tenant'},
    'spynl-developer': {
        'description': _('spynl-developer-description'),
        'type': 'tenant',
    },
    'sw-finance': {'description': _('sw-finance-description'), 'type': 'tenant'},
    'sw-servicedesk': {
        'description': _('sw-servicedesk-description'),
        'type': 'tenant',
    },
    'sw-reporting_admin': {
        'description': _('sw-reporting_admin-description'),
        'type': 'tenant',
    },
    'sw-marketing': {'description': _('sw-marketing-description'), 'type': 'tenant'},
    'sww-api': {'description': _('sww-api-description'), 'type': 'tenant'},
    'dashboard-tenant_overview': {
        'description': _('dashboard-tenant_overview-description'),
        'type': 'tenant',
    },
    # Token roles:
    'token-webshop-admin': {
        'description': _('webshop-admin-description'),
        'type': 'token',
    },
}
