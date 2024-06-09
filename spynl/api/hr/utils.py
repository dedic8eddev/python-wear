"""
Helper functions for spynl.hr.

Current user:
get_user_contacts(user, request): current user

Any user / Any tenant:
find_user_contacts(user, tenant_id=None): any user
find_owner_contact_info(tenant_id): any tenant
send_pwdreset_key(request, user, first=False): any user

Checking functions:
check_roles(roles, role_type): any role(s) (check database)
check_user_type(user_type): any user_type (hard coded)
check_user_belongs_to_tenant(tenant_id, user): any tenant, any user

Create:
create_user(new_user, tenant_id, auth_userid=None, action='create-user'):
"""

import collections
import random
import string

from pymongo.errors import DuplicateKeyError

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException
from spynl.main.mail import send_template_email

from spynl.api.auth.apps_and_roles import ROLES
from spynl.api.auth.exceptions import Forbidden, MissingTenantID
from spynl.api.auth.keys import store_key
from spynl.api.auth.utils import app_url, lookup_tenant, validate_email
from spynl.api.hr.exceptions import ExistingUser
from spynl.api.mongo.utils import get_logger


def validate_username(username):
    """
    Validate a username.

    Raise a ValueError with a descriptive message if a rule is broken.
    """

    allowed = "- _ ' . @".split()

    characters = '"' + '", "'.join(allowed) + '"'
    startswith = _('may-not-start-with', mapping={'characters': characters})
    too_long = _('username-too-long')
    too_short = _('username-too-short')
    invalid_chars = _('invalid-username-characters', mapping={'characters': characters})

    if len(username) > 64:
        raise ValueError(too_long)

    if len(username) < 5:
        raise ValueError(too_short)

    if any([username.startswith(c) for c in allowed]):
        raise ValueError(startswith)

    valid_characters = all(
        [
            (c.isdigit() or c.isalpha() or c in allowed) and not c.isspace()
            for c in username
        ]
    )

    if not valid_characters or '..' in username:
        raise ValueError(invalid_chars)

    return True


def create_user(request, new_user, tenant_id, auth_userid=None, action='create-user'):
    """
    Create a user in the database.

    Pass an initial user dict with at least the username and type.
    Also pass the tenant ID this user should have.
    Returns the new user dict as it exists in the database.
    """
    if not new_user:
        raise SpynlException(
            'Need an initial user dict to proceed with creating a user.'
        )
    username = new_user.get('username')
    if not username:
        raise SpynlException('User dict needs at least a username.')
    try:
        validate_username(username)
    except ValueError as e:
        raise SpynlException(e.args[0])

    if not new_user.get('type'):
        raise SpynlException('User dict needs to have a user type.')
    if not new_user.get('roles'):
        new_user['roles'] = {}
    # validity checks
    email = new_user.get('email')
    if email:
        validate_email(new_user['email'])
    check_user_type(new_user.get('type'))
    if new_user.get('deviceId'):
        validate_device_id(request.db, new_user['deviceId'], tenant_id)
    for t, role_dict in new_user['roles'].items():
        if 'tenant' in role_dict:
            check_roles(role_dict['tenant'], 'tenant')

    if not new_user.get('fullname'):
        # taking a good guess
        new_user['fullname'] = username

    # make sure important fields exist and are defaulted
    new_user['active'] = True
    new_user['tz'] = 'Europe/Amsterdam'
    if tenant_id:
        new_user['tenant_id'] = [tenant_id]
    try:
        request.db.users.insert_one(new_user)
    except DuplicateKeyError as e:
        if new_user.get('email') and new_user['email'] in e.args[0]:
            raise ExistingUser(email=email)
        else:  # Otherwise it should be username
            raise ExistingUser(username=username)
    return new_user


def get_user_contacts(user, request):
    """
    Return email addresses to be notified about relevant actions for the user.

    Use for the logged-in user, otherwise use find_user_contacts.

    If the user has an email address, we take that.
    Otherwise, we return email addresses of the owners of the current tenant
    which the user is working on.
    """
    email_adrs = [user.get('email')]
    if not email_adrs[0]:
        tenant = lookup_tenant(request.db, request.current_tenant_id)
        # TODO: we can also use find_owner_contact_info here, and refactor the
        # code that calls this function to also use the fullname in the email to
        # address the owner.
        email_adrs = [
            user['email']
            for user in request.db.users.find(
                {'_id': {'$in': tenant.get('owners', [])}}, ['email']
            )
        ]
    return list(email_adrs)


def find_user_contacts(db, user, tenant_id=None):
    """
    Return email addresses to be notified for a non-logged-in user.

    For the logged in user, use get_user_contacts

    If the user has and email address, we take that.
    Otherwise, we return the email addresses of the owners of its tenant. If
    the user has multiple tenants, we return the addresses of the owners of the
    tenant_id that was provided. If no tenant_id was provided, and the user
    has no email address and multiple tenants, we return an empty list.
    """
    email_adrs = [user.get('email')]
    if not email_adrs[0]:
        tenants = user.get('tenant_id', [])
        # if one tenant look up that tenant
        if len(tenants) == 1:
            tenant_id = tenants[0]
        # if the user has more than one tenant, and the tenant_id is not
        # specified, return an empty list.
        elif tenant_id not in tenants:
            return []
        # Now we have one tenant_id, look up the tenant
        tenant = lookup_tenant(db, tenant_id)
        # TODO: we can also use find_owner_contact_info here, and refactor the
        # code that calls this function to also use the fullname in the email to
        # address the owner.
        email_adrs = [
            user['email']
            for user in db.users.find(
                {'_id': {'$in': tenant.get('owners', [])}}, ['email']
            )
        ]
    return list(email_adrs)


def find_owner_contact_info(db, tenant_id):
    """
    Return a dictionary of all owners with their email addresses and fullnames
    """
    logger = get_logger()

    tenant = lookup_tenant(db, tenant_id)

    contact_info = {}
    # loop over all owners:
    for owner_id in tenant.get('owners', []):
        owner = db.users.find_one({'_id': owner_id})
        # log warning if owner could not be retrieved:
        if not owner:
            logger.warning(
                'Could not retrieve owner %s of tenant %s', owner_id, tenant_id
            )
        # TODO: also warn if owner is missing email or fullname?
        else:
            contact_info[owner_id] = {
                'email': owner.get('email', None),
                'fullname': owner.get('fullname', None),
            }
    return contact_info


def check_roles(roles, role_type=None):
    """Check if the roles exist."""
    for role in roles:
        if role not in ROLES:
            raise SpynlException('Unknown role: {}'.format(role))
        if role_type is not None:
            if ROLES[role]['type'] != role_type:
                raise SpynlException('Role {} is not type {}'.format(role, role_type))


def check_user_type(user_type):
    """
    Check if the provided user type is a type allowed by Spynl.
    TODO: can be removed when we have data model checks for the user collection.
    """
    allowed_types = ('device', 'api', 'standard')
    if user_type not in allowed_types:
        raise SpynlException('{} is not an accepted user type'.format(user_type))


def check_user_belongs_to_tenant(tenant_id, user):
    """
    Takes a user dictionary and checks if the user belongs to the tenant
    with the given tenant ID.
    """
    if not tenant_id:
        raise MissingTenantID()
    if tenant_id not in user.get('tenant_id', []):
        raise SpynlException(
            'This user does not belong to the requested tenant (%s).' % tenant_id
        )


def validate_device_id(db, device_id, tenant_id):
    """Validate uniqueness of device's id."""
    if not tenant_id:
        raise MissingTenantID()
    query = {'deviceId': device_id, 'tenant_id': {'$in': [tenant_id]}}
    if db.users.find_one(query) is not None:
        raise Forbidden(
            _(
                'validate-device-id-exists-for-different-tenant',
                mapping={'device_id': device_id},
            )
        )


def send_pwdreset_key(request, user, first=False):
    """
    Send user (or tenant owners) a mail with a key to reset their password.

    param user: user whose password is to be reset
    param first: True if this email is the first this user gets (on
                 account creation)
    The key will be valid for 48 hours.
    Return the email addresses it successfully sent the key to.
    """
    code = store_key(request.db, user['_id'], 'pwd_reset', 48 * 3600)

    emails_sent = []
    emails = find_user_contacts(request.db, user)
    if emails == []:
        raise SpynlException(_('no-email-found'))

    # please also change the send_all_templates endpoint if you change
    # anything here.
    replacements = {
        'key': code,
        'app_url': app_url(request, 'www'),
        'username': user.get('username'),
        'user_greeting': user.get('fullname', user['username']),
        'first_reset': first,
    }
    for email in emails:
        if send_template_email(
            request, email, template_file='password_reset', replacements=replacements
        ):
            emails_sent.append(email)
    return emails_sent


def flatten(d, parent_key='', sep='.'):
    """flatten a dictionary into (dot)-notation for all possible paths"""

    def _flatten(d, parent_key='', sep='.'):
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, collections.abc.MutableMapping):
                yield from _flatten(v, new_key, sep=sep)
            else:
                yield (new_key, v)

    flat_d = {}
    for key, value in _flatten(d, parent_key=parent_key, sep=sep):
        if key in flat_d.keys():
            raise SpynlException('Key %s is given more than once.' % key)
        flat_d[key] = value
    return flat_d


def inflate(d, sep='.'):
    """inflate a list from (dot)-notation into a dictionary"""
    # TODO: Function is too complicated
    items = dict()
    for k, v in d.items():
        keys = k.split(sep)
        tmp_d = items  # Check if nested key given more than once
        for key in keys:
            try:
                tmp_d[key]
                tmp_d = tmp_d[key]
            except KeyError:
                break
        else:
            raise SpynlException('Key %s is given more than once.' % k)
        sub_items = items
        for ki in keys[:-1]:
            try:
                sub_items = sub_items[ki]  # Become the nested if exists
            except KeyError:
                sub_items[ki] = dict()  # Create the nested dict
                sub_items = sub_items[ki]  # Become the nested dict

        sub_items[keys[-1]] = v
    return items


def generate_random_cust_id():
    """
    Return a 5 random string which represents the cust_id of a customer.

    It needs to be created because FoxPro needs a unique cust_id for every
    customer.
    The 1st character is a symbol, followed by 4 ascii lowercase characters.
    """
    chars = string.digits + string.ascii_lowercase + string.ascii_uppercase
    symbol = random.choice('!#()*+-.')
    return symbol + ''.join(random.choice(chars) for _ in range(4))


def generate_random_loyalty_number():
    """
    Return a random string to be used as the loyalty number for a customer.

    It needs to be created because FoxPro needs a unique loyalty number for
    every customer so for example points can be added from a shop.
    The string contains digits and ascii uppercase characters.
    """
    return ''.join(
        random.choice(string.digits + string.ascii_uppercase) for _ in range(10)
    )


def find_unused(collection, key, callback):
    """
    Small internal helper for finding a document with a value that does
    not yet exist.
    """
    for i in range(100):
        value = callback()
        if not collection.count_documents({key: value}):
            return value

    raise SpynlException(_('cannot-find-next-incremental-id'))
