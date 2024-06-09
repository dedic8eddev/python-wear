"""Tests for db_access functions."""


import datetime
import json

import pytest
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.main.serial import MalformedRequestException
from spynl.main.serial import json as spynl_json

from spynl.api.mongo import db_endpoints
from spynl.api.mongo.db_access import save_with_incremental_id
from spynl.api.mongo.testutils import TestMongoResource as MongoResource
from spynl.api.retail.exceptions import InvalidParameter


@pytest.fixture
def request_(spynl_data_db):
    """Return a ready pyramid fake request."""
    DummyRequest.db = spynl_data_db
    DummyRequest.args = {}
    return DummyRequest


@pytest.fixture
def db_set_data(db):
    """Database population with data."""
    db.test_collection.insert_many(
        [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}, {'a': 5, 'b': {'c': True}}]
    )


@pytest.fixture
def db_set_data2(db):
    """Database population with data."""
    db.test_collection.insert_many(
        [{'_id': '1234', 'a': 1, 'b': 2}, {'_id': 'abcd', 'a': 3, 'b': 4}]
    )


@pytest.fixture
def db_set_data3(db):
    """Database population with meta data."""
    db.test_collection.insert_many(
        [
            {'name': 'Jan1-4', 'created': {'date': datetime.datetime(2014, 1, 1, 4)}},
            {'name': 'Jan1-6', 'created': {'date': datetime.datetime(2014, 1, 1, 6)}},
            {
                u'name': 'Jan10-4',
                'created': {'date': datetime.datetime(2014, 1, 10, 4)},
            },
            {u'name': 'Mar1-4', 'created': {'date': datetime.datetime(2014, 3, 1, 4)}},
            {
                u'name': 'Mar10-2',
                'created': {'date': datetime.datetime(2014, 3, 10, 2)},
            },
        ]
    )


def test_get(db, mongo_config, request_):
    """Test the get returns the expected values/documents."""
    db.test_collection.insert_many([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}])
    request_.args = {'filter': {'a': 1}}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 1
    assert response['data'][0]['a'] == 1
    assert response['data'][0]['b'] == 2

    request_.args = {'filter': {'b': {'$gt': 3}}}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 1
    assert response['data'][0]['a'] == 3
    assert response['data'][0]['b'] == 4

    request_.args = {'filter': {'a': {'$lte': 3}}}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 2


def test_get_defaults(db, mongo_config, request_):
    """should ignore modified_history if not requested"""
    db.test_collection.insert_one({'a': 1, 'modified_history': 'lorem'})
    request_.args = {'filter': {'a': 1}}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 1
    assert response['data'][0]['a'] == 1
    assert 'modified_history' not in response['data'][0]

    request_.args = {'filter': {'a': 1}, 'fields': ['modified_history', 'a']}
    response = db_endpoints.get(MongoResource(), request_)
    assert response['data'][0]['a'] == 1
    assert response['data'][0]['modified_history'] == 'lorem'


@pytest.mark.parametrize("arg", ['limit', 'skip'])
def test_get_passing_non_digits_for_skip_and_limit(request_, arg):
    """Skip and limit should be digits."""
    request_.args = {arg: 'foo'}
    with pytest.raises(InvalidParameter):
        db_endpoints.get(MongoResource(), request_)


def test_limit_get(db, mongo_config, request_):
    """
    Test if get imposes correct limit for data.

    In these tests max_limit is set to 10 to make sure the other tests
    don't break while still managable to add data.
    """
    mongo_config.add_settings({'spynl.mongo.max_limit': 10})
    mongo_config.commit()

    new_data = [
        {'a': 1},
        {'a': 2},
        {'a': 3},
        {'a': 4},
        {'a': 5},
        {'a': 6},
        {'a': 7},
        {'a': 8},
        {'a': 9},
        {'a': 10},
        {'a': 11},
        {'a': 12},
        {'a': 13},
        {'a': 14},
        {'a': 15},
        {'a': 16},
        {'a': 17},
        {'a': 18},
        {'a': 19},
        {'a': 20},
    ]
    db.test_collection.insert_many(new_data)
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 10
    assert response['limit'] == 10

    # test less than max_limit data-set
    request_.args = {'filter': {'a': {"$lt": 9}}}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 8
    assert response['limit'] == 10

    # test request limit > max_limit
    request_.args = {'limit': 15}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 10
    assert response['limit'] == 10


def test_limit_get_in_url(db, mongo_config, request_):
    """
    Test if get imposes the correct limit for data, also when the limit
    is in the url.
    """
    new_data = [
        {'a': 1},
        {'a': 2},
        {'a': 3},
        {'a': 4},
        {'a': 5},
        {'a': 6},
        {'a': 7},
        {'a': 8},
        {'a': 9},
        {'a': 10},
        {'a': 11},
        {'a': 12},
        {'a': 13},
        {'a': 14},
        {'a': 15},
        {'a': 16},
        {'a': 17},
        {'a': 18},
        {'a': 19},
        {'a': 20},
    ]
    db.test_collection.insert_many(new_data)
    request_.args = {'limit': 8}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 8
    assert response['limit'] == 8


@pytest.mark.parametrize('sort', [[['a', 1]], [{'field': 'a', 'direction': 1}]])
def test_sort_ascending(db, mongo_config, request_, sort):
    """
    Request sorted documents from the database in ascending order.
    old style and new style params.
    """
    db.test_collection.insert_many([{'a': 1}, {'a': 2}])
    request_.args = {'sort': sort}
    response = db_endpoints.get(MongoResource(), request_)
    assert response['data'][0]['a'] == 1
    assert response['data'][1]['a'] == 2


@pytest.mark.parametrize('sort', [[['a', -1]], [{'field': 'a', 'direction': -1}]])
def test_sort_descending(db, mongo_config, request_, sort):
    """
    Request sorted documents from the database in descending order.
    old style and new style params.
    """
    db.test_collection.insert_many([{'a': 1}, {'a': 2}])
    request_.args = {'sort': sort}
    response = db_endpoints.get(MongoResource(), request_)
    assert response['data'][0]['a'] == 2
    assert response['data'][1]['a'] == 1


def test_insert_single(db, mongo_config, request_):
    """Insert one document and check if exists in the database."""
    request_.args = {'data': {'a': 1}}
    db_endpoints.add(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 1


def test_insert_multiple_documents(db, mongo_config, request_):
    """Insert some documents to the database."""
    request_.args = {'data': [{'a': 1}, {'a': 2}]}
    db_endpoints.add(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 1
    assert db.test_collection.count_documents({'a': 2}) == 1


def test_remove(db, mongo_config, request_):
    """Remove one document and check if it exists in the database."""
    db.test_collection.insert_one({'a': 1})
    request_.args = {'filter': {'a': 1}}
    db_endpoints.remove(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 0


def test_remove_with_ObjectId(db, mongo_config, request_):
    """Find document by ObjectId and remove it."""
    oid = ObjectId()
    db.test_collection.insert_one({'_id': oid, 'a': 1})
    request_.args = {'filter': {'_id': oid}}
    db_endpoints.remove(MongoResource(), request_)
    assert db.test_collection.count_documents({'_id': oid}) == 0


def test_update(db, mongo_config, request_):
    """
    Check when updating a document if its values are correct.

    Also check if other document was affected by the updates.
    """
    db.test_collection.insert_many([{'a': 1, 'b': 2}, {'a': 3, 'b': 4}])
    request_.args = {'filter': {'a': 1}, 'data': {'$set': {'a': True}}}
    db_endpoints.single_edit(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 0
    assert db.test_collection.count_documents({'a': True}) == 1
    assert db.test_collection.count_documents({'b': 2}) == 1
    assert db.test_collection.count_documents({'a': 3}) == 1
    assert db.test_collection.count_documents({'b': 4}) == 1


def test_update_individual(db, mongo_config, db_set_data, request_):
    """Update a field in a document that other documents have it too."""
    request_.args = {'filter': {'a': 1}, 'data': {'$set': {'a': True}}}
    db_endpoints.single_edit(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 0
    assert db.test_collection.count_documents({'a': True}) == 1
    assert db.test_collection.count_documents({'b': 2}) == 1
    assert db.test_collection.count_documents({'a': 3}) == 1
    assert db.test_collection.count_documents({'b': 4}) == 1


def test_update_nested_key(db, mongo_config, db_set_data, request_):
    """Update a nested field in a document that other documents have it too."""
    request_.args = {'filter': {'a': 5}, 'data': {'$set': {'b.c': False}}}
    db_endpoints.single_edit(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 5}) == 1
    assert db.test_collection.count_documents({'b': {'c': False}}) == 1
    assert db.test_collection.count_documents({'a': 3}) == 1
    assert db.test_collection.count_documents({'b': 4}) == 1


def test_save(db, mongo_config, db_set_data2, request_):
    """Check saving documents one by one."""
    db.test_collection.insert_one({'d': 5, 'e': 6})
    request_.args = {'data': {'_id': '1234', 'a': True, 'b': 2}}
    db_endpoints.save(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 0
    assert db.test_collection.count_documents({'a': True}) == 1
    assert db.test_collection.count_documents({'b': 2}) == 1
    assert db.test_collection.count_documents({'a': 3}) == 1
    assert db.test_collection.count_documents({'b': 4}) == 1
    assert db.test_collection.count_documents({'d': 5}) == 1


def test_save_multi(db, mongo_config, db_set_data2, request_):
    """Request to save multiple documents at once."""
    request_.args = {
        'data': [
            {'_id': '1234', 'a': True, 'b': 2},
            {'_id': '12345', 'c': True, 'd': 2},
        ]
    }
    db_endpoints.save(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 0
    assert db.test_collection.count_documents({'a': True}) == 1
    assert db.test_collection.count_documents({'b': 2}) == 1
    assert db.test_collection.count_documents({'a': 3}) == 1
    assert db.test_collection.count_documents({'b': 4}) == 1
    assert db.test_collection.count_documents({'_id': '12345'}) == 1


def test_bad_data_passing_bad_json(db, mongo_config, db_set_data2, request_):
    """Test with some bad data."""
    request_.args = {
        'data': [
            {'_id': '1234', 'a': True, '$b': 2},
            {'_id': '12345', 'c': True, 'd': 2},
        ]
    }
    with pytest.raises(Exception):
        db_endpoints.save(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 1


def test_bad_data_passing_existing_key(db, mongo_config, db_set_data2, request_):
    """Test adding document with already existing key: 1234."""
    request_.args = {
        'data': [
            {'_id': '1234', 'a': True, 'b': 2},
            {'_id': '12345', 'c': True, 'd': 2},
        ]
    }
    with pytest.raises(Exception):
        db_endpoints.add(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 1


def test_bad_data_by_editing_without_set_operator(
    db, mongo_config, db_set_data2, request_
):
    """Edit document without passing $set."""
    request_.args = {
        'data': {'_id': '1234', 'a': True, 'b': 2},
        'filter': {'_id': '1234'},
    }
    with pytest.raises(Exception):
        db_endpoints.add(MongoResource(), request_)
    assert db.test_collection.count_documents({'a': 1}) == 1


def test_database_with_request_by_passing_specific_date(
    mongo_config, request_, db_set_data3
):
    """Only one doc should be in the response with the specific date."""
    request_.args = {'filter': {'created.date': datetime.datetime(2014, 1, 1, 6)}}
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 1


def test_database_with_date_range_by_request(mongo_config, db_set_data3, request_):
    """Find documents by requesting with range of dates."""
    request_.args = {
        'filter': {
            'created.date': {
                '$gte': datetime.datetime(2014, 1, 1, 7),
                '$lte': datetime.datetime.now(),
            }
        }
    }
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 3


def test_that_mongo_decoding_date_fields_work(mongo_config):
    """date key accepts only date format values."""
    with pytest.raises(MalformedRequestException):
        spynl_json.loads(json.dumps({'filter': {'created.date': 'Lalalala'}}))


def test_inserting_docs_with_dates_that_exist(db, mongo_config, request_):
    """Insert docs with date fields and check if they were inserted."""
    db.test_collection.insert_many(
        [
            {'name': 'TypeA', 'created': {'date': datetime.datetime(2014, 1, 1, 4)}},
            {'name': 'TypeB', 'created': {'date': datetime.datetime(2014, 1, 1, 6)}},
            {'name': 'TypeA', 'created': {'date': datetime.datetime(2014, 1, 10, 4)}},
            {'name': 'TypeB', 'created': {'date': datetime.datetime(2014, 3, 1, 4)}},
            {'name': 'TypeC', 'created': {'date': datetime.datetime(2014, 3, 10, 2)}},
        ]
    )
    request_.args = {
        'filter': {
            '$and': [
                {'$or': [{'name': 'TypeB'}, {'name': 'TypeC'}]},
                {'created.date': {'$gte': datetime.datetime(2014, 1, 1, 6)}},
            ]
        }
    }
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 3


def test_incremental_id_is_created_correctly(db, mongo_config, request_):
    """Test that incremental id is saved for each request."""
    # First we'll insert some existing records with ids we should skip
    # this means non numerical or lower than 1000000
    db.test_collection.insert_many(
        [
            {'_id': ObjectId(), 'name': 'Test-ObjectId'},
            {'_id': '87t08qgo', 'name': 'Test-Non-Numerical-String'},
            {'_id': '99', 'name': '99'},
        ]
    )

    save_with_incremental_id(
        MongoResource(), request_, [{'name': str(i)} for i in range(3)]
    )
    assert db.test_collection.find_one({'name': '0'})['_id'] == '100000'
    assert db.test_collection.find_one({'name': '1'})['_id'] == '100001'
    assert db.test_collection.find_one({'name': '2'})['_id'] == '100002'


def test_incremental_id_is_created_correctly_after_100000(db, mongo_config, request_):
    """Test that incremental id is saved for each request."""
    db.test_collection.insert_many([{"_id": "100004", "name": "4"}])

    save_with_incremental_id(
        MongoResource(), request_, [{'name': str(i)} for i in range(3)]
    )
    assert db.test_collection.find_one({'name': '0'})['_id'] == '100005'
    assert db.test_collection.find_one({'name': '1'})['_id'] == '100006'
    assert db.test_collection.find_one({'name': '2'})['_id'] == '100007'


def test_save_new_document_that_returns_string_instead_of_object_id(
    mongo_config, request_
):
    """Return string of the Objectid() when saving a new document."""
    request_.args = {
        'resource': 'test_collection',
        'method': 'save',
        'data': {'some_field': 'test_word'},
    }
    response = db_endpoints.save(MongoResource(), request_)
    returned_id = response['data'][0]
    assert isinstance(returned_id, ObjectId)


def test_save_doc_with_existing_id_that_returns_id_in_str(mongo_config, request_):
    """Test save existing doc that returns the _id in str format."""
    request_.args = {'data': {'some_field': 'test_word', '_id': '12345'}}
    db_endpoints.save(MongoResource(), request_)

    request_.args['data']['some_field'] = 'test_word2'
    response = db_endpoints.save(MongoResource(), request_)
    returned_id = response['data'][0]

    assert isinstance(returned_id, str)
    assert returned_id == request_.args['data']['_id']


def test_save_with_new_doc_insert_that_returns_new_id_in_object_id(
    mongo_config, request_
):
    """
    Save new doc and check that returns the _id as ObjectId.

    The request does not include _id, so new one must be created.
    """
    request_.args = {'data': {'some_field': 'test_word'}}
    response = db_endpoints.save(MongoResource(), request_)
    new_id = response['data'][0]
    assert isinstance(new_id, ObjectId)


def test_save_with_existing_id_returns_the_original_id_in_str(mongo_config, request_):
    """Test save function by passing an existing _id."""
    request_.args = {'data': {'some_field': 'test_word', '_id': 'test_id'}}
    db_endpoints.save(MongoResource(), request_)

    request_.args['data']['some_field'] = 'test_word2'
    response = db_endpoints.save(MongoResource(), request_)
    new_id = response['data'][0]
    assert isinstance(new_id, str)
    assert new_id == request_.args['data']['_id']
