"""Test utils for spynl.mongo functionality."""

from pyramid.authorization import Allow

from spynl.api.mongo import MongoResource
from spynl.api.mongo.db_endpoints import get_include_public_documents
from spynl.api.mongo.plugger import add_dbaccess_endpoints


class TestMongoResource(MongoResource):

    """Represents some random data for testing"""

    collection = 'test_collection'
    paths = ['test']

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit', 'delete')),
        (Allow, 'role:sw-admin', ('read', 'add', 'edit', 'delete')),
        (Allow, 'role:account-admin', ('read', 'add', 'edit', 'delete')),
    ]


class TestLargeCollectionResource(MongoResource):

    """Represents a large collection"""

    collection = 'large_collection'
    paths = ['test-large']
    is_large_collection = True


class TestRetailCustomersResource(MongoResource):

    """Represents customer data to test importing"""

    collection = 'customers'
    paths = ['test-customers']


def patched_includeme(config):
    """
    Use this for adding additional functionality for tests.

    Sometimes tests need additional things such as routes. Define those here.
    """
    config.add_endpoint(
        get_include_public_documents,
        '/',
        context=TestMongoResource,
        permission='read',
        request_method='GET',
    )
    config.add_endpoint(
        get_include_public_documents,
        'get',
        context=TestMongoResource,
        permission='read',
    )
    add_dbaccess_endpoints(
        config, TestMongoResource, ['remove', 'count', 'edit', 'save']
    )
    add_dbaccess_endpoints(config, TestLargeCollectionResource, ['get'])
    add_dbaccess_endpoints(config, TestRetailCustomersResource, ['get'])
