"""Map resources to endpoints that will be used."""


from pyramid.authorization import Authenticated
from pyramid.security import NO_PERMISSION_REQUIRED

from spynl.api.auth.resources import Tenants, User
from spynl.api.hr import (
    account_provisioning,
    developer_endpoints,
    order_terms,
    retail_customer,
    tenant_crud,
    tenant_endpoints,
    user_crud,
    user_endpoints,
    wholesale_customer,
)
from spynl.api.hr.resources import (
    AccountManager,
    AccountProvisioning,
    AccountResource,
    Cashiers,
    DeveloperTools,
    OrderTerms,
    RetailCustomers,
    Settings,
    Tokens,
    WholesaleCustomers,
)
from spynl.api.hr.settings import (
    delete_tenant_settings,
    delete_user_settings,
    get_settings,
    get_tenant_settings,
    get_user_settings,
    set_tenant_settings,
    set_upload_directory,
    set_user_settings,
)
from spynl.api.hr.token_endpoints import generate_token, list_tokens, revoke_token
from spynl.api.mongo.db_endpoints import count
from spynl.api.mongo.plugger import add_dbaccess_endpoints


def includeme(config):
    """Configure endpoints."""

    add_dbaccess_endpoints(
        config, Cashiers, ['get', 'edit', 'add', 'count', 'save', 'remove']
    )
    add_dbaccess_endpoints(config, RetailCustomers, ['get', 'count'])
    config.add_endpoint(
        retail_customer.add, 'add', context=RetailCustomers, permission='add'
    )
    config.add_endpoint(
        retail_customer.save, 'save', context=RetailCustomers, permission='edit'
    )

    # Tenant endpoints
    config.add_endpoint(
        tenant_crud.get_tenants,
        '/',
        context=Tenants,
        permission='read',
        request_method='GET',
    )
    config.add_endpoint(
        tenant_crud.get_tenants, 'get', context=Tenants, permission='read'
    )
    config.add_endpoint(
        tenant_crud.edit_tenant,
        '/',
        context=Tenants,
        permission='edit',
        request_method='POST',
    )
    config.add_endpoint(
        tenant_crud.edit_tenant, 'edit', context=Tenants, permission='edit'
    )
    config.add_endpoint(count, 'count', context=Tenants, permission='read')

    # Order terms endpoints
    config.add_endpoint(order_terms.save, 'save', context=OrderTerms, permission='edit')
    config.add_endpoint(order_terms.get, 'get', context=OrderTerms, permission='read')
    config.add_endpoint(
        order_terms.remove, 'remove', context=OrderTerms, permission='delete'
    )

    # Wholesale customer endpoints
    config.add_endpoint(
        wholesale_customer.save, 'save', context=WholesaleCustomers, permission='edit'
    )
    config.add_endpoint(
        wholesale_customer.get, 'get', context=WholesaleCustomers, permission='read'
    )
    config.add_endpoint(
        wholesale_customer.count, 'count', context=WholesaleCustomers, permission='read'
    )

    # Token endpoints
    config.add_endpoint(generate_token, 'request', context=Tokens, permission='add')
    config.add_endpoint(revoke_token, 'revoke', context=Tokens, permission='delete')
    config.add_endpoint(list_tokens, 'get', context=Tokens, permission='read')

    # (Mostly) generic /user/* db access endpoints
    config.add_endpoint(user_crud.get_users, '/', context=User, permission='read')
    config.add_endpoint(user_crud.get_users, 'get', context=User, permission='read')
    config.add_endpoint(user_crud.count_users, 'count', context=User, permission='read')
    config.add_endpoint(user_crud.add_user, 'add', context=User, permission='add')
    config.add_endpoint(user_crud.edit_user, 'edit', context=User, permission='edit')

    # Specific /user/* management endpoints
    config.add_endpoint(
        user_endpoints.update_tenant_roles,
        'update-roles',
        context=User,
        permission='edit',
    )
    config.add_endpoint(
        user_endpoints.get_tenant_roles, 'get-roles', context=User, permission='read'
    )
    config.add_endpoint(
        user_endpoints.change_active, 'change-active', context=User, permission='edit'
    )
    # Specific /tenants/* management endpoints
    config.add_endpoint(
        tenant_endpoints.change_application_access,
        'change-application-access',
        context=Tenants,
        permission='edit',
    )
    config.add_endpoint(
        tenant_endpoints.get_applications,
        'get-applications',
        context=Tenants,
        permission='read',
    )
    config.add_endpoint(
        tenant_endpoints.change_ownership,
        'change-ownership',
        context=Tenants,
        permission='edit',
    )
    config.add_endpoint(
        tenant_endpoints.get_owners, 'get-owners', context=Tenants, permission='read'
    )
    config.add_endpoint(
        tenant_endpoints.get_counters,
        'get-counters',
        context=Tenants,
        permission='read',
    )
    config.add_endpoint(
        tenant_endpoints.save_counters,
        'save-counters',
        context=Tenants,
        permission='edit',
    )
    config.add_endpoint(
        tenant_endpoints.reset_bi,
        'reset-bi',
        context=Tenants,
        redshift=True,
        permission='edit',
    )
    # account manager endpoints:
    config.add_endpoint(
        tenant_endpoints.set_country_code,
        'set-country-code',
        context=AccountManager,
        permission='edit',
    )
    config.add_endpoint(
        set_upload_directory,
        'change-upload-directory',
        context=AccountManager,
        permission='edit',
    )
    config.add_endpoint(
        user_endpoints.change_email_account_manager,
        'change-email',
        context=AccountManager,
        permission='edit',
    )

    # endpoints for owners:
    config.add_endpoint(
        tenant_endpoints.save_current,
        'save',
        context=AccountResource,
        permission='edit',
    )
    config.add_endpoint(
        tenant_endpoints.get_current, 'get', context=AccountResource, permission='read'
    )

    # Change pwd and email endpoints, update me
    config.add_endpoint(
        user_endpoints.request_pwd_reset,
        'request-pwd-reset',
        permission=NO_PERMISSION_REQUIRED,
    )
    config.add_endpoint(
        user_endpoints.reset_pwd, 'reset-pwd', permission=NO_PERMISSION_REQUIRED
    )
    config.add_endpoint(
        user_endpoints.change_pwd, 'change-pwd', permission=Authenticated
    )
    config.add_endpoint(
        user_endpoints.change_email, 'change-email', permission=Authenticated
    )
    config.add_endpoint(
        user_endpoints.change_username, 'change-username', permission=Authenticated
    )
    config.add_endpoint(
        user_endpoints.verify_email, 'verify-email', permission=NO_PERMISSION_REQUIRED
    )
    config.add_endpoint(
        user_endpoints.resend_email_verification_key,
        'resend-email-verification-key',
        permission=Authenticated,
    )

    config.add_endpoint(user_endpoints.update_me, 'update-me', permission=Authenticated)

    # Endpoints for settings management
    config.add_endpoint(get_settings, '/', context=Settings, permission=Authenticated)
    config.add_endpoint(get_settings, 'get', context=Settings, permission=Authenticated)
    config.add_endpoint(
        get_user_settings, 'get-user', context=Settings, permission='read'
    )
    config.add_endpoint(
        get_tenant_settings, 'get-tenant', context=Settings, permission='read'
    )
    config.add_endpoint(
        set_user_settings, 'set-user', context=Settings, permission='edit'
    )
    config.add_endpoint(
        delete_user_settings, 'delete-user', context=Settings, permission='edit'
    )
    config.add_endpoint(user_endpoints.set_2fa, 'set-2fa', permission=Authenticated)
    config.add_endpoint(
        set_tenant_settings, 'set-tenant', context=Settings, permission='edit'
    )
    config.add_endpoint(
        delete_tenant_settings, 'delete-tenant', context=Settings, permission='edit'
    )

    # Endpoint for account provisioning
    config.add_endpoint(
        account_provisioning.import_new_accounts,
        'import',
        context=AccountProvisioning,
        permission='add',
    )

    # Endpoint for checking templates
    config.add_endpoint(
        developer_endpoints.send_all_templates,
        'email-templates',
        context=DeveloperTools,
        permission='add',
    )

    config.include('pyramid_jinja2')
    config.add_settings(
        {
            'base_email_template': 'base.jinja2',
            'jinja2.globals': {'tenant_logo_url': tenant_logo_url},
        }
    )
    config.add_jinja2_search_path('spynl.api.hr:email-templates')

    config.add_jinja2_renderer('.jinja2')


def tenant_logo_url(request):
    """Return the logo url from tenant's settings."""
    tenant_id = request.requested_tenant_id
    tenant = request.db.tenants.find_one({'_id': tenant_id}, {'settings': 1, '_id': 0})
    if not tenant:
        return None
    return tenant['settings'].get('logoUrl', {}).get('medium')
