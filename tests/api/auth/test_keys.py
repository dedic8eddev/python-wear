"""Tests for spynl.auth.keys functions."""

from datetime import datetime, timedelta

import pytest
import pytz

from spynl.api.auth.authentication import scramble_password
from spynl.api.auth.keys import check_key, remove_key, store_key


@pytest.fixture(autouse=True)
def set_db(db):
    """Fill the database with data for tests to have."""
    db.tenants.insert_one({'_id': 'tenant1', 'name': 'Tenant Eins'})
    db.users.insert_one(
        {
            'email': 'blahuser@blah.com',
            'username': 'blahuser',
            'password_hash': scramble_password('blah', 'blah', '2'),
            'password_salt': 'blah',
            'default_application': 'defApp',
            'hash_type': '2',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            'email': 'blahuser2@blah.com',
            'username': 'blahuser2',
            'password_hash': scramble_password('blah2', 'blah2', '1'),
            'password_salt': 'blah',
            'hash_type': '1',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            'email': 'blahuser3@blah.com',
            'username': 'blahuser3',
            'password_hash': scramble_password('blah3', 'blah3', '2'),
            'password_salt': 'blah',
            'hash_type': '2',
            'active': False,
            'tenant_id': ['tenant1'],
        }
    )


def test_store_key(db, config, spynl_data_db):
    """Test the store_key function."""
    seconds = 24 * 3600
    email = 'blahuser@blah.com'
    user = db.users.find_one({'email': email})
    user_id = user['_id']
    key_type = 'pwd_reset'
    created = datetime.utcnow().replace(tzinfo=pytz.utc)
    expires = created + timedelta(seconds=seconds)
    store_key(spynl_data_db, user_id, key_type, seconds)
    user = db.users.find_one({'email': email})
    keys = user['keys']
    assert key_type in keys
    assert keys[key_type]['key'] is not None
    # check that the times are the same within a second
    assert (
        created - timedelta(seconds=1)
        <= keys[key_type]['created']
        <= created + timedelta(seconds=1)
    )
    assert (
        expires - timedelta(seconds=1)
        <= keys[key_type]['expires']
        <= expires + timedelta(seconds=1)
    )

    # check that old keys get stored and all other values get overwritten
    old_key = user['keys'][key_type]['key']
    old_created = keys[key_type]['created']
    old_expires = keys[key_type]['expires']
    store_key(spynl_data_db, user_id, key_type, seconds)
    user = db.users.find_one({'email': email})
    keys = user['keys']
    assert keys[key_type]['key'] != old_key
    assert keys[key_type]['created'] != old_created
    assert keys[key_type]['expires'] != old_expires
    assert keys[key_type]['oldkeys'][0] == old_key
    old_key2 = user['keys'][key_type]['key']

    store_key(spynl_data_db, user_id, key_type, seconds)
    user = db.users.find_one({'email': email})
    keys = user['keys']
    assert keys[key_type]['oldkeys'] == [old_key, old_key2]


def test_check_keys(db, config, spynl_data_db):
    """Test check_key function with several keys, without duration."""
    email = 'blahuser@blah.com'
    user = db.users.find_one({'email': email})
    user_id = user['_id']
    key_type = 'check'
    seconds = 24 * 3600
    store_key(spynl_data_db, user_id, key_type, seconds)
    invalid_key = 'abcdefg'
    result = check_key(db, user_id, key_type, invalid_key)
    assert not result['exists']
    assert not result['valid']

    user = db.users.find_one({'email': email})
    first_key = user['keys'][key_type]['key']
    result = check_key(db, user_id, key_type, first_key)
    assert result['exists']
    assert result['valid']
    result = check_key(db, user_id, 'invalid', first_key)
    assert not result['exists']
    assert not result['valid']
    store_key(spynl_data_db, user_id, key_type, seconds)
    result = check_key(db, user_id, key_type, first_key)
    assert result['exists']
    assert not result['valid']


def test_check_key_expiration(db, config, spynl_data_db):
    """Check that the key expires after the specified duration."""
    email = 'blahuser@blah.com'
    user = db.users.find_one({'email': email})
    user_id = user['_id']
    key_type = 'duration'
    seconds = 2
    store_key(spynl_data_db, user_id, key_type, seconds)
    user = db.users.find_one({'email': email})
    short_key = user['keys'][key_type]['key']
    result = check_key(db, user_id, key_type, short_key)
    assert result['exists']
    assert result['valid']
    keys = user['keys']
    keys[key_type]['expires'] -= timedelta(seconds=3)
    db.users.update_one({'email': email}, {'$set': {'keys': keys}})
    result = check_key(spynl_data_db, user_id, key_type, short_key)
    assert result['exists']
    assert not result['valid']


def test_remove_key(db, config, spynl_data_db):
    """
    Check that a key gets removed.

    And that there are no problems if the key does not exist.
    """
    email = 'blahuser@blah.com'
    user = db.users.find_one({'email': email})
    user_id = user['_id']
    key_type = 'remove'
    remove_key(spynl_data_db, user_id, key_type)
    # no error if key field is not present?
    keys = {'remove': {'oldkeys': [], 'created': 'bla'}}
    db.users.update_one({'email': email}, {'$set': {'keys': keys}})
    remove_key(db, user_id, 'remove')
    # now test actual removing
    key = store_key(spynl_data_db, user_id, key_type, 3600)
    user = db.users.find_one({'email': email})
    assert user['keys'][key_type]['key'] == key
    remove_key(spynl_data_db, user_id, key_type)
    user = db.users.find_one({'email': email})
    assert user['keys'][key_type]['key'] is None
    assert user['keys'][key_type]['oldkeys'] == [key]
    # test if second key gets stored in oldkeys
    key2 = store_key(spynl_data_db, user_id, key_type, 3600)
    user = db.users.find_one({'email': email})
    assert user['keys'][key_type]['key'] == key2
    assert user['keys'][key_type]['oldkeys'] == [key]
    remove_key(spynl_data_db, user_id, key_type)
    user = db.users.find_one({'email': email})
    assert user['keys'][key_type]['key'] is None
    assert user['keys'][key_type]['oldkeys'] == [key, key2]


def test_none_is_not_valid_key_after_remove(db, config, spynl_data_db):
    """You should never be able to use None as a valid key"""
    email = 'blahuser@blah.com'
    user = db.users.find_one({'email': email})
    user_id = user['_id']
    key_type = 'remove'
    store_key(spynl_data_db, user_id, key_type, 3600)
    remove_key(spynl_data_db, user_id, key_type)
    result = check_key(db, user_id, key_type, None)
    assert not result['exists']
    assert not result['valid']
