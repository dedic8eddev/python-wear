import os

import pytest
from pyramid.testing import DummyRequest

from spynl.main.exceptions import SpynlException

from spynl.api.auth.tenantid_utils import extend_filter_by_tenant_id
from spynl.api.mongo import MongoResource


@pytest.fixture(scope="module")
def settings_2():
    """Return the settings for the test pyramid application."""
    return {
        'spynl.mongo.db': 'test_db',
        'spynl.pretty': '1',
        'spynl.domain': 'localhost',
        'spynl.mongo.url': os.environ.get('MONGODB_URL'),
        'spynl.mongo.max_limit': 100,
        'spynl.mongo.max_agglimit': 10000,
        'pyramid.default_locale_name': 'en',
    }


def test_extend_filter_do_not_allow_none():
    """The filter should never be extended with None for the tenantid"""
    with pytest.raises(SpynlException, match='no-tenant-id-in-filter'):
        extend_filter_by_tenant_id({}, ['tenant1', None], MongoResource(DummyRequest()))
    with pytest.raises(SpynlException, match='no-tenant-id-in-filter'):
        extend_filter_by_tenant_id({}, [], MongoResource(DummyRequest()))


class PublicResource(MongoResource):
    collection = 'public1'
    contains_public_documents = True


def test_extend_filter_allow_none_for_public(config, settings_2):
    """The filter should never be extended with None for the tenantid"""
    config.add_settings(settings_2)
    publicR = PublicResource(DummyRequest())
    extended_filter = extend_filter_by_tenant_id(
        {}, ['tenant1', None], publicR, include_public=True
    )
    assert extended_filter == {
        '$or': [{'tenant_id': {'$in': ['tenant1', None]}}, {'tenant_id': None}]
    }
