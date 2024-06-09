"""
Endpoints for managing tenant accounts.
"""
import os

import pymongo
from marshmallow import ValidationError
from pyramid.settings import asbool

from spynl_schemas.tenant import Counters, Tenant

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException
from spynl.main.mail import send_template_email
from spynl.main.utils import get_settings, required_args

from spynl.api.auth.apps_and_roles import APPLICATIONS
from spynl.api.auth.exceptions import TenantDoesNotExist
from spynl.api.auth.utils import (
    audit_log,
    find_user,
    get_tenant_applications,
    get_user_info,
    lookup_tenant,
)
from spynl.api.hr.exceptions import UserHasNoEmail
from spynl.api.hr.utils import check_user_belongs_to_tenant, find_owner_contact_info

OWNER_ALLOWED_EDIT_FIELDS = (
    'bic',
    'bankAccountNumber',
    'bankAccountName',
    'vatNumber',
    'addresses',
    'gln',
    'cocNumber',
    'legalname',
    'name',
)

OWNER_ALLOWED_READ_FIELDS = OWNER_ALLOWED_EDIT_FIELDS + ('retail', 'wholesale')


@audit_log(
    message="Attempt to change access to application '{}' to <{}>.",
    request_args=['application', 'has_access'],
)
@required_args('application')
def change_application_access(request):
    """
    Change the access of a tenant to an application.

    ---
    post:
      tags:
        - account management
      description: >
        Change the access to an application for the requested tenant.
        The status is either toggled, or set to the value of
        the has_access parameter if provided.
        Only users with write access to the tenant can make this
        change. At the moment, only Softwear employees have this right.
        An email will be sent to all current tenant owners
        if a change was made.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        application  | string       | &#10004; | ID of the application to be
        changed\n
        has_access  | boolean      |          | enforce access to be given or
        revoked.\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
    """
    application = request.args['application']
    # check if application is valid:
    if application not in APPLICATIONS:
        raise SpynlException(
            _('change-app-access-unknown', mapping={'app': application})
        )
    if APPLICATIONS[application].get('default', False):
        raise SpynlException(_('change-app-access-default'))
    if APPLICATIONS[application].get('internal', False):
        raise SpynlException(_('change-app-access-internal'))
    if APPLICATIONS[application].get('link', False):
        raise SpynlException(_('change-app-access-link'))

    tid = request.requested_tenant_id
    tenant = lookup_tenant(request.db, tid)
    # here we do not use get_tenant_apps, because this endpoint only changes
    # which apps are in the db.
    tenant_apps = tenant.get('applications', [])

    old_access = application in tenant_apps
    if request.args.get('has_access') is not None:
        new_access = asbool(request.args['has_access'])
        if new_access is old_access:  # nothing needs to be done
            if old_access:
                msg = _('change-app-access-return-1')
            else:
                msg = _('change-app-access-return-2')
            return dict(status='ok', message=msg)
    else:
        new_access = not old_access

    if new_access:
        given_or_removed = _('change-app-access-given')
        tenant_apps.append(application)
    else:
        given_or_removed = _('change-app-access-revoked')
        tenant_apps = [app for app in tenant_apps if app != application]

    setter = {'applications': tenant_apps}
    request.db.tenants.update_one({'_id': tid}, {'$set': setter})

    auth_user = get_user_info(request, 'cached_user')

    # send email to all owners:
    # (please also change the send_all_templates endpoint if you change
    # anything here).
    contact_info = find_owner_contact_info(request.db, tid)
    for owner_id, owner in contact_info.items():
        if owner.get('email'):
            replacements = {
                'application': APPLICATIONS[application],
                'tenant_name': tenant['name'],
                'was_given': new_access,
                'recipient_fullname': owner.get('fullname'),
                'auth_user_username': auth_user.get('username'),
            }
            send_template_email(
                request,
                owner['email'],
                template_file='application_access_change_notification',
                replacements=replacements,
            )

    message = _(
        'change-app-access-return-3',
        mapping={'app': application, 'verb': given_or_removed, 'tenant_id': tid},
    )
    return dict(status='ok', message=message)


def get_applications(request):
    """
    Returns the applications of a tenant.

    ---
    get:
      tags:
        - account management
      description: >
        Returns a list of all available applications, with information
        if a particular tenant account has access to them. This will not
        return any of the default applications, since access to them
        cannot be changed.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | array  | array containing one object per
        application ("id", "has_access" (boolean) and "description" (string))\n
    """
    tid = request.requested_tenant_id
    tenant_applications = get_tenant_applications(lookup_tenant(request.db, tid))

    applications = []
    for app_id, app in APPLICATIONS.items():
        # do not return default or internal apps, access to them cannot be
        # changed.
        if (
            not app.get('default', False)
            and not app.get('internal', False)
            and not app.get('link', False)
        ):
            application_descr = app.get('description', '')
            applications.append(
                dict(
                    id=app_id,
                    has_access=app_id in tenant_applications,
                    description=application_descr,
                )
            )

    return dict(status='ok', data=applications)


@audit_log(
    message="Attempt to change ownership of user <{}> to <{}>.",
    request_args=['username', 'is_owner'],
)
@required_args('username')
def change_ownership(request):
    """
    Change ownership of a tenant for a user.

    ---
    post:
      tags:
        - account management
      description: >
        Change the ownership of a user for the requested tenant.
        The status is either toggled, or set to the value of
        the is_owner parameter if provided.
        Only users with write access to the tenant can make this
        change. At the moment, only Softwear employees have this right.
        An email will be sent to the user and all current tenant owners
        if a change was made.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | username for the user to be
        changed\n
        is_owner  | boolean      |          | enforce ownership to be given or
        revoked.\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
    """
    args = request.args

    # Check that username is in the database
    username = args['username']
    user = find_user(request.db, username)
    tid = request.requested_tenant_id
    check_user_belongs_to_tenant(tid, user)
    tenant = lookup_tenant(request.db, tid)
    tenant_owners = tenant.get('owners', [])

    old_ownership = user['_id'] in tenant_owners
    if args.get('is_owner') is not None:
        new_ownership = asbool(args['is_owner'])
        if new_ownership is old_ownership:  # nothing needs to be done
            if old_ownership:
                msg = _('change-ownership-return-no-change')
            else:
                msg = _('change-ownership-return-2')
            return dict(status='ok', message=msg)
    else:
        new_ownership = not old_ownership

    if new_ownership:
        # check that the new owner has an email address:
        if not user.get('email'):
            message = _('change-ownership-no-email')
            raise UserHasNoEmail(username=user['username'], message=message)
        if user.get('email_verify_pending'):
            raise SpynlException(message=_('owner-email-not-verified'))
        given_or_removed = _('change-ownership-given')
        tenant_owners.append(user['_id'])
    else:
        given_or_removed = _('change-ownership-removed')
        tenant_owners.remove(user['_id'])

    setter = {'owners': tenant_owners}
    request.db.tenants.update_one({'_id': tid}, {'$set': setter})

    # send email to all current owners, and, if applicable, old owner:
    contact_info = find_owner_contact_info(request.db, tid)
    # please also change the send_all_templates endpoint if you change
    # anything here.
    # will overwrite if already in owners, so no double emails:
    contact_info[user['_id']] = user
    for owner_id, owner in contact_info.items():
        if owner.get('email'):
            replacements = {
                'user_username': user.get('username'),
                'tenant': tenant['name'],
                'was_given': new_ownership,
                'recipient_fullname': owner.get('fullname'),
            }
            send_template_email(
                request,
                owner['email'],
                template_file='ownership_notification',
                replacements=replacements,
            )
    message = _(
        'change-ownership-return-3',
        mapping={'tenant_id': tid, 'verb': given_or_removed, 'username': username},
    )
    return dict(status='ok', message=message)


def get_owners(request):
    """
    Returns the owners of a tenant.

    ---
    get:
      tags:
        - account management
      description: >
        Get the owners of a particular account.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | array  | array containing owners ("id",
        "active" and "username")\n
    """
    tid = request.requested_tenant_id
    tenant_owners = lookup_tenant(request.db, tid).get('owners', [])

    owners_list = []
    for owner in tenant_owners:
        user = request.db.users.find_one({'_id': owner})
        if user:
            owners_list.append(
                dict(
                    username=user.get('username'),
                    active=user.get('active'),
                    id=user.get('_id'),
                )
            )

    return dict(status='ok', data=owners_list)


@required_args('data')
def save_current(ctx, request):
    """
    Save current tenant.

    ---
    post:
      description: >
        Only allowed fields will be saved/accepted. Data is expected to be complete as
        the save will overwrite the previous data.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        data      | dict         | &#10004; | Data to be updated\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error'\n
        message   | string | error description\n

      tags:
        - account management
    """
    input_data = request.json_payload.get('data', {})

    schema = Tenant(only=OWNER_ALLOWED_EDIT_FIELDS, partial=True)
    data = schema.load(input_data)
    # We treat this subset of fields as one unit. And replace the whole set.
    # Meaning we update the provided values and unset the ones that did not
    # get sent.
    update = {
        '$set': data,
        '$unset': {k: '' for k in OWNER_ALLOWED_EDIT_FIELDS if k not in data},
    }
    if not update['$set']:
        update.pop('$set')
    if not update['$unset']:
        update.pop('$unset')

    if data:
        tenant = request.db[ctx].find_one({'_id': request.current_tenant_id})
        request.db[ctx].update_one({'_id': request.current_tenant_id}, update)
        send_template_email(
            request,
            get_settings('spynl.hr.finance_email'),
            template_file='tenant_document_updated',
            replacements={'tenant': tenant['name'], 'fields': data.keys()},
        )
    return {}


def get_current(ctx, request):
    """
    Return the document of the current tenant.

    ---
    get:
      description: >
        Only the allowed fields will be returned.

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error'\n
        data      | string | tenant document\n

      tags:
        - account management
    """
    projection = dict.fromkeys(OWNER_ALLOWED_READ_FIELDS, 1)
    projection.update(_id=0)
    data = request.db[ctx].find_one(dict(_id=request.current_tenant_id), projection)
    return dict(data=data)


def get_counters(ctx, request):
    """
    Returns tenant's counters.

    ---
    get:
      tags:
        - account management
      description: >
        Returns tenant's counters.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | dict   | dictionary with the counters\n
    """
    data = request.db[ctx].find_one(
        {'_id': request.requested_tenant_id}, {'counters': 1, '_id': 0}
    )
    return dict(data=data.get('counters', {}))


def save_counters(ctx, request):
    """
    Save the new counters of the tenant.

    ---
    post:
      tags:
        - account management
      description: >
        Save the new counters of the tenant.
        Counters are defined in the counters schema:
        [schema](https://gitlab.com/softwearconnect/spynl.data/blob/master/spynl_schemas/tenant.py#L186)

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | dict   | the new updated counters\n
    """
    tenant = request.db[ctx].find_one(
        dict(_id=request.requested_tenant_id), dict(_id=0, counters=1)
    )
    if tenant is None:
        raise TenantDoesNotExist(request.requested_tenant_id)

    old_counters = tenant.get('counters', {})
    data = Counters(context=dict(old_counters=old_counters)).load(request.args)

    increment_counters = {
        'counters.' + key: val - old_counters.get(key, 0) for key, val in data.items()
    }
    updated_counters = request.db.pymongo_db.tenants.find_one_and_update(
        {'_id': request.requested_tenant_id},
        {'$inc': increment_counters},
        return_document=pymongo.ReturnDocument.AFTER,
        projection={'counters': 1, '_id': 0},
    )

    return dict(data=updated_counters.get('counters', {}))


def debug_query(cursor, query):
    if os.environ.get('DEBUG', False):
        import sqlparse

        print(sqlparse.format(cursor.mogrify(query), reindent=True))


def reset_bi(ctx, request):
    """
    Reset BI data for a tenant.
    ---
    post:

      description: >
        Removes all tenant transaction data from redshift database.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        data         | list   | all tenant transaction on redshift after the reset\n
    """

    requested_tenant_id = request.requested_tenant_id
    tenant = request.db[ctx].find_one(
        dict(_id=requested_tenant_id), dict(_id=0, counters=1)
    )
    if tenant is None:
        raise TenantDoesNotExist(request.requested_tenant_id)
    select_query = "select count(*) from transactions where tenant = {}".format(
        requested_tenant_id
    )
    remove_query = "delete from transactions where tenant = {}".format(
        requested_tenant_id
    )
    with request.redshift.cursor() as cursor:
        cursor.execute(select_query)
        debug_query(cursor, select_query)
    with request.redshift.cursor() as cursor:
        debug_query(cursor, remove_query)
        cursor.execute(remove_query)
        request.redshift.commit()
    with request.redshift.cursor() as cursor:
        cursor.execute(select_query)
        result = cursor.fetchall()
        return {'data': result}


@required_args('data')
def set_country_code(request):
    """
    Set the country code of a tenant.

    ---
    post:
      tags:
        - account management
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        data      | dict         | &#10004; | dictionary with one key:
        countryCode\n


        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | dict   | dictionary containing the new country code\n
    """
    data = request.args['data']

    if 'countryCode' not in data:
        # No need to translate, this is an internal endpoint:
        raise SpynlException('Missing countryCode key in data')

    try:
        data = Tenant(only=['countryCode']).load(data)
    # reraise so account manager can see error directly:
    except ValidationError as e:
        raise SpynlException(e)

    request.db.tenants.update_one(
        {'_id': request.requested_tenant_id},
        {'$set': {'countryCode': data['countryCode']}},
    )

    return {'data': data}
