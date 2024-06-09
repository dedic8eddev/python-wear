"""
Endpoints for managing user accounts.

* request_pwd_reset
* reset_pwd
* change_pwd
* change_email
* verify_email
* resend_email_verification_key
* update_tenant_roles
* get_tenant_roles
* change_active
"""
import os

import pyotp
from marshmallow import EXCLUDE, ValidationError, fields, validates, validates_schema
from pymongo.errors import DuplicateKeyError
from pyramid.httpexceptions import HTTPForbidden
from pyramid.settings import asbool

from spynl_schemas import ObjectIdField, Schema, lookup

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import now
from spynl.main.exceptions import IllegalAction, InvalidResponse, SpynlException
from spynl.main.mail import send_template_email
from spynl.main.utils import get_settings, required_args, validate_locale

from spynl.api.auth.apps_and_roles import ROLES
from spynl.api.auth.authentication import challenge, set_password
from spynl.api.auth.exceptions import CannotRetrieveUser, Forbidden, WrongCredentials
from spynl.api.auth.keys import check_key, remove_key, store_key
from spynl.api.auth.session_cycle import USER_EDIT_ME_WHITELIST
from spynl.api.auth.utils import (
    MASTER_TENANT_ID,
    app_url,
    audit_log,
    find_user,
    get_tenant_applications,
)
from spynl.api.auth.utils import get_tenant_roles as get_tenant_roles_util
from spynl.api.auth.utils import (
    get_user_info,
    lookup_tenant,
    validate_email,
    validate_password,
)
from spynl.api.hr.exceptions import EmailNotSet
from spynl.api.hr.utils import (
    check_roles,
    check_user_belongs_to_tenant,
    find_owner_contact_info,
    get_user_contacts,
    send_pwdreset_key,
    validate_username,
)


@audit_log(
    message='Request to reset password for user <{}>.', request_args=['username']
)
@required_args('username')
def request_pwd_reset(request):
    """
    Request initiation of password reset process.

    ---
    post:
      description: >
        Send an email to the (unauthenticated) user with a password reset key.
        This only is done if a user is identifiable by his username or with
        that address.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | Username or Email address to
        identify the user\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n


      tags:
        - account management
    """
    username = request.args['username']
    user = find_user(request.db, username, search_email=True)
    sent_to = send_pwdreset_key(request, user)
    if sent_to:
        msg = _('request-pwd-reset-return-ok')
        return dict(status='ok', message=msg)
    else:
        raise SpynlException(_('request-pwd-reset-error'))


@audit_log(
    message='Attempt to reset password for user <{}> (key used: {}).',
    request_args=['username', 'key'],
)
@required_args('username', 'key', 'pwd1', 'pwd2')
def reset_pwd(request):
    """
    Reset a password with a password reset key.

    ---
    post:
      description: >
        Finish password reset process. Works only if the "username" parameter
        identifies a user, if the correct "key" parameter is sent and the
        new password is given twice ("pwd1" and "pwd2").

        All sessions of the user are removed from the database.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | Username or Email address to
        identify the user\n
        key       | string       | &#10004; | The access key which was sent
        by email\n
        pwd1      | string       | &#10004; | new password
        pwd2      | string       | &#10004; | new password again,
        for confirmation\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n


      tags:
        - account management
    """
    args = request.args
    username = args['username']
    user = find_user(request.db, username, search_email=True)

    key_status = check_key(request.db, user['_id'], 'pwd_reset', args['key'])
    if not key_status['valid']:
        if key_status['exists']:
            raise Forbidden(_('reset-pwd-expired-key'))
        else:
            raise Forbidden(_('reset-pwd-invalid-key'))

    pwd1 = args['pwd1']
    pwd2 = args['pwd2']
    if pwd1 != pwd2:
        raise Forbidden(_('reset-pwd-unmatched-password'))
    validate_password(pwd1)
    set_password(request, user, pwd1)

    request.db.spynl_sessions.delete_many({'auth___userid': user['_id']})
    remove_key(request.db, user['_id'], 'pwd_reset')
    return dict(status='ok', message=_('reset-pwd-return'))


@audit_log(message='Attempt to change password.')
@required_args('current_pwd', 'pwd1', 'pwd2')
def change_pwd(request):
    """
    Change the password of the authenticated user.

    ---

    post:
      description: >
        Change the password of the authenticated user.
        Only possible if the existing password is given as well.
        This will send a notification email to the the user if (s)he
        has an email adress or the tenant owner(s) otherwise.

        All other sessions of the user are removed from the database.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        current_pwd   | string   | &#10004; | Current password\n
        pwd1     | string       | &#10004; | new password
        pwd2     | string       | &#10004; | new password again, for
        confirmation\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n

      tags:
        - account management
    """
    user = get_user_info(request, 'cached_user')
    user_id = challenge(request, request.args['current_pwd'], username=user['username'])
    if not user_id:
        raise Forbidden(_('change-pwd-incorrect-password'))
    pwd1 = request.args['pwd1']
    pwd2 = request.args['pwd2']
    if pwd1 != pwd2:
        raise Forbidden(_('reset-pwd-unmatched-password'))
    validate_password(pwd1)
    set_password(request, user, pwd1)

    request.db.spynl_sessions.delete_many(
        {'auth___userid': user_id, '_id': {'$ne': request.session.id}}
    )

    # please also change the send_all_templates endpoint if you change
    # anything here.
    for email in get_user_contacts(user, request):
        replacements = {
            'user_username': user.get('username'),
            'user_greeting': user.get('fullname', user.get('username')),
        }
        send_template_email(
            request,
            email,
            template_file='password_change_notification',
            replacements=replacements,
        )

    return dict(status='ok', message=_('change-pwd-return'))


@audit_log(
    message='Email address requested to be changed to <{}>.', request_args=['new_email']
)
@required_args('current_pwd', 'new_email')
def change_email(request):
    """
    Change the email address of the authenticated user.

    ---
    post:
      tags:
        - account management
      description: >
        Change the email address of the authenticated user.
        Only possible if the existing password is given as well.
        This will send a notification email to the old address,
        as well as a verification key to the new address. The email address
        will be the new one of the user immediately.
        For device users and inventory users it's possible to remove the email
        address as well.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              current_pwd:
                required: true
                type: string
                description: a password is needed to change the email.
              new_email:
                required: true
                type: string
                description: the new email
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
    """
    new_email = request.args['new_email']
    user = request.cached_user

    # Check the user's password
    user_id = challenge(request, request.args['current_pwd'], username=user['username'])
    if not user_id:
        raise Forbidden(_('change-email-incorrect-password'))

    return _change_email(request, new_email, user)


@audit_log(
    message='Email address requested to be changed to <{}>.', request_args=['new_email']
)
@required_args('username', 'new_email')
def change_email_account_manager(request):
    """
    Change the email address of a user

    ---
    post:
      tags:
        - account management
      description: >
        Change the email address of the authenticated user.
        Only possible if the existing password is given as well.
        This will send a notification email to the old address,
        as well as a verification key to the new address. The email address
        will be the new one of the user immediately.
        For device users and inventory users it's possible to remove the email
        address as well.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              username:
                required: true
                type: string
                description: username of user that needs email changed
              new_email:
                required: true
                type: string
                description: the new email
      responses:
        200:
          schema:
            type: object
            properties:
              status:
                type: string
              message:
                type: string
    """
    # Check that the new email is in the correct format
    new_email = request.args['new_email']

    user = request.db.users.find_one({'username': request.args['username']})
    if not user:
        raise CannotRetrieveUser()

    return _change_email(request, new_email, user)


def _change_email(request, new_email, user):
    """shared code for changing an email address"""
    if new_email == '':
        roles = get_tenant_roles_util(request.db, user, user['tenant_id'][0])
        # 1. user of type device.
        # 2. user has only the mentioned roles and has only one tenant.
        if user.get('type') == 'device' or (
            len(user['tenant_id']) == 1
            and (
                set(roles)
                <= {'inventory-user', 'logistics-inventory_user', 'pos-device'}
            )
        ):
            return _delete_email(request, user)
        raise Forbidden(_('change-to-empty-email-with-one-tenant'))

    validate_email(new_email)
    # Check that email is not in use on another account
    if request.db.users.find_one({'email': new_email}):
        raise Forbidden(_('change-email-already-used', mapping={'address': new_email}))
    # Generate confirmation code and save it back to the user document
    key = store_key(request.db, user['_id'], 'email-verification', 172800)

    setter = {'email': new_email, 'email_verify_pending': True}

    username = user['username']
    old_email = user.get('email')

    # Set the new email as the primary email and push the original email
    # into the oldEmails array.
    request.db.users.update_one(
        {'username': username}, {'$set': setter, '$addToSet': {'oldEmails': old_email}}
    )

    message = _('change-email-mail-changed').translate(request.localizer)

    # please also change the send_all_templates endpoint if you change
    # anything here.
    # Send notification to the old email
    replacements = {
        'new_email_address': new_email,
        'user_username': username,
        'user_fullname': user.get('fullname', username),
    }
    send_template_email(
        request,
        old_email,
        replacements=replacements,
        template_file='email_change_notification',
    )

    # Send confirmation to the new email
    replacements = {
        'new_email_address': new_email,
        'key': key,
        'app_url': app_url(request, 'www'),
        'user_username': username,
        'user_fullname': user.get('fullname', username),
        'first': True,
    }
    if send_template_email(
        request,
        new_email,
        replacements=replacements,
        template_file='email_change_confirmation',
    ):
        message += _('email-change-mail-sent').translate(request.localizer)

    return dict(status='ok', message=message)


def _delete_email(request, user):
    """
    Set user's email to None.

    Because of the unique index we set it to None instead of empty string.
    Send email to that address to inform that it was deleted.
    """
    username = user.get('username')

    query = {'$set': {'email': None, 'email_verify_pending': False}}
    request.db.users.update_one({'username': username}, query)
    tenant = lookup_tenant(request.db, request.requested_tenant_id)
    # legalname is required for a tenant, so the requested_tenant_id is a
    # fallback for incorrect data.
    tenant_name = tenant.get('name') or tenant.get(
        'legalname', request.requested_tenant_id
    )

    removed_email = user.get('email')

    # please also change the send_all_templates endpoint if you change
    # anything here.
    replacements = {
        'user_username': username,
        'user_fullname': user.get('fullname', username),
        'tenant_name': tenant_name,
        'email_removed': True,
    }
    send_template_email(
        request,
        removed_email,
        replacements=replacements,
        template_file='email_change_notification',
    )

    # please also change the send_all_templates endpoint if you change
    # anything here.
    contact_info = find_owner_contact_info(request.db, request.requested_tenant_id)
    for owner_id, owner in contact_info.items():
        replacements = {
            'user_username': username,
            'user_fullname': owner.get('fullname'),
            'tenant_name': tenant_name,
            'removed_email': removed_email,
            'multiple_owners': len(contact_info) > 1,
        }
        send_template_email(
            request,
            owner['email'],
            template_file='email_removal_notification_owners',
            replacements=replacements,
        )

    message = _('change-email-mail-removed')
    return dict(status='ok', message=message)


@audit_log(
    message='Email address <{}> requested to be verified.', request_args=['email']
)
@required_args('email', 'key')
def verify_email(request):
    """
    Confirm the email address of a non-authenticated user's account.

    ---
    post:
      tags:
        - account management
      description: >
        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        email     | string       | &#10004; | new email address\n
        key       | string       | &#10004; | \n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
    """
    email = request.args['email']
    validate_email(email)
    # Locate the user account by the email address
    user = request.db.users.find_one({'email': email})
    if not user:
        raise Forbidden(_('verify-email-user-not-found', mapping={'email': email}))

    if not user.get('email_verify_pending'):
        raise Forbidden(_('verify-email-not-required', mapping={'email': email}))

    # Check if key is correct and valid
    key = request.args['key']
    key_status = check_key(request.db, user['_id'], 'email-verification', key)
    if not key_status['valid']:
        if key_status['exists']:
            raise Forbidden(_('reset-pwd-expired-key'))
        else:
            raise Forbidden(_('reset-pwd-invalid-key'))

    # if the key was valid, we can remove it and verify the email:
    remove_key(request.db, user['_id'], 'email-verification')
    request.db.users.update_one(
        {'_id': user['_id']}, {'$set': {'email_verify_pending': False}}
    )
    return dict(status='ok', message=_('verify-email-return'))


@audit_log()
def resend_email_verification_key(request):
    """
    Resend the key to verify an email which still needs verification.

    ---
    post:
      tags:
        - account management
      description: >
        This can be used by an authenticated user who changed his email address
        recently but does not have the key to verify that he indeed uses this
        address.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
    """
    user = get_user_info(request, 'fresh_user')
    username = user.get('username')
    if not user:
        raise Forbidden(
            _('resend-mail-verification-user-not-found', mapping={'username': username})
        )
    email = user.get('email')

    if user.get('email_verify_pending') is not True:
        raise Forbidden(_('resend-mail-verification-no-verification-required'))
    # This check could be removed if we set email_verify_pending to false for all users
    # without email addresses.
    elif not email:
        request.db.users.update_one(
            {'_id': user['_id']}, {'$set': {'email_verify_pending': False}}
        )
        raise EmailNotSet()

    key = store_key(request.db, user['_id'], 'email-verification', 172800)

    # Send verification key to the new email
    # please also change the send_all_templates endpoint if you change
    # anything here.
    replacements = {
        'key': key,
        'new_email_address': email,
        'app_url': app_url(request, 'www'),
        'user_username': username,
        'user_fullname': user.get('fullname', username),
        'first': False,
    }
    if send_template_email(
        request,
        email,
        template_file='email_change_confirmation',
        replacements=replacements,
    ):
        return dict(
            status='ok',
            message=_('resend-mail-verification-email-sent', mapping={'email': email}),
        )
    else:
        return dict(status='error', message=_('resend-mail-verification-no-key-sent'))


@required_args('data')
def update_me(request):
    """
    Update the currently logged-in user.

    ---
    get:
      description: >
        Updates specific user profile properties
        Languages are validated against our supported languages in the .ini
        files.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        data      | dict         | &#10004; | Data to be updated, will become
        a parameter to the MongoDB $pull operator.\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error'\n
        message   | string | error description\n
        updated | list | list of fields which were affected (only
        white-listed fields are applied to the DB)
        information\n

      tags:
        - session
    """
    user = get_user_info(request, 'cached_user')
    if not user:
        raise CannotRetrieveUser()

    data = request.args['data']
    update_doc = {key: data[key] for key in USER_EDIT_ME_WHITELIST if key in data}

    if update_doc:
        set_langague_cookie = False
        if 'language' in update_doc:
            language = validate_locale(update_doc['language'])
            if not language:
                locales = ['nl-nl', 'en-gb', 'fr-fr', 'de-de', 'it-it', 'es-es']
                raise InvalidResponse(
                    _('invalid-locale', mapping={'locales': ', '.join(locales)})
                )
            else:
                set_langague_cookie = True

        updated = list(update_doc.keys())

        message = _('update-profile-return-ok')

        request.db.users.update_one({'_id': user['_id']}, {'$set': update_doc})

        if set_langague_cookie:
            cookie_domain = get_settings()['spynl.domain']
            request.response.set_cookie(
                'lang', value=update_doc['language'], domain=cookie_domain
            )
            request._LOCALE_ = language

    else:
        updated = None
        message = _('update-nothing-return-ok')

    return dict(message=message, affected_fields=updated or [], status='ok')


@audit_log(
    message='Roles set to <{}> for user <{}>.', request_args=['roles', 'username']
)
@required_args('roles', 'username')
def update_tenant_roles(request):
    """
    Update tenant roles for a user.

    ---
    post:
      tags:
        - account management
      description: >
        Set/unset tenant roles for a user for the requested tenant.
        Only users with write access to the user collection of this tenant
        can make this change.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | username for the user\n
        roles     | dict         | &#10004; | a dict with role names
        as keys and boolean values as values. If True, role will be in the
        list of roles in the DB, if False, the role will be removed if it
        is in the list.\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
    """
    # TODO: check roles for tenant applications

    args = request.args
    roles = args['roles']
    if not isinstance(roles, dict):
        raise SpynlException(_('update-tenant-roles-not-dict'))
    check_roles(roles, 'tenant')

    # Check that username is in the database
    username = args['username']
    user = find_user(request.db, username)

    tid = request.requested_tenant_id
    check_user_belongs_to_tenant(tid, user)

    # check roles against tenant's applications
    tenant = request.db.tenants.find_one({'_id': tid})
    tenant_apps = get_tenant_applications(tenant)
    for role in roles:
        app = role.split('-')[0]
        if app not in tenant_apps:
            raise SpynlException(
                _(
                    'update-tenant-roles-no-access',
                    mapping={'tenant_id': tid, 'role': role, 'app': app},
                )
            )
    user = request.db.users.find_one({'username': username})
    # start with existing:
    final_roles = set(user.get('roles', {}).get(tid, {}).get('tenant', []))
    for role in [r for r in roles if roles[r] is True]:
        final_roles.add(role)
    for role in [r for r in roles if roles[r] is False and r in final_roles]:
        final_roles.remove(role)
    setter = {'roles.%s.tenant' % tid: list(final_roles)}
    request.db.users.update_one({'username': username}, {'$set': setter})

    if not user.get('email'):
        status = 'warning'
        # .  transalate to fr, de
        message = _(
            'update-tenant-roles-return-warning',
            mapping={'user': username, 'roles': ','.join(final_roles)},
        )
    else:
        status = 'ok'
        message = _(
            'update-tenant-roles-return',
            mapping={'user': username, 'roles': ','.join(final_roles)},
        )

    return dict(status=status, message=message)


@required_args('username')
def get_tenant_roles(request):
    """
    get tenant roles for a user.

    ---
    post:
      tags:
        - account management
      description: >
        Retrieve the dictionary of available tenant roles for a user
        for the set tenant, with roles set to True if the user currently has
        them.


        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | username for the user\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        roles        | object | dictionary with a key per role that is
                                available to the user for the set tenant.
                                If the user has a role, the value for it
                                is True, otherwise it's False\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
    """
    args = request.args
    username = args['username']
    user = find_user(request.db, username)

    tid = request.requested_tenant_id
    check_user_belongs_to_tenant(tid, user)

    current_roles = get_tenant_roles_util(request.db, user, tid, restrict=True)

    # only return available roles with type 'tenant':
    available_roles = {
        key: value for key, value in ROLES.items() if value['type'] == 'tenant'
    }
    if available_roles is None:
        available_roles = []
    # make sure tenant has access to corresponding applications:
    tenant_apps = get_tenant_applications(lookup_tenant(request.db, tid))

    for role in available_roles.copy():
        if role.split('-')[0] not in tenant_apps:
            available_roles.pop(role, None)

    roles = {}
    for role in available_roles:
        roles[role] = role in current_roles

    return dict(status='ok', roles=roles)


@audit_log(
    message="Activity status of user <{}> was set, with the"
    " 'active' param being <{}>",
    request_args=['username', 'active'],
)
@required_args('username')
def change_active(request):
    """
    Change active field for a user.

    ---
    post:
      tags:
        - account management
      description: >
        Change the active status of a user. The status is either toggled, or
        set to the value provided. Only users with write access to the user
        collection of this tenant can make this change.
        An email will be sent if a change was made (to the user or the account
        owners if the user has no email address).

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | username for the user to be
        changed\n
        active    | boolean      |          | set active to true or false\n

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
    check_user_belongs_to_tenant(request.requested_tenant_id, user)

    old_active = user['active']
    new_active = args.get('active', not old_active)
    new_active = asbool(new_active)  # needed in case endpoint is used as get

    if new_active is old_active:
        return dict(
            status='ok',
            message=_('change-active-no-change', mapping={'active_status': new_active}),
        )

    update = {'active': new_active}
    # we also set last_login to now, so the user does not get deactivated
    # again over night (inactive users get deactivated).
    if new_active:
        update['last_login'] = now(tz='UTC')
    request.db.users.update_one({'username': username}, {'$set': update})
    if new_active:
        activated = _('change-active-activated')
    else:
        activated = _('change-active-deactivated')

    # please also change the send_all_templates endpoint if you change
    # anything here.
    for email in get_user_contacts(user, request):
        replacements = {
            'user_username': user.get('username'),
            'user_fullname': user.get('fullname'),
            'activated': True if new_active else False,
        }
        send_template_email(
            request,
            email,
            replacements=replacements,
            template_file='account_status_notification',
        )

    message = _(
        'change_active-return-ok',
        mapping={'username': username, 'active_status': activated},
    )
    return dict(status='ok', message=message)


@audit_log(
    message='Request to change username to <{}>. For user with id <{}>',
    request_args=['userId', 'username'],
)
@required_args('username')
def change_username(request):
    """
    Change the username of the currently authenticated user or user
    specified by userId.

    ---
    post:
      tags:
        - account management
      description: >
        Change the username of the currently authenticated user or user
        specified by userId.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username     | string       | &#10004; | new username\n
        userId     | string       | | id of user \n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
    """

    class UsernameSchema(Schema):
        username = fields.String(required=True)
        userId = ObjectIdField()

        @validates('username')
        def validate_username(self, value):
            try:
                validate_username(value)
            except ValueError as e:
                raise ValidationError(e.args[0])

        class Meta:
            unknown = EXCLUDE

    # default to changing own userId
    request.args.setdefault('userId', request.authenticated_userid)
    data = UsernameSchema().load(request.args)
    user = request.cached_user

    if data['userId'] != request.authenticated_userid:
        # if not admin don't allow users to change others' usernames.
        required_roles = {'sw-admin', 'sw-servicedesk', 'sw-account_manager'}
        master_roles = set(
            get_tenant_roles_util(
                request.db, request.cached_user, MASTER_TENANT_ID, restrict=False
            )
        )
        if (
            request.current_tenant_id != MASTER_TENANT_ID
            or not master_roles & required_roles
        ):
            exc = IllegalAction(_('illegal-filter'))
            exc.http_escalate_as = HTTPForbidden
            raise exc
        user = request.db.users.find_one({'_id': data['userId']})

    try:
        request.db.users.update_one(
            {'_id': data['userId']}, {'$set': {'username': data['username']}}
        )
    except DuplicateKeyError:
        raise IllegalAction(
            _('existing-user-by-username', mapping={'username': data['username']})
        )

    send_template_email(
        request,
        user['email'],
        template_file='username_change_notification',
        replacements={
            'fullname': user.get('fullname', data['username']),
            'old_username': user['username'],
            'new_username': data['username'],
        },
    )

    return {}


class SetTwoFactorAuthSchema(Schema):
    TwoFactorAuthEnabled = fields.Boolean(
        required=True, metadata={'description': 'Enable Two Factor Authentication'}
    )
    username = fields.String(required=True)
    password = fields.String(required=True)

    @validates_schema
    def authenticate(self, data, **kwargs):
        if not challenge(
            self.context['request'], data['password'], username=data['username']
        ):
            raise WrongCredentials()


def set_2fa(request):
    """
    Setup two factor authentication

    ---
    post:
      description: >
        Setup two factor authentication.
        If the setting does not change the endpoint is a noop.
      tags:
        - session
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'set_two_factor_auth.json#/definitions/SetTwoFactorAuthSchema'
      responses:
        200:
          description: Set 2fa response
          schema:
            type: object
            properties:
              2FAProvisioningUri:
                type: string
                description: uri to for registering with an 2fa authorization app
    """
    data = SetTwoFactorAuthSchema(context={'request': request}).load(
        request.json_payload
    )

    response = {}
    user = request.cached_user

    if data['TwoFactorAuthEnabled'] != lookup(user, 'settings.TwoFactorAuthEnabled'):
        if data['TwoFactorAuthEnabled']:
            shared_secret = pyotp.random_base32()
            totp = pyotp.TOTP(shared_secret)
            uri = totp.provisioning_uri(
                request.cached_user['username'],
                issuer_name=get_settings('spynl.auth.otp.issuer'),
            )
            if os.getenv('DEBUG'):
                import qrcode

                img = qrcode.make(uri)
                img.save('qr.png', 'png')

            response['2FAProvisioningUri'] = uri
            update = {
                '$set': {
                    'two_factor_shared_secret': shared_secret,
                    'settings.TwoFactorAuthEnabled': True,
                }
            }
        else:
            update = {
                '$set': {'settings.TwoFactorAuthEnabled': False},
                '$unset': {'two_factor_shared_secret': None},
            }
        request.db.users.update_one({'_id': request.authenticated_userid}, update)

    return response
