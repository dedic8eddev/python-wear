"""Tests for mongo utils."""


import datetime

from spynl.api.mongo.utils import (
    db_safe_dict,
    get_filter_keys,
    get_first_keys_of_indexes,
)


def test_flat_clean():
    """Pass a flat/simple dictionary."""
    data = {'body': {'username': 'maddoxx.aveen', 'posToken': '1', 'sid': '2'}}
    assert db_safe_dict(data) == data


def test_flat_dirty():
    """Pass a dictionary with $ operator."""
    data = {'body': {'username': 'maddoxx.aveen', 'posToken': '1', '$sid': '2'}}
    assert 'dbm:$sid' in db_safe_dict(data)['body']
    assert '$sid' not in db_safe_dict(data)['body']


def test_deep():
    """Pass a dictionary with multiple operator."""
    data = {'filter': {'$or': [{'_id': {'$in': ['54']}}, {'_id': {'$exists': False}}]}}
    output = {
        'filter': {
            'dbm:$or': [{'_id': {'dbm:$in': ['54']}}, {'_id': {'dbm:$exists': False}}]
        }
    }
    assert db_safe_dict(data) == output


def test_get_first_keys_of_indexes():
    """It should return only the first key of the multikey."""
    indexes = {
        '_id_1': {'key': [('_id', 1)], 'ns': 'database_name.collection_name', 'v': 1}
    }
    result = get_first_keys_of_indexes(indexes)
    assert result == {'_id'}


def test_get_first_keys_of_indexes_function():
    """
    Create double key index where the first key exists as index.

    The function should return the set of first key indexes and not duplicates.
    """
    indexes = {
        'created.utc_date_str_-1': {
            'key': [('confirmed', 1.0), ('created.utc_date_str', -1.0)],
            'ns': 'database_name.collection_name',
            'v': 1,
        }
    }
    result = get_first_keys_of_indexes(indexes)
    assert result == {'confirmed'}


def test_get_filter_keys_with_key_operator():
    """Return only the field keys not the operators."""
    filtr = {'$or': [{'name': 'TypeB'}, {'fullname': 'TypeC'}]}
    result = get_filter_keys(filtr)
    assert result == {'name', 'fullname'}


def test_get_filter_keys_with_key_operator_and_second_key_a_normal_one():
    """Return only the field keys not the operators."""
    filtr = {
        '$or': [{'name': 'TypeB'}, {'fullname': 'TypeC'}],
        'test_field_key': 'some_test_value',
    }
    result = get_filter_keys(filtr)
    assert result == {'name', 'fullname', 'test_field_key'}


def test_get_filter_keys_with_dotted_multikey():
    """When multikey, the first key is pickes."""
    filtr = {
        '$and': [
            {'$or': [{'name': 'TypeB'}, {'name': 'TypeC'}]},
            {'created.date': {'$gte': datetime.datetime(2014, 1, 1, 6, 0)}},
        ]
    }
    result = get_filter_keys(filtr)
    assert result == {'name', 'created.date', 'created'}


def test_get_first_keys_of_indexes_that_dont_return_duplicates():
    """
    In case of multiple keys return only the first(left) keys.

    The function should return a set of them. So if multiple keys like:
    (A, B), (B, C), (A, C), function should return {A, B}
    """
    transaction_indexes = {
        'test_key_': {
            'key': [('test_key', 1)],
            'ns': 'my_database.my_collection',
            'v': 1,
        },
        'test_key_1_test_key2_-1': {
            'key': [('test_key', 1), ('test_key_2', -1)],
            'ns': 'my_database.my_collection',
            'v': 1,
        },
    }
    first_key_indexes = get_first_keys_of_indexes(transaction_indexes)
    assert first_key_indexes == {'test_key'}
