"""Pytest fixtures to be used by all tests in main spynl package."""

import os
from datetime import datetime

import pytest
from pyramid import testing
from pyramid_mailer import get_mailer
from webtest import TestApp

from spynl.main import main
from spynl.main.serial.objects import (
    add_decode_function,
    add_encode_function,
    decode_date,
    encode_boolean,
    encode_date,
)

MONGO_URL = os.environ.get(
    'MONGODB_URL', 'mongodb://mongo-user:password@localhost:27020'
)


@pytest.fixture(scope="session")
def settings():
    """Return the settings for the test pyramid application."""
    return {
        'spynl.tests.no_plugins': 'true',
        'spynl.pretty': '1',
        'pyramid.debug_authorization': 'false',
        'pyramid.default_locale_name': 'nl',
        'pyramid.reload_templates': 'true',
        'spynl.domain': 'localhost',
        'spynl.latestcollection.url': 'https://www.latestcollection.fashion',
        'spynl.latestcollection.master_token': 'masterToken',
        'spynl.mongo.url': MONGO_URL,
        'pyramid.debug_notfound': 'false',
        'pyramid.debug_templates': 'true',
        'pyramid.debug_routematch': 'false',
        'spynl.tld_origin_whitelist': 'softwearconnect.com,swcloud.nl',
        'spynl.dev_origin_whitelist': 'http://0.0.0.0:9001,chrome-extension:// ',
        'mail.host': 'smtp.fakehost.com',
        'mail.ssl': 'false',
        'mail.sender': 'info@spynl.com',
        'pyramid.includes': 'pyramid_mailer.testing',
    }


@pytest.fixture(scope="session")
def app(settings):
    """Create a pyramid app that will behave realistic."""
    config = testing.setUp(settings=settings)
    config.include('pyramid_mailer.testing')
    config.add_translation_dirs('spynl:locale/')
    config.include('pyramid_jinja2')
    config.add_jinja2_renderer('.txt')
    # needed for serial tests:
    add_decode_function(config, decode_date, ['date'])
    add_encode_function(config, encode_date, datetime)
    add_encode_function(config, encode_boolean, bool)
    spynl_app = main(None, **settings)
    webtest_app = TestApp(spynl_app)

    return webtest_app


@pytest.fixture
def app_factory():
    """Return a basic factory app maker to be able to pass custom settings."""

    def make_app(settings):
        """Return the maker app."""
        spynl_app = main(None, **settings)
        webtest_app = TestApp(spynl_app)
        return webtest_app

    return make_app


@pytest.fixture
def mailer(app):
    """Return applications mailer."""
    mailer = get_mailer(app.app.registry)
    mailer.outbox = []
    return mailer


@pytest.fixture(scope="session")
def dummyrequest():
    return testing.DummyRequest()
