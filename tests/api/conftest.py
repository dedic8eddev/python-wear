import os
from copy import deepcopy
from uuid import uuid4

import pytest
from pyramid import testing
from pyramid.authorization import Authenticated
from pyramid.config import Configurator
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid_mailer import get_mailer
from webtest import TestApp

from spynl_dbaccess import Database

from spynl.main import TemplateTranslations, main, main_includeme

from spynl.api.auth import testutils as auth_testutils
from spynl.api.auth.resources import User

MONGO_URL = os.environ.get(
    'MONGODB_URL', 'mongodb://mongo-user:password@localhost:27020'
)
REDSHIFT_URL = os.environ.get(
    'REDSHIFT_URL', 'redshift://postgres:password@localhost:5439/softwearbi'
)


SPYNL_SETTINGS = {
    'spynl.pay_nl.ip_whitelist': '127.0.0.1',
    'spynl.redshift.url': REDSHIFT_URL,
    'spynl.redshift.max_connections': 1,
    'spynl.pretty': '1',
    'spynl.schemas': 'src/spynl.api/schemas',
    'spynl.mongo.url': MONGO_URL,
    'spynl.mongo.max_limit': 100,
    'spynl.mongo.max_agglimit': 100,
    'spynl.mongo.large_collection_threshold': 100000,
    'spynl.auth.otp.jwt.secret_key': 'secret',
    'spynl.auth.otp.issuer': 'sw2fa',
    'pyramid.default_locale_name': 'en',
    'pyramid.reload_templates': 'true',
    'spynl.domain': 'localhost',
    'mail.host': 'smtp.fakehost.com',
    'mail.ssl': 'false',
    'mail.sender': 'info@spynl.com',
    'spynl.auth.rate_limiter_interval': 60,
    'spynl.auth.enable_rate_limiter': True,
    'spynl.auth.rate_limiter_threshold_fallback': 100,
    'spynl.latestcollection.url': 'https://www.latestcollection.fashion',
    'spynl.latestcollection.master_token': 'masterToken',
    'pyramid.includes': 'pyramid_mailer.testing',
    'spynl.pipe.fp_web_url': 'http://localhost',
}


@pytest.fixture
def settings():
    """Return the settings for the test pyramid application."""
    return deepcopy(SPYNL_SETTINGS)


@pytest.fixture(scope="session")
def app(db):
    """Create a pyramid app that will behave realistic."""
    settings = deepcopy(SPYNL_SETTINGS)
    settings['spynl.mongo.db'] = db.name

    config = Configurator(settings=settings)
    main_includeme(config)
    from spynl.api.mongo.testutils import patched_includeme

    patched_includeme(config)
    include_dummy_views(config)
    application = main(None, config=config)

    application = TestApp(application)
    return application


@pytest.fixture()
def login(app, request):
    """Login to app before the test and logout afterwards."""
    defaults = dict(remember_me=False, tenant_id=None)

    username, password, *custom = request.param
    if custom:
        defaults.update(custom[0])

    params = dict(
        username=username, password=password, remember_me=defaults['remember_me']
    )

    response = app.get('/login', params, status=200)

    if defaults['tenant_id'] is not None:
        params = dict(id=defaults['tenant_id'], sid=response.json['sid'])
        app.get('/set-tenant', params, status=200)

    yield response.json
    app.get('/logout', status=200)


@pytest.fixture
def config(db):
    settings = deepcopy(SPYNL_SETTINGS)
    settings['spynl.mongo.db'] = db
    _config = testing.setUp(settings=settings)
    _config.add_translation_dirs('spynl:locale/')
    _config.include(
        'pyramid_mailer.testing'
    )  # doesn't work if is included via settings dict
    _config.include('pyramid_jinja2')
    _config.add_settings({'jinja2.i18n.gettext': TemplateTranslations})
    import spynl.api as spapi

    _config.add_jinja2_renderer('.jinja2', package=spapi)
    _config.add_jinja2_search_path('spynl.api.hr:email-templates')

    yield _config
    testing.tearDown()


@pytest.fixture
def mailer_outbox(app):
    """Return the pyramid.mailer.outbox cleaned before a test executes."""
    mailer = get_mailer(app.app.registry)
    mailer.outbox = []
    return mailer.outbox


@pytest.fixture(scope="session")
def spynl_data_db():
    os.environ['RUNNING_TESTS'] = 'true'
    db_url = MONGO_URL
    db_name = uuid4().hex
    db = Database(host=db_url, database_name=db_name, ssl=False)
    yield db
    db.pymongo_client.drop_database(db_name)
    db.pymongo_client.close()
    os.environ.pop('RUNNING_TESTS', None)


@pytest.fixture(scope="session")
def db(spynl_data_db):
    """Yield a unique database for the entire session and then drop it."""
    yield spynl_data_db.pymongo_db


@pytest.fixture(autouse=True)
def clean_db_collections(db):
    """Clean collections after every test."""
    yield
    for coll in db.list_collection_names():
        db[coll].delete_many({})


def include_dummy_views(config):
    def generic_view(context, request):
        """generic endpoint view to use here"""
        return {
            'status': 'ok',
            'message': 'You accessed %s' % context.__class__.__name__,
            'filter': request.args.get('filter'),
        }

    def authenticated_view(request):
        """authenticated view"""
        return {'status': 'ok', 'message': 'This is an authenticated view.'}

    config.add_endpoint(
        generic_view,
        'open',
        context=auth_testutils.PublicResource,
        permission=NO_PERMISSION_REQUIRED,
    )
    config.add_endpoint(authenticated_view, 'authenticated', permission=Authenticated)
    config.add_endpoint(
        generic_view, 'get', context=auth_testutils.PublicResource, permission='read'
    )
    config.add_endpoint(
        generic_view, 'update', context=auth_testutils.PublicResource, permission='edit'
    )
    config.add_endpoint(
        generic_view, '/', context=auth_testutils.POSResource, permission='edit'
    )
    config.add_endpoint(
        generic_view, '/', context=auth_testutils.DashboardResource, permission='edit'
    )
    config.add_endpoint(
        generic_view, '/', context=auth_testutils.ReportingResource, permission='read'
    )
    config.add_endpoint(
        generic_view, 'get', context=auth_testutils.SharedResource, permission='read'
    )
    config.add_endpoint(generic_view, 'test_get', context=User, permission='read')
    config.add_endpoint(generic_view, 'test_edit', context=User, permission='edit')
