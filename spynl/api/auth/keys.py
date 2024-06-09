# coding=UTF8
"""
Functions to store, check and remove keys.
store_key stores a key of type key_type, check_key checks if the key is
valid and/or expired. After the key has been successfully used, it should
be removed with remove_key.
"""

import string
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import Crypto.Random.random as secure_random

from spynl.main.utils import get_logger

from spynl.api.auth.exceptions import CannotRetrieveUser

KEY_LENGTH = 25


def store_key(db, user_id, key_type, duration):
    """
    Store a key into the user's keys property.

    Store a key of a specific type for a user, use the duration in seconds to
    compute the expiration date of the key.
    """
    user = db.users.find_one({'_id': user_id})

    # initialise keys entry if needed
    if 'keys' in user:
        keys = user['keys']
        if key_type not in keys:
            keys[key_type] = defaultdict()
    else:
        keys = defaultdict()
        keys[key_type] = defaultdict()

    # store the old key in oldkeys list if it exists
    if 'key' in keys[key_type] and keys[key_type]['key'] is not None:
        if 'oldkeys' in keys[key_type]:
            keys[key_type]['oldkeys'].extend([keys[key_type]['key']])
        else:
            keys[key_type]['oldkeys'] = [keys[key_type]['key']]

    created = datetime.now(timezone.utc)
    keys[key_type]['created'] = created
    keys[key_type]['expires'] = created + timedelta(seconds=duration)

    code = "".join(
        secure_random.choice(string.ascii_letters + string.digits)
        for x in range(KEY_LENGTH)
    )
    keys[key_type]['key'] = code
    db.users.update_one({'_id': user_id}, {'$set': {'keys': keys}})

    return code


def check_key(db, user_id, key_type, try_key):
    """
    Check if a key is valid.

    Check if a key of a certain type is valid. Returns two booleans, one to
    check if it exists, and one to say if it is still valid.
    """
    if try_key is None or try_key == '':
        return {'exists': False, 'valid': False}

    if len(try_key) != KEY_LENGTH:
        return {'exists': False, 'valid': False}

    user = db.users.find_one({'_id': user_id})
    if not user:
        raise CannotRetrieveUser()

    if 'keys' in user and key_type in user['keys']:
        key = user['keys'][key_type]
    else:
        return {'exists': False, 'valid': False}

    if try_key == key['key']:
        if not key['expires']:
            exists = False
            valid = False
        else:
            exists = True
            now = datetime.now(timezone.utc)
            valid = key['expires'] > now
    else:
        valid = False
        exists = try_key in key.get('oldkeys', [])

    return {'exists': exists, 'valid': valid}


def remove_key(db, user_id, key_type):
    """
    Remove a key of a specific type.

    A key of type key_type is removed and added to oldkeys. This function can
    be used to remove keys after they've been used.
    """
    log = get_logger()
    user = db.users.find_one({'_id': user_id})

    if 'keys' in user:
        keys = user['keys']
        if (
            key_type in keys
            and 'key' in keys[key_type]
            and keys[key_type]['key'] is not None
        ):
            if 'oldkeys' in keys[key_type]:
                keys[key_type]['oldkeys'].extend([keys[key_type]['key']])
            else:
                keys[key_type]['oldkeys'] = [keys[key_type]['key']]
            keys[key_type]['key'] = None
            keys[key_type]['expires'] = None
            db.users.update_one({'_id': user_id}, {'$set': {'keys': keys}})
        else:
            log.error(
                'Tried to remove non-existent %s key for user %s',
                key_type,
                user['username'],
            )
    else:
        log.error(
            'Tried to remove non-existent %s key for user %s',
            key_type,
            user['username'],
        )
