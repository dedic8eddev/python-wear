"""
Pytest fixtures to be used by all tests.

Also a function to be able to compare pdf files.
"""

import os
from copy import deepcopy
from uuid import uuid4

import psycopg2
import pytest
from bson.codec_options import CodecOptions
from jinja2 import ChoiceLoader, Environment, PackageLoader
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from pymongo import MongoClient
from pyramid import testing
from pyramid_mailer import get_mailer
from webtest import TestApp

from spynl.main import main

import spynl.services.pdf.utils as pdf_utils
from spynl.services.reports.utils import parse_connection_string

MONGO_URL = os.environ.get(
    'MONGODB_URL', 'mongodb://mongo-user:password@localhost:27020'
)
REDSHIFT_URL = os.environ.get(
    'REDSHIFT_URL', 'redshift://postgres:password@localhost:5439/softwearbi'
)


@pytest.fixture(scope='session')
def postgres_db():
    pg_args = parse_connection_string(REDSHIFT_URL)

    test_conn = psycopg2.connect(**{**pg_args, 'cursor_factory': RealDictCursor})
    test_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    yield test_conn

    test_conn.close()


@pytest.fixture()
def postgres_cursor(postgres_db):
    with postgres_db.cursor() as c:
        yield c


@pytest.fixture(scope="session")
def settings():
    """Return the settings for the test pyramid application."""
    settings_ = {
        'spynl.redshift.url': REDSHIFT_URL,
        'spynl.redshift.max_connections': 1,
        'spynl.pretty': '1',
        'spynl.mongo.url': MONGO_URL,
        'spynl.mongo.max_limit': 100,
        'spynl.mongo.max_agglimit': 10000,
        'spynl.mongo.large_collection_threshold': 100000,
        'spynl.domain': 'localhost',
        'spynl.latestcollection.url': 'https://www.latestcollection.fashion',
        'spynl.latestcollection.master_token': 'masterToken',
        'pyramid.default_locale_name': 'en',
        'pyramid.reload_templates': 'true',
        'mail.host': 'smtp.fakehost.com',
        'mail.ssl': 'false',
        'mail.sender': 'info@spynl.com',
        'spynl.pipe.marketing_email': 'marketing@softwear.nl',
        'pyramid.includes': 'pyramid_mailer.testing',
        'spynl.pipe.vw_web_url': 'http://172.0.0.75:8080/vector/resources/sql',
        'spynl.pipe.vw_access_token': '1234',
        'spynl.pipe.fp_web_url': 'http://api.softwear.nl',
        'spynl.pipe.fp_access_token': '1234',
        'spynl.pipe.marketing_email': 'marketing@softwear.nl',
        'spynl.auth.otp.secret_key': '7UNTWJDQ54ZZH4SQ',
        'spynl.auth.otp.jwt.secret_key': 'secret',
        'spynl.auth.otp.issuer': 'sw2fa',
    }
    return deepcopy(settings_)


@pytest.fixture(autouse=True)
def patch_connectionpool(monkeypatch):
    class Pool(ThreadedConnectionPool):
        def putconn(self, *args, **kwargs):
            kwargs['close'] = True
            return super().putconn(*args, **kwargs)

    monkeypatch.setattr('spynl.services.reports.plugger.ThreadedConnectionPool', Pool)


@pytest.fixture(scope="session")
def db():
    """Create and return a unique database."""
    connection = MongoClient(MONGO_URL)
    db_ = connection.get_database(
        uuid4().hex, CodecOptions(tz_aware=True, uuid_representation=4)
    )
    yield db_
    connection.drop_database(db_.name)
    connection.close()


@pytest.fixture(autouse=True)
def clean_db(db):
    """Clean all db collections after every test."""
    yield
    for name in db.list_collection_names():
        db[name].delete_many({})


@pytest.fixture(autouse=True)
def mock_boto(monkeypatch):
    """Fake some boto functionality to avoid calling check_s3_credentials."""

    class FakeBoto:
        def __getattr__(self, name):
            return FakeBoto()

        def __call__(self, *a, **kw):
            return FakeBoto()

    monkeypatch.setattr('spynl.services.upload.utils.boto3', FakeBoto())


@pytest.fixture(scope="session")
def app(db, settings):
    """Create a pyramid app that will behave realistic."""
    settings['spynl.mongo.db'] = db.name
    spynl_app = main(None, **settings)
    application = TestApp(spynl_app)

    return application


@pytest.fixture(scope="session")
def config(settings, db):
    """Create a Pyramid configurator."""
    config = testing.setUp(settings=settings)
    config.add_settings({'spynl.mongo.db': db})
    yield config
    testing.tearDown()


@pytest.fixture
def inbox(app):
    """Return the pyramid.mailer.outbox cleaned before a test executes."""
    mailer = get_mailer(app.app.registry)
    mailer.outbox = []

    return mailer.outbox


def patched_render(path, replacements, request=None):
    env = Environment(
        trim_blocks=True,
        loader=ChoiceLoader(
            [
                PackageLoader('spynl.services.pdf', 'pdf-templates'),
                PackageLoader('spynl.services.pdf', 'pdf-templates/reports'),
            ]
        ),
    )
    env.filters['translate'] = (pdf_utils.non_babel_translate,)
    env.filters['format_datetime'] = pdf_utils.format_datetime
    env.filters['format_date'] = pdf_utils.format_date
    env.filters['format_country'] = pdf_utils.format_country
    env.filters['format_currency'] = pdf_utils.format_currency
    env.filters['format_decimal'] = pdf_utils.format_decimal
    env.filters['change_case'] = pdf_utils.change_case
    env.globals['tenant_logo_url'] = lambda x: str(x)
    env.globals['_'] = lambda x, mapping=None: str(x)
    template = env.get_template(path)
    return template.render(**replacements)


@pytest.fixture
def patch_jinja(monkeypatch):
    monkeypatch.setattr('spynl.services.pdf.pdf.render', patched_render)
