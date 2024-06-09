"""
plugger.py is used by spynl Plugins to say which endpoints are resouces it will use.
"""
from functools import partial

from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.settings import asbool

from spynl_dbaccess.database import Database

from spynl.main.serial.objects import add_decode_function

from spynl.api.hr.resources import AccountProvisioning
from spynl.api.mongo.callbacks import (
    aggregate_callback,
    find_callback,
    save_callback,
    timestamp_callback,
)
from spynl.api.mongo.db_endpoints import (
    add,
    count,
    db_connection_health,
    get,
    remove,
    save,
    single_edit,
)
from spynl.api.mongo.serial_objects import decode_date, decode_id
from spynl.api.mongo.utils import validate_filter_and_data


def add_dbaccess_endpoints(config, resource, endpoints):
    """
    Add standard old style db access endpoints.
    """
    if 'get' in endpoints:
        config.add_endpoint(
            get, '/', context=resource, permission='read', request_method='GET'
        )
        config.add_endpoint(get, 'get', context=resource, permission='read')
    if 'edit' in endpoints:
        config.add_endpoint(
            single_edit, '/', context=resource, permission='edit', request_method='POST'
        )
        config.add_endpoint(single_edit, 'edit', context=resource, permission='edit')
    if 'count' in endpoints:
        config.add_endpoint(count, 'count', context=resource, permission='read')
    if 'add' in endpoints:
        config.add_endpoint(add, 'add', context=resource, permission='add')
    if 'save' in endpoints:
        config.add_endpoint(save, 'save', context=resource, permission='edit')
    if 'remove' in endpoints:
        config.add_endpoint(remove, 'remove', context=resource, permission='delete')


def includeme(config):
    """Set up MongoDB connection, adds endpoints."""
    settings = config.get_settings()

    config.add_view_deriver(validate_filter_and_data)

    # add mongo specific decoding and encoding functions
    add_decode_function(
        config, decode_id, ['_id', '_uuid', 'created.user._id', 'modified.user._id']
    )
    add_decode_function(
        config,
        decode_date,
        ['date', 'created.date', 'modified.date', 'periodStart', 'periodEnd'],
    )

    # set up connection to DB

    db = Database(
        host=settings['spynl.mongo.url'],
        database_name=settings['spynl.mongo.db'],
        ssl=asbool(settings.get('spynl.mongo.ssl')),
        auth_mechanism=settings.get('spynl.mongo.auth_mechanism'),
        max_limit=int(settings['spynl.mongo.max_limit']),
        max_agg_limit=int(settings['spynl.mongo.max_agglimit']),
    )

    def add_db_property(request):
        # NOTE we do not set the callbacks for every request. So reset them to their
        # defaults to prevent them from carrying over from the last request that did
        # set them, even if the tenant_id is different (DANGER)
        db.reset_callbacks()

        # NOTE we do NOT want to set these callbacks on account provisioning since the
        # point is to operate on multiple other tenants.
        if isinstance(request.context, AccountProvisioning):
            return db

        tenant_id = request.requested_tenant_id
        try:
            timestamp_user = {
                '_id': request.cached_user.get('_id'),
                'username': request.cached_user.get('username'),
            }
        except AttributeError:
            timestamp_user = None

        db.timestamp_callback = partial(
            timestamp_callback, timestamp_user, request.path
        )
        db.find_callback = partial(find_callback, tenant_id, request.current_tenant_id)
        db.save_callback = partial(save_callback, tenant_id)
        db.aggregate_callback = partial(aggregate_callback, tenant_id)

        return db

    config.add_request_method(add_db_property, name='db', reify=True)

    # This is the original db object from pymongo. It does not do anything extra like
    # our custom db wrapper. Useful for internal logic.
    config.add_request_method(lambda r: db.pymongo_db, name='pymongo_db', reify=True)

    # we use this for pre spynl_data code with original db_access.
    config.add_settings({'spynl.mongo.db': db.pymongo_db})

    config.add_endpoint(
        db_connection_health, 'db-status', permission=NO_PERMISSION_REQUIRED
    )
