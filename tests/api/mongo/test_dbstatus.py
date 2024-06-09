"""Test the db status endpoint."""


import pytest
from pyramid.testing import DummyRequest

from spynl.api.mongo import db_endpoints


@pytest.fixture
def request_(spynl_data_db):
    DummyRequest.db = spynl_data_db
    return DummyRequest


@pytest.fixture
def db_set(db):
    """Database with some documents to get a healthy db message."""
    db.users.insert_one({'fullname': 'Some person'})
    db.customers.insert_one({'last_name': 'Meyer'})
    db.transactions.insert_one({'a': 5, 'b': {'c': True}})


def test_db_status_error(mongo_config, request_):
    """Test the db-status endpoint."""
    response = db_endpoints.db_connection_health(request_)
    assert 'db-connection-health' in response['message'].translate()
    assert 'time' in response


def test_db_status_healthy(mongo_config, db_set, request_):
    """Test the db-status endpoint."""
    response = db_endpoints.db_connection_health(request_)
    assert response['status'] == 'healthy'
    assert 'time' in response
