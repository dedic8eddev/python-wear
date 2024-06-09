"""Tests for the functions in the utils."""

import string
from collections import OrderedDict

import pytest

from spynl.api.hr import utils


@pytest.fixture
def set_db(db):
    """Fill in the database some data for the tests."""
    db.tenants.insert_one(
        {
            '_id': 'tenant1',
            'name': 'BlaTenant',
            'owners': ['owner1_id', 'also_owner1_id'],
        }
    )
    db.tenants.insert_one(
        {'_id': 'tenant2', 'name': 'BluppTenant', 'owners': ['owner2_id']}
    )
    db.users.insert_one(
        {
            '_id': 'user_with_mail_id',
            'email': 'user@blah.com',
            'username': 'user_with_mail',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            '_id': 'user_without_mail_id',
            'username': 'user_without_mail',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            '_id': 'user2_without_mail_id',
            'username': 'user2_without_mail',
            'active': True,
            'tenant_id': ['tenant1', 'tenant2'],
        }
    )
    db.users.insert_one(
        {
            '_id': 'owner1_id',
            'email': 'owner1@tenant1.com',
            'username': 'owner1',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            '_id': 'also_owner1_id',
            'email': 'also_owner1@tenant1.com',
            'username': 'also_owner1',
            'active': True,
            'tenant_id': ['tenant1'],
        }
    )
    db.users.insert_one(
        {
            '_id': 'owner2_id',
            'email': 'owner2@tenant2.com',
            'username': 'owner2',
            'active': True,
            'tenant_id': ['tenant2'],
        }
    )


def test_find_contacts_with_email(set_db, db, spynl_data_db):
    """test user with email address"""
    user = db.users.find_one({'username': 'user_with_mail'})
    emails = utils.find_user_contacts(spynl_data_db, user)
    assert emails == ['user@blah.com']


def test_find_contacts_without_email(set_db, db, spynl_data_db):
    """test user without email address"""
    user = db.users.find_one({'username': 'user_without_mail'})
    emails = utils.find_user_contacts(spynl_data_db, user)
    assert set(emails) == set(['owner1@tenant1.com', 'also_owner1@tenant1.com'])


def test_find_contacts_without_email_dont_set_tenant(set_db, db, spynl_data_db):
    """
    test user without email address and multiple tenants without
    setting the tenant.
    """
    user = db.users.find_one({'username': 'user2_without_mail'})
    emails = utils.find_user_contacts(spynl_data_db, user)
    assert emails == []


def test_find_contacts_without_email_set_tenant(set_db, db, spynl_data_db):
    """
    test user without email address and multiple tenants with
    setting the tenant.
    """
    user = db.users.find_one({'username': 'user2_without_mail'})
    emails = utils.find_user_contacts(spynl_data_db, user, 'tenant1')
    assert set(emails) == set(['owner1@tenant1.com', 'also_owner1@tenant1.com'])
    emails = utils.find_user_contacts(spynl_data_db, user, 'tenant2')
    assert emails == ['owner2@tenant2.com']


@pytest.mark.parametrize(
    'items,error,result',
    [
        ([('a', '')], False, {'a': ''}),
        ([('a', {'b': 'c'})], False, {'a.b': 'c'}),
        ([('a.b', 'c'), ('a', {'b': 'c'})], True, 'a.b'),
        ([('a', {'b': 'c'}), ('a.b', 'c')], True, 'a.b'),  # opposite of previous
        ([('a', {'b': 'c.d'})], False, {'a.b': 'c.d'}),  # Dotted value
        ([('a', {'b': {'c': 4}}), ('d', 5)], False, {'a.b.c': 4, 'd': 5}),
        (
            [('a', {'b': {'c': 4}}), ('d', 5), ('e', {'e': 6})],
            False,
            {'a.b.c': 4, 'd': 5, 'e.e': 6},
        ),
        (
            [('a', {'b': {'c': 3, 'e': 5}, 'c': {'b': 4}})],
            False,
            {'a.b.c': 3, 'a.c.b': 4, 'a.b.e': 5},
        ),
    ],
)
def test_flatten_func(items, error, result):
    """
    Flatten func should return a flatten dict but raise when dublicates.

    Important! The order of the passed dictionary matters thus the OrderedDict
    """
    d = OrderedDict()
    for key, value in items:
        d[key] = value

    if not error:
        assert utils.flatten(d) == result
    else:
        with pytest.raises(Exception) as exc:
            utils.flatten(d)
        assert str(exc.value) == 'Key %s is given more than once.' % result


@pytest.mark.parametrize(
    'items,error,result',
    [
        ([('a', '')], False, {'a': ''}),
        ([('a.b', 'c')], False, {'a': {'b': 'c'}}),
        ([('a.b', 1), ('a', {'b': 1})], True, 'a'),
        ([('a', {'b': 1}), ('a.b', 1)], True, 'a.b'),  # opposite of previous
        ([('a.b', 'c.d')], False, {'a': {'b': 'c.d'}}),  # Dotted value
        ([('a.b.c', 4), ('d', 5)], False, {'a': {'b': {'c': 4}}, 'd': 5}),
        (
            [('a.b.c', 4), ('d', 5), ('e.e', 6)],
            False,
            {'a': {'b': {'c': 4}}, 'd': 5, 'e': {'e': 6}},
        ),
        (
            [('a.b.c', 3), ('a.c.b', 4), ('a.b.e', 5)],
            False,
            {'a': {'b': {'c': 3, 'e': 5}, 'c': {'b': 4}}},
        ),
    ],
)
def test_inflate_func(items, error, result):
    """Inflate func should return a regular dict from dod-notated dict."""
    d = OrderedDict()
    for key, value in items:
        d[key] = value
    if error:
        with pytest.raises(Exception) as exc:
            utils.inflate(d)
        assert str(exc.value) == 'Key %s is given more than once.' % result
    else:
        assert utils.inflate(d) == result


def test_generate_random_cust_id():
    """Must return symbol + 4 chars(lowercase/uppercase/digits)."""
    chars = string.digits + string.ascii_lowercase + string.ascii_uppercase
    symbols = '!#()*+-.'
    id_ = utils.generate_random_cust_id()
    assert len(id_) == 5
    assert id_[0] in symbols
    for char in id_[1:]:
        assert char in chars


def test_generate_random_loyalty_number():
    """Must return 10th length str using digits and/or ascii uppercase."""
    chars = string.digits + string.ascii_uppercase
    id_ = utils.generate_random_loyalty_number()
    assert len(id_) == 10
    for char in id_:
        assert char in chars


@pytest.mark.parametrize(
    "device_id,tenant_id,expected_msg",
    [
        (None, None, 'missing-tenant-id'),
        (
            'foo_device_id',
            'bar_tenant_id',
            'validate-device-id-exists-for-different-tenant',
        ),
    ],
)
def test_validate_device_id_with_bad_tenant_id(
    db, set_db, device_id, tenant_id, expected_msg, spynl_data_db
):
    # This test doesnt need the whole set_db, just 1 doc, but using it cause
    # of the cleaning process. When tests/refactoring is merged then one
    # fixture in conftest will clean the db after every test no matter what
    if tenant_id:
        db.users.insert_one({'tenant_id': [tenant_id], 'deviceId': device_id})
    # TODO fix test: (add dummy request with db)
    with pytest.raises(Exception) as err:
        utils.validate_device_id(spynl_data_db, device_id, tenant_id)
    assert expected_msg in str(err.value)


@pytest.mark.parametrize(
    'username',
    (
        "user..name",
        "a" * 65,
        "#blah",
        "@blah",
        "$blah",
        "=blah",
        "+blah",
        " blah",
        " blah\n",
        ".sdfsdf",
        "-sdfsdf",
        "_sdfdsf",
        "'sdfdsf",
        "shor",
    ),
)
def test_validate_bad_username(username):
    """test bad usernames raise."""
    with pytest.raises(ValueError):
        utils.validate_username(username)


@pytest.mark.parametrize(
    'username',
    (
        "kareem_",
        "kareem.user",
        "kareem-user",
        "kareem\'s-user",
        "kareem\'s-1st-user",
        "098kAreem\'s-1st-user",
    ),
)
def test_validate_username(username):
    """test valid usernames pass."""
    assert utils.validate_username(username)
