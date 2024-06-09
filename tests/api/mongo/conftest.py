"""Pytest fixtures to be used by all tests."""
import os

import pytest
from pyramid import testing

from spynl.main.routing import main as routing_main

from spynl.api.mongo.plugger import includeme as mongo_includeme

MONGO_URL = os.environ.get(
    'MONGODB_URL', 'mongodb://mongo-user:password@localhost:27020'
)


@pytest.fixture
def mongo_config(db):
    """Configurator with mongo plugger plus mongo extra endpoints."""
    settings = {
        'spynl.mongo.url': MONGO_URL,
        'spynl.mongo.db': db.name,
        'spynl.mongo.max_limit': 100,
        'spynl.mongo.max_agglimit': 10,
    }
    config = testing.setUp(settings=settings)
    # hook add_endpoint so mongo plugger can be hooked too
    routing_main(config)
    mongo_includeme(config)
    yield config
    testing.tearDown()
