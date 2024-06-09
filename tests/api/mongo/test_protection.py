"""Tests for protection module."""


import pytest
from pyramid.testing import DummyRequest

from spynl.api.mongo import db_endpoints
from spynl.api.mongo.testutils import (
    TestLargeCollectionResource as LargeCollectionResource,
)
from spynl.api.mongo.testutils import TestMongoResource as MongoResource


@pytest.fixture(autouse=True)
def db_set_data(db):
    """Database population with data."""
    db.large_collection.insert_many(
        [
            {'_id': '1', 'a': 1, 'b': 2},
            {'_id': '2', 'a': 3, 'b': 4},
            {'_id': '3', 'a': 5, 'b': {'c': True}},
        ]
    )
    db.test_collection.insert_many(
        [{'_id': '1234', 'a': 1, 'b': 2}, {'_id': 'abcd', 'a': 3, 'b': 4}]
    )


@pytest.fixture
def request_(spynl_data_db):
    """Return a ready pyramid fake request."""
    DummyRequest.db = spynl_data_db
    DummyRequest.args = {}
    return DummyRequest


def test_querying_large_collection_with_index_keys(mongo_config, request_):
    """Quering large collections with an index key IS allowed."""
    request_.args = dict(filter={'_id': '1'})
    response = db_endpoints.get(LargeCollectionResource(), request_)
    assert len(response['data']) == 1


def test_querying_normal_collection_without_index_keys(mongo_config, request_):
    """Querying collection under threshold without any index key IS allowed."""
    request_.args = dict(filter={'a': {'$lt': 6}})
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 2


def test_querying_normal_collection_with_index_keys(mongo_config, request_):
    """Querying collection under threshold without any index key IS allowed."""
    request_.args = dict(filter={'_id': '1234'})
    response = db_endpoints.get(MongoResource(), request_)
    assert len(response['data']) == 1


def test_count_entire_large_collection_without_index_keys(mongo_config, request_):
    """Counting entire collection is a cheap thing to do so its allowed."""
    request_.args = dict(filter={})
    response = db_endpoints.count(LargeCollectionResource(), request_)
    assert response['count'] == 3


def test_counting_large_collection_with_index_keys(mongo_config, request_):
    """Counting large collections with index key IS allowed."""
    request_.args = dict(filter={'_id': '1'})
    response = db_endpoints.count(LargeCollectionResource(), request_)
    assert response['count'] == 1


def test_counting_normal_collection_without_index_keys(mongo_config, request_):
    """Counting collection under threshold without any index key IS allowed."""
    request_.args = dict(filter={'a': {'$lt': 6}})
    response = db_endpoints.count(MongoResource(), request_)
    assert response['count'] == 2


def test_counting_normal_collection_with_index_keys(mongo_config, request_):
    """Counting collection under threshold without any index key IS allowed."""
    request_.args = dict(filter={'_id': '1234'})
    response = db_endpoints.count(MongoResource(), request_)
    assert response['count'] == 1


def test_get_filtr_with_index_sort_with_2_keys_first_index(mongo_config, request_):
    """
    Passing a sorting index as first positional argument should not complain.

    Test should ask more documents than the threshold.
    """
    request_.args = dict(
        filter={'_id': {'$in': [str(i) for i in range(5)]}}, sort=[('_id', 1), ('a', 1)]
    )
    response = db_endpoints.get(LargeCollectionResource(), request_)
    assert len(response['data']) == 3


def test_get_filtr_with_index_sort_with_index(mongo_config, request_):
    """
    There should not be any exception.

    Test should ask more documents than the threshold.
    """
    request_.args = dict(
        filter={'_id': {'$in': [str(i) for i in range(5)]}}, sort=[('_id', 1)]
    )
    response = db_endpoints.get(LargeCollectionResource(), request_)
    assert len(response['data']) == 3
