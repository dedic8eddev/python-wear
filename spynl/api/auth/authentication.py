"""Deals with passwords authentication, scrambling and resetting."""

import random
from hashlib import md5, sha512

from pbkdf2 import crypt

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import now

# from spynl.api.auth.utils import get_user_info
from spynl.api.auth.exceptions import (
    SpynlPasswordRequirementsException,
    UnrecognisedHashType,
)

HASH_TYPE = '2'


def scramble_password(password, salt='', hash_type=None):
    """
    Check the hash type against what is stored in the user object.

    Will use that type to determine what encryption method to use
    """
    hash_type = hash_type or HASH_TYPE
    if hash_type == '1':
        return md5((password + salt).encode('utf-8')).hexdigest()
    elif hash_type == '2':
        return crypt(password, salt)
    elif hash_type == '3':
        return sha512((password + salt).encode('utf-8')).hexdigest()

    raise UnrecognisedHashType()


def challenge_password(password, scrambled_password, salt='', hash_type=None):
    """Challenge a given password against the existing one."""
    return scrambled_password == scramble_password(
        password, salt=salt, hash_type=hash_type
    )


def set_password(request, user, password, hash_type=None):
    """
    Update the user's password hash.

    Add their current password hash to a history of previously used hashes.
    Do not allow already used password hashes to be used as new ones.
    Keep history of previous password hashes.
    Set a new salt only if user does not have one already.
    """
    hash_type = hash_type or user.get('hash_type') or HASH_TYPE
    salt = user.get('password_salt', salt_generator())
    new_password_hash = scramble_password(password, salt, hash_type)

    older_hashes = [
        item.get('hash')
        for item in user.get('oldPasswords', [])
        if isinstance(item, dict) and item.get('hash_type') == hash_type
    ]
    if user.get('password_hash'):
        older_hashes.append(user['password_hash'])
    if new_password_hash in older_hashes:
        raise SpynlPasswordRequirementsException(
            _('password-does-not-meet-requirements-already-used')
        )

    new_auth_info = {
        'password_hash': new_password_hash,
        'hash_type': hash_type,
        'password_salt': salt,
        'hash_date': now(tz='UTC'),
    }
    record = {
        'hash': user.get('password_hash'),
        'hash_type': user.get('hash_type'),
        'hash_date': user.get('hash_date'),
    }
    update_user = {'$set': new_auth_info, '$push': {'oldPasswords': record}}
    request.db.users.update_one({'username': user['username']}, update_user)


def salt_generator():
    """Generate an alphanumerical salt string."""
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ''.join(random.choice(chars) for i in range(16))


def challenge(
    request, password, username=None, email=None, fallback=None, callback=None
):
    """
    Challenge authentication status of this user.

    Perform a password check and allow for fallback and callback options.
    """
    filtr = {'$or': [{'username': username}, {'email': username}]}
    if username is None:
        filtr = {'email': email}

    user = request.db.users.find_one(filtr)
    if not user:
        if fallback and fallback(username, password) and callback:
            return callback(username, password)
        return False

    if challenge_password(
        password,
        user.get('password_hash'),
        user.get('password_salt'),
        user.get('hash_type'),
    ):
        hash_type = HASH_TYPE
        # rehash the password if the user's hash_type is not conform to the
        # default hash_type
        if hash_type != user.get('hash_type'):
            set_password(request, user, password, hash_type)
        return user['_id']
    return None
