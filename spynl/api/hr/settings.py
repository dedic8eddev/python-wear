"""
Module for maintaining settings on users and tenants.

Settings is modelled as a virtual resource so that we
are in control how they are accessed. Most importantly,
we want to keep close track of who can read and write
which settings.
Right now, we distinguish between normal users and superusers
and maintain whitelists. When roles are rolled out, we plan
to maintain a list of supported settings in the Settings
resource and keep track precisely who (which roles) can
read and write each setting.

We want to enable frontends to send
dotted notation. Therefore, we internally flatten
all settings to dot-notated keys. For example,

    {"logo": {"thumbnail": "http://..."},
             {"fullsize": "http://..."}}

is internally treated as the two settings

    "logo.thumbnail" and "logo.fullsize"

Settings can be treated via dynamic getter and setter functions,
such that for example setting a setting can perform a validation
or getting it can compute the value dynamicall rather than
simply fetching it from the database.
"""

from bson import ObjectId

from spynl_schemas import Currency
from spynl_schemas.shared_schemas import DeleteSettings
from spynl_schemas.tenant import Loyalty, LoyaltyException
from spynl_schemas.tenant import Settings as TenantSettings
from spynl_schemas.tenant import (
    generate_modify_price_receivings_fp_query,
    generate_regions_fp_query,
    to_date,
)
from spynl_schemas.user import Settings as UserSettings

from spynl.locale import SpynlTranslationString as _

from spynl.main import dateutils
from spynl.main.exceptions import IllegalAction, SpynlException
from spynl.main.utils import required_args

from spynl.api.auth.exceptions import CannotRetrieveUser, Forbidden
from spynl.api.auth.utils import (
    MASTER_TENANT_ID,
    get_tenant_roles,
    get_user_info,
    lookup_tenant,
)
from spynl.api.hr.utils import check_user_belongs_to_tenant, flatten, inflate
from spynl.api.mongo.utils import insert_foxpro_events


def get_user(request):
    """find a user by request data"""
    if 'userid' in request.args:
        user = request.db.users.find_one({'_id': ObjectId(request.args['userid'])})
    elif 'username' in request.args:
        user = request.db.users.find_one({'username': request.args['username']})
    else:
        user = get_user_info(request, 'cached_user')
    if user is None:
        raise CannotRetrieveUser()
    return user


def get_settings(request):
    """
    Return the settings of the current tenant and authenticated user.
    ---

    post:
      description: >
        Returns the settings of both authenticated user and current tenant. This endoint
        is a shortcut for a special use case. For any other use case, e.g. cross-tenant
        access, use the other settings endpoints.
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              user:
                type: object
                properties:
                  id:
                    type: string
                  username:
                    type: string
                  settings:
                    type: object
                    $ref: 'user_settings.json#/definitions/Settings'
              tenant:
                type: object
                properties:
                  id:
                    type: string
                    decription: tenant id
                  settings:
                    type: object
                    $ref: 'tenant_settings.json#/definitions/Settings'
      tags:
        - settings management
    """
    user = get_user_info(request, 'cached_user')
    if user is None:
        raise CannotRetrieveUser()

    if request.requested_tenant_id != request.current_tenant_id:
        raise SpynlException(_('only-current-account'))
    tenant = lookup_tenant(request.db, request.current_tenant_id)

    user_settings = UserSettings().dump(user.get('settings', {}))

    tenant_settings = TenantSettings().dump(tenant.get('settings', {}))

    if 'pointFactor' in tenant_settings.get('loyalty', {}):
        tenant_settings['loyalty']['pointFactor'] = determine_loyalty_factor(request)

    settings = {
        'user': {
            'id': user['_id'],
            'username': user['username'],
            'settings': user_settings,
        },
        'tenant': {'id': request.requested_tenant_id, 'settings': tenant_settings},
    }
    return dict(status='ok', data=settings)


def get_user_settings(request):
    """
    Returns the settings of the user.
    ---

    post:
      description: >
        Return user settings.
        Give either userid or username. If none are given, the
        settings of the authenticated user are returned.
        Only master users can get settings of users that are
        not in the current tenant.

      parameters:
        - name: body
          in: body
          schema:
            type: object
            properties:
              userid:
                type: string
                description: The user's ID
              username:
                type: string
                description: The user's username
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              data:
                type: object
                $ref: 'user_settings.json#/definitions/Settings'
      tags:
        - settings management
    """
    user = get_user(request)
    settings = UserSettings().dump(user.get('settings', {}))
    # NOTE now all users can see settings of all other users of the same tenant,
    # so non-admin users can see the settings of other non-admin users.
    if request.current_tenant_id != MASTER_TENANT_ID:
        check_user_belongs_to_tenant(request.current_tenant_id, user)
    return dict(status='ok', data=settings)


def get_tenant_settings(request):
    """
    Return the settings of a tenant.
    ---

    post:
      description: >
        Returns the settings object of a tenant.
        Only master users can read settings from a tenant that
        is not the(ir) current tenant.\n

      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              data:
                type: object
                $ref: 'tenant_settings.json#/definitions/Settings'
      tags:
        - settings management
    """
    tenant = lookup_tenant(request.db, request.requested_tenant_id)
    settings = TenantSettings().dump(tenant.get('settings', {}))

    if 'pointFactor' in settings.get('loyalty', {}):
        settings['loyalty']['pointFactor'] = determine_loyalty_factor(request)

    return dict(status='ok', data=settings)


@required_args('settings')
def set_user_settings(request):
    """
    Set settings of a user.

    ---

    post:
      description: >
        Sets user settings from the given data object.
        Give either userid or username. If none are given, the
        settings of the authenticated user are updated.
        Only master users can set settings of users that do not
        not belong the(ir) current tenant.\n
        Note: None of the settings are required and defaults are not filled in if
        a setting is not provided.\n
        Note: we currently do not tell you which settings were ignored
        but you can tell from the difference between input and output.\n
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              userid:
                type: string
                description: The user's ID
              username:
                type: string
                description: The user's username
              settings:
                type: object
                $ref: 'user_settings.json#/definitions/Settings'
            required:
              - settings
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              data:
                type: object
                $ref: 'user_settings.json#/definitions/Settings'
      tags:
        - settings management
    """
    args = request.args
    roles = get_tenant_roles(
        request.db,
        request.cached_user,
        request.current_tenant_id,
        restrict=(request.current_tenant_id != MASTER_TENANT_ID),
    )
    settings = args.get('settings', {})
    user = get_user(request)
    if request.current_tenant_id != MASTER_TENANT_ID:
        check_user_belongs_to_tenant(request.current_tenant_id, user)
        if user['_id'] != request.cached_user['_id'] and not {
            'owner',
            'account-admin',
            'sales-admin',
        } & set(roles):
            raise Forbidden(_('change-user-settings-not-allowed'))

    regions = (
        lookup_tenant(request.db, request.current_tenant_id)
        .get('settings', {})
        .get('sales', {})
        .get('regions')
    )
    schema = UserSettings(context=dict(user_roles=roles, available_regions=regions))

    settings = schema.load(settings, partial=True)

    request.db.users.update_one(
        {'_id': user['_id']}, {'$set': flatten(settings, parent_key='settings')}
    )

    return dict(status='ok', message=_('user-settings-updated'), data=settings)


@required_args('settings')
def set_tenant_settings(request):
    """
    Set settings of a tenant.

    ---

    post:
      description: >
        Sets tenant settings from the given data object.
        Only master users can set settings on a tenant that
        is not the(ir) current tenant.\n
        Note: we currently do not tell you which settings were ignored
        but you can tell from the difference between input and output.\n
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              settings:
                type: object
                $ref: 'tenant_settings.json#/definitions/Settings'
            required:
              - settings
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              data:
                type: object
                $ref: 'tenant_settings.json#/definitions/Settings'
      tags:
        - settings management
    """
    settings = request.args.get('settings', {})
    if not isinstance(settings, dict):
        raise SpynlException(_('invalid-settings-format'))
    settings = inflate(settings)

    roles = get_tenant_roles(
        request.db,
        request.cached_user,
        request.current_tenant_id,
        restrict=(request.current_tenant_id != MASTER_TENANT_ID),
    )

    schema = TenantSettings(context=dict(user_roles=roles), partial=True)

    # For backwards compatibility some validations raise a specific error that we can
    # translate:
    try:
        settings = schema.load(settings)
    except LoyaltyException as e:
        if 'Start date should be before end date' in str(e):
            raise SpynlException(_('illegal-period-end-over-start'))
        elif 'Campaign overlap' in str(e):
            raise SpynlException(_('campaign-overlap'))
        else:
            raise

    if settings == {}:
        raise SpynlException(_('no-applicable-settings'))

    tenant_id = request.requested_tenant_id

    if 'currencies' in settings and settings['currencies']:
        # reload, should not be partial
        settings['currencies'] = Currency().load(settings['currencies'], many=True)

        old_settings = request.db.tenants.find_one(
            {'_id': tenant_id}, {'settings': 1}
        ).get('settings', {})

        new_currencies = {
            currency['uuid']: currency['label'] for currency in settings['currencies']
        }
        old_currencies = {
            currency['uuid']: currency['label']
            for currency in old_settings.get('currencies', [])
        }

        for uuid, label in old_currencies.items():
            if uuid not in new_currencies or label != new_currencies[uuid]:
                raise IllegalAction(
                    _('cannot-delete-currencies', mapping={'label': label})
                )

        insert_foxpro_events(
            request, settings['currencies'], Currency.generate_fpqueries
        )

    if 'regions' in settings.get('sales', {}):
        users = list(
            request.db.users.find(
                {
                    '$and': [
                        {'tenant_id': tenant_id},
                        {
                            'sales.region': {
                                '$not': {'$in': settings['sales']['regions']}
                            }
                        },
                        {'sales.region': {'$ne': ''}},
                        {'sales.region': {'$exists': True}},
                    ]
                }
            )
        )
        customers = list(
            request.db.wholesale_customers.find(
                {
                    '$and': [
                        {'tenant_id': tenant_id},
                        {'region': {'$not': {'$in': settings['sales']['regions']}}},
                        {'region': {'$ne': ''}},
                        {'region': {'$exists': True}},
                    ]
                }
            )
        )
        if users or customers:
            used_regions = set(
                [u['sales']['region'] for u in users] + [c['region'] for c in customers]
            )
            deleted_regions = [
                r for r in used_regions if r not in settings['sales']['regions']
            ]
            raise IllegalAction(
                _(
                    'regions-still-in-use',
                    mapping={'regions': ', '.join(deleted_regions)},
                )
            )

        insert_foxpro_events(
            request, settings['sales']['regions'], generate_regions_fp_query
        )

    if 'allowModifyPriceReceivings' in settings.get('logistics', {}):
        insert_foxpro_events(
            request, settings['logistics'], generate_modify_price_receivings_fp_query
        )

    if 'loyalty' in settings:
        insert_foxpro_events(
            request, settings['loyalty'], Loyalty.generate_fpqueries, check_empty=True
        )

    request.db.tenants.update_one(
        {'_id': request.requested_tenant_id},
        {'$set': flatten(settings, parent_key='settings')},
    )

    return dict(status='ok', message=_('account-settings-updated'), data=settings)


@required_args('settings')
def set_upload_directory(request):
    """
    Set the uploadDirectory

    ---

    post:
      description: >
        Sets the uploadDirectory on the tenant.
        Only the sw-account_manager has access.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              settings:
                type: object
                properties:
                  uploadDirectory:
                    type: string
                required:
                  - uploadDirectory
            required:
              - settings
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
      tags:
        - settings management
    """
    tenant_id = request.requested_tenant_id

    schema = TenantSettings(only=['uploadDirectory'])
    dir = schema.load(request.args['settings'])['uploadDirectory']

    if request.db.tenants.pymongo_count_documents(
        {'settings.uploadDirectory': dir, 'tenant_id': {'$not': {'$in': [tenant_id]}}}
    ):
        raise IllegalAction(_('duplicate-upload-directory'))

    request.db.tenants.update_one(
        {'_id': tenant_id}, {'$set': {'settings.uploadDirectory': dir}}
    )

    return dict(status='ok', message=_('upload-directory-updated'))


def delete_user_settings(request):
    """
    delete settings of a user.

    ---

    post:
      description: >
        delete user settings
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              userid:
                type: string
                description: The user's ID
              username:
                type: string
                description: The user's username
              settings:
                description: >
                  a flat list of settings using dot notation
                  that need to be deleted.
                type: array
                items:
                  type: string
            required:
              - settings
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              deleted:
                type: array
                description: list of settings that were deleted
                items:
                  type: string
      tags:
        - settings management
    """
    roles = get_tenant_roles(
        request.db,
        request.cached_user,
        request.current_tenant_id,
        restrict=(request.current_tenant_id != MASTER_TENANT_ID),
    )
    user = get_user(request)
    if request.current_tenant_id != MASTER_TENANT_ID:
        check_user_belongs_to_tenant(request.current_tenant_id, user)
        if user['_id'] != request.cached_user['_id'] and not {
            'owner',
            'account-admin',
            'sales-admin',
        } & set(roles):
            raise Forbidden(_('change-user-settings-not-allowed'))

    return _delete_settings(
        request.json_payload, request.db.users, user['_id'], roles, UserSettings
    )


def delete_tenant_settings(request):
    """
    Delete settings of a tenant.

    ---

    post:
      description: >
        delete tenant settings
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              settings:
                description: >
                  a flat list of settings using dot notation
                  that need to be deleted.
                type: array
                items:
                  type: string
            required:
              - settings
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
              deleted:
                type: array
                description: list of settings that were deleted
                items:
                  type: string
      tags:
        - settings management
    """

    roles = get_tenant_roles(
        request.db,
        request.cached_user,
        request.current_tenant_id,
        restrict=(request.current_tenant_id != MASTER_TENANT_ID),
    )

    return _delete_settings(
        request.json_payload,
        request.db.tenants,
        request.requested_tenant_id,
        roles,
        TenantSettings,
    )


def _delete_settings(payload, collection, _id, roles, schema):
    to_delete = DeleteSettings(context={'roles': set(roles), 'schema': schema}).load(
        payload
    )['settings']
    collection.update_one(
        {'_id': _id}, {'$unset': {'settings.' + s: None for s in to_delete}}
    )
    return {'deleted': to_delete}


def determine_loyalty_factor(request):
    """
    Look up if we are currently within a loyalty campaign.
    If so, return the campaigns pointFactor,
    otherwise return default pointFactor (which is usually 1).
    """
    tenant = lookup_tenant(request.db, request.requested_tenant_id)
    user = get_user_info(request, purpose='cached_user')
    settings = tenant.get('settings', {})
    campaigns = settings.get('loyalty', {}).get('campaigns', [])

    today = dateutils.now(tz=user.get('tz', 'Europe/Amsterdam')).date()
    for campaign in campaigns:
        start_date = to_date(campaign['startDate'])
        end_date = to_date(campaign['endDate'])
        if start_date <= today and today <= end_date:
            return campaign['factor']
    return flatten(settings).get('loyalty.pointFactor', 1)
