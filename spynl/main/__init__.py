"""The main package of Spynl."""
import os

import sentry_sdk
from marshmallow import INCLUDE, Schema, ValidationError, fields
from pkg_resources import get_distribution
from pyramid.config import Configurator
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.viewderivers import INGRESS
from sentry_sdk.integrations.pyramid import PyramidIntegration

from spynl.locale import TemplateTranslations

from spynl.main import about, endpoints, events, plugins, routing, serial, session
from spynl.main.dateutils import now
from spynl.main.docs.documentation import make_docs
from spynl.main.error_views import error400, error500, spynl_error, validation_error
from spynl.main.exceptions import SpynlException
from spynl.main.utils import (
    add_jinja2_filters,
    check_origin,
    get_logger,
    handle_pre_flight_request,
    renderer_factory,
    sentry_before_send,
)

# monkeypatch MAX_DATABAG_BREADTH so our payloads do not get trimmed:
# (see https://github.com/getsentry/sentry-python/issues/377)
sentry_sdk.serializer.MAX_DATABAG_BREADTH = 40


class IniSettings(Schema):
    """
    Schema for the ini settings defined by spynl (does not include pyramid ini settings)
    """

    spynl_domain = fields.String(attribute='spynl.domain', data_key='spynl.domain')
    spynl_tld_origin_whitelist = fields.String(
        attribute='spynl.tld_origin_whitelist',
        data_key='spynl.tld_origin_whitelist',
        metadata={
            'description': 'Comma-separated whitelist for allowed origins. It is '
            "expected to hold only the top-level domains,  e.g. 'google.com'."
        },
    )
    spynl_dev_origin_whitelist = fields.String(
        attribute='spynl.dev_origin_whitelist',
        data_key='spynl.dev_origin_whitelist',
        metadata={
            'description': 'Comma separated whitelist for allowed origins which is '
            'usable for a development context. It is expected to hold either complete '
            "domains or mere protocols, e.g. 'chrome-extension://'.."
        },
    )
    spynl_pretty = fields.String(
        attribute='spynl.pretty',
        data_key='spynl.pretty',
        metadata={
            'description': 'Pretty printing for development. Is read with Pyramid '
            'asbool function.'
        },
    )
    spynl_app_environment = fields.String(
        attribute='spynl.app.environment',
        data_key='spynl.app.environment',
        metadata={
            'description': 'The environment Spynl is running in. This is quite useful '
            'for things like error log aggregation.'
        },
    )
    spynl_app_function = fields.String(
        attribute='spynl.app.function',
        data_key='spynl.app.function',
        metadata={'description': 'To keep track of api and services instances.'},
    )
    spynl_sentry_key = fields.String(
        attribute='spynl.sentry.key',
        data_key='spynl.sentry.key',
        metadata={
            'description': 'The key used to connect to Sentry. Leave empty if '
            'you are not using Sentry.'
        },
    )
    spynl_sentry_project = fields.String(
        attribute='spynl.sentry.project',
        data_key='spynl.sentry.project',
        metadata={'description': 'The project identifier Spynl reports to in Sentry.'},
    )
    spynl_auth_otp_jwt_secret_key = fields.String(
        required=True,
        attribute='spynl.auth.otp.jwt.secret_key',
        data_key='spynl.auth.otp.jwt.secret_key',
        metadata={'description': 'JWT Secret key for the 2FA authentication flow'},
    )
    spynl_auth_otp_issuer = fields.String(
        required=True,
        attribute='spynl.auth.otp.issuer',
        data_key='spynl.auth.otp.issuer',
        metadata={'description': '2FA issuer, shows up in Authenticator app.'},
    )
    spynl_mongo_url = fields.String(
        attribute='spynl.mongo.url',
        data_key='spynl.mongo.url',
        metadata={'description': 'URL to the mongo database'},
    )
    spynl_mongo_url = fields.String(
        required=True,
        attribute='spynl.mongo.url',
        data_key='spynl.mongo.url',
        metadata={'description': 'URL to the mongo database'},
    )
    spynl_mongo_db = fields.String(
        required=True,
        attribute='spynl.mongo.db',
        data_key='spynl.mongo.db',
        metadata={'description': 'Name of the database to connect to.'},
    )
    spynl_mongo_ssl = fields.String(
        attribute='spynl.mongo.ssl',
        data_key='spynl.mongo.ssl',
        metadata={
            'description': 'Use ssl or not. Is read with Pyramid asbool function.'
        },
    )
    spynl_mongo_auth_mechanism = fields.String(
        attribute='spynl.mongo.auth_mechanism',
        data_key='spynl.mongo.auth_mechanism',
        metadata={'description': 'If given, use a specific auth method for mongo.'},
    )
    spynl_mongo_max_limit = fields.String(
        required=True,
        attribute='spynl.mongo.max_limit',
        data_key='spynl.mongo.max_limit',
        metadata={
            'description': 'The maximum number of returned documents when using the '
            'Mongo find function'
        },
    )
    spynl_mongo_max_agglimit = fields.String(
        required=True,
        attribute='spynl.mongo.max_agglimit',
        data_key='spynl.mongo.max_agglimit',
        metadata={
            'description': 'Maximum number of returned documents for aggregation'
        },
    )
    spynl_pipe_fp_web_url = fields.String(
        attribute='spynl.pipe.fp_web_url',
        data_key='spynl.pipe.fp_web_url',
        metadata={'description': 'Web URL for Foxpro.'},
    )
    spynl_pipe_fp_access_token = fields.String(
        attribute='spynl.pipe.fp_access_token',
        data_key='spynl.pipe.fp_access_token',
        metadata={'description': 'Access token for Foxpro.'},
    )
    spynl_pipe_marketing_email = fields.String(
        attribute='spynl.pipe.marketing_email',
        data_key='spynl.pipe.marketing_email',
        metadata={
            'description': 'Email that emails for the marketing department '
            'will get send to'
        },
    )
    spynl_pipe_bitly_access_token = fields.String(
        attribute='spynl.pipe.bitly_access_token',
        data_key='spynl.pipe.bitly_access_token',
        metadata={'description': 'Access token for Bitly.'},
    )

    class Meta:
        unknown = INCLUDE


def check_required_settings(config):
    """
    The proper way to do this would be to do a load, but not all the fields have
    the correct type yet, and we should really check very carefully that everything
    works before we make that change.
    """
    if config.get_settings().get('spynl.tests.no_plugins') != 'true':
        required_settings = [
            value.data_key for value in IniSettings().fields.values() if value.required
        ]
        for setting in required_settings:
            if setting not in config.registry.settings:
                raise SpynlException(f'Please set {setting} in the Pyramid ini file')


class ConfigCommited(object):
    """Event to signal that configurator finished and commited."""

    def __init__(self, config):
        self.config = config


def main(global_config, config=None, **settings):
    """
    Return a Pyramid WSGI application.

    Before that, we tell plugins how to add a view and tell views which
    renderer to use. And we take care of test settings. Then, we initialise the
    main plugins and the external plugins (which are not in this repository).
    """
    log = get_logger()
    try:
        dsn = 'https://{}@sentry.io/{}'.format(
            settings['spynl.sentry_key'], settings['spynl.sentry_project']
        )
        sentry_sdk.init(
            dsn=dsn,
            release=get_distribution('spynl.app').version,
            environment=settings.get('spynl.app.environment', 'dev'),
            # Note: This will also make breadcrumbs of all logging actions:
            # https://docs.sentry.io/platforms/python/pyramid/
            integrations=[PyramidIntegration()],
            before_send=sentry_before_send,
        )
    except KeyError:
        # if sentry key or project don't exist move on
        pass
    except sentry_sdk.utils.BadDsn:
        log.warning('Invalid Sentry DSN')

    if config is None:
        config = Configurator(settings=settings)
        main_includeme(config)

    config.commit()
    config.registry.notify(ConfigCommited(config))

    return config.make_wsgi_app()


def main_includeme(config):
    config.add_settings({'spynl.app.start_time': now()})

    # Add spynl.main's view derivers
    config.add_view_deriver(handle_pre_flight_request, under=INGRESS)
    config.add_view_deriver(check_origin)

    # initialize the main plugins
    # serial should be before plugins, because plugins can overwrite field
    # treatment
    # session needs to be after plugins, because plugins can set the session
    # mechanism
    routing.main(config)
    events.main(config)
    serial.main(config)
    endpoints.main(config)
    about.main(config)
    plugins.main(config)
    session.main(config)

    check_required_settings(config)

    # Custom renderer from main.serial or vanilla json renderer
    config.add_renderer('spynls-renderer', renderer_factory)

    config.add_translation_dirs('spynl:locale')

    # Error views
    config.add_view(
        error400,
        context='pyramid.httpexceptions.HTTPError',
        renderer='spynls-renderer',
        is_error_view=True,
        permission=NO_PERMISSION_REQUIRED,
    )
    config.add_view(
        spynl_error,
        context=SpynlException,
        renderer='spynls-renderer',
        is_error_view=True,
        permission=NO_PERMISSION_REQUIRED,
    )
    config.add_view(
        error500,
        context=Exception,
        renderer='spynls-renderer',
        is_error_view=True,
        permission=NO_PERMISSION_REQUIRED,
    )
    config.add_view(
        validation_error,
        context=ValidationError,
        renderer='spynls-renderer',
        is_error_view=True,
        permission=NO_PERMISSION_REQUIRED,
    )

    # make spynl documentation
    if os.environ.get('GENERATE_SPYNL_DOCUMENTATION') == 'generate':
        make_docs(config)
        exit()

    # add jinja for templating
    config.include('pyramid_jinja2')
    config.add_settings({'jinja2.i18n.gettext': TemplateTranslations})
    config.add_settings({'jinja2.trim_blocks': 'true'})
    jinja_filters = {
        'static_url': 'pyramid_jinja2.filters:static_url_filter',
        'quoteplus': 'urllib.parse.quote_plus',
    }
    add_jinja2_filters(config, jinja_filters)
    return config
