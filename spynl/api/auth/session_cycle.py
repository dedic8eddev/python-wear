"""
Endpoints for managing a session life cycle:

* login
* logout
* set_tenant
* validate_session
* logged_in_user
"""

import json
import re
from datetime import datetime, timedelta, timezone

import jwt
import pyotp
import requests
from bson import ObjectId
from marshmallow import fields, pre_load, validates_schema
from pyramid.security import forget, remember
from pyramid.settings import asbool

from spynl_schemas import Schema, User, lookup

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import now
from spynl.main.exceptions import SpynlException
from spynl.main.utils import get_settings, required_args

from spynl.api.auth.apps_and_roles import APPLICATIONS
from spynl.api.auth.authentication import challenge
from spynl.api.auth.exceptions import (
    ExpiredCredentials,
    ForbiddenTenant,
    NoActiveTenantsFound,
    TenantNotActive,
    UserNotActive,
    WrongCredentials,
)
from spynl.api.auth.tenantid_utils import get_allowed_tenant_ids
from spynl.api.auth.utils import (
    MASTER_TENANT_ID,
    find_tenants,
    find_user,
    get_default_application,
    get_tenant_roles,
    get_user_info,
    lookup_tenant,
)

# This is the whitelist used for read-based action.
# Some of these are cleaned before being returned, e.g. 'roles'
USER_DATA_WHITELIST = (
    'email',
    '_id',
    'reportacls',
    'tz',
    'username',
    'active',
    'fullname',
    'tenant_id',
    'type',
    'roles',
    'default_application',
    'favorites',
    'language',
    'email_verify_pending',
    'wh',
    'deviceId',
    'created',
    'modified',
    'last_login',
)
# This is the whitelist used for the general editing of users (_update_user)
USER_EDIT_ME_WHITELIST = ('fullname', 'tz', 'language')

USER_EDIT_WHITELIST = USER_EDIT_ME_WHITELIST + (
    'reportacls',
    'favorites',
    'wh',
    'deviceId',
)
# These fields need to be treated in a special way, because
# they may contain data from tenants that the current user has no access to
TENANT_FIELDS = ('roles', 'default_application')


def get_cookie_domain(request):
    # drop the spynl subdomain
    try:
        _, domain = request.domain.split('.', 1)
    except ValueError:
        domain = request.domain
    return domain


def set_cookie(request, expire, sid, user):
    now_ = datetime.now(timezone.utc)
    cookie_age = (expire - now_).total_seconds()
    cookie_domain = get_cookie_domain(request)
    request.response.set_cookie(
        'sid', value=sid, max_age=cookie_age, domain=cookie_domain
    )
    # Remember the language forever. Unless the user logs out.
    request.response.set_cookie(
        'lang', value=user.get('language'), domain=cookie_domain
    )


class LoginSchema(Schema):
    username = fields.String(
        required=True,
        metadata={'description': 'Can be either the username or the email of a user.'},
    )
    password = fields.String(required=True)
    remember_me = fields.Bool(load_default=False)

    @pre_load
    def handle_boolean(self, data, **kwargs):
        try:
            data['remember_me'] = asbool(data['remember_me'])
        except KeyError:
            pass
        return data

    @validates_schema
    def authenticate(self, data, **kwargs):
        if not challenge(
            self.context['request'], data['password'], username=data['username']
        ):
            user = self.context['request'].db.users.find_one(
                {'$or': [{'username': data['username']}, {'email': data['username']}]}
            )
            if user:
                self.context['request'].pymongo_db.users.update_one(
                    {'_id': user['_id']}, {'$inc': {'failed_login': 1}}
                )
            raise WrongCredentials()


def login(request):
    """
    Login a user.


    ---
    post:
      description: >
        Login to spynl. A tenant gets set for the user
        automatically. If a user has more than one tenant the first
        active tenant gets set. If a user has no active tenants they cannot
        login.

        If a user has two factor authorization enabled, a TFA token is returned,
        the login process can then be completed using the /validate-otp endpoint.
      tags:
        - session
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'login.json#/definitions/LoginSchema'
      responses:
        200:
          description: Logged in response
          schema:
            type: object
            properties:
              2FAToken:
                type: string
                description: >
                  If this is returned the 2FA flow is required,
                  where this token needs to be provided.
              _id:
                type: string
                description: the user id
              username:
                type: string
                description: the username
              email:
                type: string
                description: the users email address
              type:
                type: string
                description: The type of user account
              current_tenant:
                type: string
                description: The currently set tenant for this session
              sid:
                type: string
                description: The session id
              tenants:
                description: The tenants the user belongs to.
                type: array
                items:
                  type: object
                  properties:
                    _id:
                      type: string
                    name:
                      type: string
    """
    data = LoginSchema(context={'request': request}).load(request.args)
    user = find_user(request.db, data['username'], search_email=True)

    # The user provided the correct credentials, now we check if the
    # user account is actually active. Do not log in if the user is not
    # active:
    if not user.get('active', True):
        raise UserNotActive(user['username'])

    if user.get('two_factor_shared_secret'):
        return {
            # this token needs to be sent back to verify and link the two
            # seperate requests together.
            '2FAToken': jwt.encode(
                {
                    'exp': datetime.utcnow() + timedelta(minutes=5),
                    'user_id': str(user['_id']),
                    'remember_me': data['remember_me'],
                },
                key=get_settings('spynl.auth.otp.jwt.secret_key'),
                algorithm='HS256',
            )
        }

    return do_login(request, user=user, remember_me=data['remember_me'])


class TwoFactorAuthSchema(Schema):
    _2FAToken = fields.String(
        required=True,
        data_key='2FAToken',
        metadata={
            'description': 'The token used to link the login request and the 2fa '
            'request'
        },
    )
    _2FAOtp = fields.String(
        required=True,
        data_key='2FAOtp',
        metadata={
            'description': 'The One Time Password used to authenticate the user, '
            'provided by the 2FA app'
        },
    )


def validate_otp(ctx, request):
    """
    Authenticate the user with a one time password.

    ---
    post:
      description: >
        Authenticate the user with a one time password.
      tags:
        - session
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'two_factor_auth.json#/definitions/TwoFactorAuthSchema'
      responses:
        200:
          description: Logged in response
          schema:
            type: object
            properties:
              _id:
                type: string
                description: the user id
              username:
                type: string
                description: the username
              email:
                type: string
                description: the users email address
              type:
                type: string
                description: The type of user account
              current_tenant:
                type: string
                description: The currently set tenant for this session
              sid:
                type: string
                description: The session id
              tenants:
                description: The tenants the user belongs to.
                type: array
                items:
                  type: object
                  properties:
                    _id:
                      type: string
                    name:
                      type: string
    """
    settings = get_settings()

    # For some reason the json_payload request property is not available here
    try:
        data = request.json_body
    except json.decoder.JSONDecodeError:
        data = {}

    data = TwoFactorAuthSchema().load(data)

    try:
        payload = jwt.decode(
            data['_2FAToken'].encode('u8'),
            key=settings['spynl.auth.otp.jwt.secret_key'],
            algorithms=['HS256'],
        )
    except jwt.ExpiredSignatureError:
        raise ExpiredCredentials()
    except jwt.DecodeError:
        raise SpynlException(_('invalid-jwt-token'))

    user = request.db.users.find_one({'_id': ObjectId(payload['user_id'])})

    totp = pyotp.TOTP(user['two_factor_shared_secret'])
    otp = re.sub(r'\s', '', data['_2FAOtp'])
    if totp.verify(otp):
        return do_login(request, user, payload['remember_me'])

    raise WrongCredentials()


def do_login(request, user, remember_me):
    """Perform the login and set the cookies"""
    tenants = find_tenants(request.db, user.get('tenant_id', []))
    try:
        tenant_id = [t for t in tenants if t.get('active', True)][0]['_id']
    except IndexError:
        raise NoActiveTenantsFound

    # Make sure the new user does not inherit an older session that could
    # exist on their computer
    session = request.session
    if (
        request.authenticated_userid is not None
        and request.authenticated_userid != user['_id']
    ):
        session.invalidate()
        session.__init__()

    # login succesful, reset count and store last_login date
    request.pymongo_db.users.update_one(
        {'_id': user['_id']}, {'$set': {'failed_login': 0, 'last_login': now(tz='UTC')}}
    )

    user_info = get_user_info(request)
    session['username'] = user.get('username')
    session['remote_addr'] = user_info['ipaddress']
    session['tenant_id'] = tenant_id

    if remember_me and MASTER_TENANT_ID not in user.get('tenant_id', []):
        session.remember_me = True
        cookie_age_days = 30
    else:
        # This is needed in case a user logs in while still logged in and
        # chooses False when remember_me was True before.
        session.remember_me = False
        cookie_age_days = 1

    now_ = datetime.now(timezone.utc)

    # expire at midnight
    expire = now_.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
        days=cookie_age_days
    )
    session.expire = expire

    set_cookie(request, expire, session.id, user)

    headers = remember(request, user['_id'])
    request.response.headerlist.extend(headers)

    return {
        'tenants': [{'id': t['_id'], 'name': t.get('name', '')} for t in tenants],
        'current_tenant': tenant_id,
        'sid': session.id,
        '_id': user.get('_id'),
        'username': user.get('username'),
        'email': user.get('email'),
        'type': user.get('type'),
    }


def logout(request):
    """
    Logout the authenticated user.

    ---
    post:
      description: Deletes the session and the cookie.
      tags:
        - session
    """
    latestcollection_url = get_settings('spynl.latestcollection.url')
    masterToken = get_settings('spynl.latestcollection.master_token')
    spynl_sid = request.cookies.get('sid')
    lc_response = 0
    try:
        res = requests.delete(
            f"{latestcollection_url}/data/me?id={spynl_sid}&token={masterToken}"
        )
        lc_response = res.status_code
    except requests.exceptions.RequestException:
        lc_response = 0

    if request.session:
        request.session.invalidate()
    forget(request)
    request.response.delete_cookie('sid', domain=get_cookie_domain(request))

    return {'lc_response': lc_response}


def validate_session(request):
    """
    Check if session is valid or not.

    ---
    post:
      description: >
        If you have a valid session for this Spynl instance,
        then the response will have status='ok',
        otherwise status='error' (meaning you are not authenticated).
        The only required parameter is "sid", the session ID.
        It will be sent from cookies automatically by browsers.

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error'\n
        sid       | string | session ID\n
        message   | string | error description\n

      tags:
        - session
    """
    userid = request.authenticated_userid
    if userid:
        return {'status': 'ok', 'sid': request.headers['sid']}
    else:
        return {'status': 'error', 'message': _('invalid-session')}


@required_args('id')
def set_tenant(request):
    """
    Set tenant ID for the ongoing session.

    ---
    post:
      description: >
        Set a tenant for the user to use during this session.
        The only required parameter is "id", the tenant's ID.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        id        | string       | &#10004; | Tenant ID\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        roles | list | list of tenant roles which the user has for this
        tenant\n
        default_application | string | id of the default application for the
        user for this tenant\n

      tags:
        - session
    """
    tenant_id = request.args['id']
    users_tenants = get_allowed_tenant_ids(request)
    if tenant_id not in users_tenants:
        raise ForbiddenTenant()
    tenant = lookup_tenant(request.db, tenant_id)
    if tenant.get('active') not in (True, None):
        raise TenantNotActive(tenant_id)

    user = get_user_info(request)

    # make a new session, but keep the expire of the old session. Otherwise you could
    # keep switching tenants to extend the 30 days max login:
    session = request.session
    try:
        previous_expire = session.expire
    except KeyError:
        raise SpynlException(_('old-style-session'))
    previous_remember = session.remember_me
    session.invalidate()
    session.__init__()
    session['tenant_id'] = tenant_id
    session['username'] = user.get('username')
    session['remote_addr'] = user['ipaddress']
    session.expire = previous_expire
    session.remember_me = previous_remember

    set_cookie(request, session.expire, session.id, user)

    headers = remember(request, user['_id'])
    request.response.headerlist.extend(headers)

    return {
        'roles': get_tenant_roles(
            request.db, request.cached_user, tenant_id, restrict=True
        ),
        'default_application': get_default_application(
            request.db, request.cached_user, tenant_id
        ),
        'sid': session.id,
    }


favorites_example = {
    'favorites': {
        'reports': [
            {
                'settings': {
                    'selectedgroupers': [],
                    'filters': {},
                    'selectionRange0': '20100101230059',
                    'selectionRange1': '20170101000000',
                },
                'report_id': '74455dfc-1005-4cc0-a94c-b6e5653f7105',
                'name': 'Verkopen per klant',
                'description': '21-10-19',
                'favorite_id': '6da7eb793ca4474a8078a52602ccad92',
            }
        ]
    }
}


def get_primary_address(tenant):
    for address in tenant.get('addresses', []):
        if address.get('primary'):
            return address
    return None


class LoggedInUserDocumentation(User):
    # keys that should be in the user document, but are not yet in there:
    favorites = fields.Dict(
        metadata={
            'description': 'favorites for softwear6 reporting. example:'
            '\n```\n {} \n```\n'.format(json.dumps(favorites_example, indent=4))
        }
    )
    email_verify_pending = fields.Boolean(
        metadata={'description': 'If true, the user still needs to verify their email.'}
    )
    last_login = fields.DateTime()

    # overwrite documentation
    wh = fields.String(metadata={'description': 'only added for devices'})
    deviceId = fields.String(metadata={'description': 'only added for devices'})

    # keys added by function
    tenants = fields.List(
        fields.Dict,
        metadata={
            'description': 'List of objects, one for each tenant the user belongs to. '
            'object contains the following keys: id (string), name (string), retail '
            '(boolean), wholesale (boolean), address (object).'
        },
    )
    current_tenant = fields.String()
    roles = fields.Dict(
        metadata={
            'description': "object with tenant_id's as keys, and a list of "
            'corresponding roles as values.'
        }
    )
    applications = fields.Dict(
        metadata={
            'description': 'object with all apps as keys, with a boolean as a value '
            'to say if the user has access.'
        }
    )

    class Meta(User.Meta):
        exclude = [
            *list(set(User().fields.keys()) - set(USER_DATA_WHITELIST)),
            'tenant_id',
        ]


def logged_in_user(ctx, request):
    """
    Info about the currently logged-in user.

    ---
    get:
      description: >
        Returns a data dict with user information, sensitive data removed.
        Data also contains 'current_tenant' if one has been set and the
        allowed tenants with their id and name.


      responses:
        "200":
          schema:
            type: object
            properties:
              status:
                type: string
              data:
                $ref: 'logged_in_user.json#/definitions/LoggedInUserDocumentation'
      tags:
        - session
    """

    response = {
        k: v for k, v in request.cached_user.items() if k in USER_DATA_WHITELIST
    }

    if response.get('type') != 'device':
        response.pop('wh', None)
        response.pop('deviceId', None)

    tenants = list(
        request.db.tenants.pymongo_find({'_id': {'$in': response.pop('tenant_id')}})
    )
    response.update(
        {
            'tenants': sorted(
                [
                    {
                        'id': t['_id'],
                        'name': t.get('name', ''),
                        'retail': t.get('retail', False),
                        'wholesale': t.get('wholesale', False),
                        'address': get_primary_address(t),
                    }
                    for t in tenants
                ],
                key=lambda t: request.cached_user['tenant_id'].index(t['id']),
            ),
            'current_tenant': request.current_tenant_id,
            'roles': {},
            'applications': {},
        }
    )

    for tenant in tenants:
        restrict = tenant['_id'] != MASTER_TENANT_ID
        response['roles'][tenant['_id']] = get_tenant_roles(
            request.db, request.cached_user, tenant['_id'], restrict=restrict
        )

    # Return all internal apps for master users:
    if request.current_tenant_id == MASTER_TENANT_ID:
        response['applications'] = {
            k: v.get('internal', False) for k, v in APPLICATIONS.items()
        }

    # For normal users, only return the apps they have a role for:
    else:
        user_apps = [
            r.split('-')[0] for r in response['roles'][request.current_tenant_id]
        ]
        for app, data in APPLICATIONS.items():
            if data.get('link'):
                user_settings = request.cached_user.get('settings', {})
                response['applications'][app] = lookup(
                    user_settings, 'applicationLinks.{}'.format(app), False
                )
            else:
                response['applications'][app] = app in user_apps

    # Set dashboard app for owners
    for tenant in tenants:
        if (
            response['current_tenant'] == tenant['_id']
            and 'owner' in response['roles'][tenant['_id']]
            and 'dashboard' in tenant['applications']
        ):
            response['applications']['dashboard'] = True
            break

    return {'data': response}
