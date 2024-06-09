"""Utility methods for the spynl.mongo module."""

import time
from copy import deepcopy

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalParameter
from spynl.main.utils import find_view_name, get_logger, get_settings

from spynl.api.mongo.resources import MongoResource


def validate_filter_and_data(endpoint, info):
    """
    Make sure that the filter and data parameters fulfill basic requirements. Endpoints
    can then operate assuming these requirements are fulfilled. The requirements are
    that "filter" is a dict and "data" is a list. For the filter requirement, we raise;
    for the data requirement, we wrap the given data into a list.
    """
    if info.options.get('is_error_view', False) is True:
        return endpoint  # no need to validate (again)

    def wrapper_view(context, request):
        """raise if filter or data don't fulfil expectations"""
        if not isinstance(context, MongoResource):
            return endpoint(context, request)

        endpoint_method = find_view_name(request)
        if 'filter' in request.args and not isinstance(request.args['filter'], dict):
            raise IllegalParameter(_('incorrect-filter-type'))

        if 'data' in request.args and endpoint_method in ('add', 'save'):
            if not isinstance(request.args['data'], list):
                # NOTE: Removing this might also mean we have to change new style
                # endpoints, see e.g. retail customer save
                request.args['data'] = [request.args['data']]

        return endpoint(context, request)

    return wrapper_view


validate_filter_and_data.options = ('is_error_view',)


# ---- date utilities


def log_db_query(dbfunc):
    """
    Log meta information about a database query, like its time.

    Log level adapts to the execution time.
    """

    def wrapper(ctx, request, filter_or_data, *args, **kwargs):
        "record start time, execute db call, record finish time"
        log = get_logger()
        settings = get_settings()
        start_time = time.time()

        result = dbfunc(ctx, request, filter_or_data, *args, **kwargs)

        # decide on log level
        log_function = log.debug
        exe_time = time.time() - start_time
        if exe_time > int(settings.get('spynl.querylog_info_threshold', 5)):
            log_function = log.info
        if exe_time > int(settings.get('spynl.querylog_warn_threshold', 15)):
            log_function = log.warn

        payload = {}
        if isinstance(filter_or_data, dict):
            payload['filter'] = filter_or_data
        elif isinstance(filter_or_data, list):
            payload['data'] = filter_or_data
        if dbfunc.__name__ == 'edit':
            payload['update'] = args[0]
        log_function(
            'MongoDB was queried on collection "%s" with method "%s".',
            ctx.collection,
            dbfunc.__name__,
            extra=dict(
                payload=payload,
                meta=dict(
                    collection=ctx.collection,
                    method=dbfunc.__name__,
                    execution_time=exe_time,
                ),
            ),
        )
        return result

    return wrapper


def extend_filter(filtr, condition):
    """
    Add a condition to the filter.

    A top-level $and will be added if a key in condition is already being used.
    """
    if len(filtr) == 0:
        new_filtr = condition
    else:
        new_filtr = deepcopy(filtr)
        all_keys = list(new_filtr.keys()) + list(condition.keys())
        if len(all_keys) == len(set(all_keys)):
            new_filtr.update(condition)
        else:
            new_filtr = {'$and': [filtr, condition]}
    return new_filtr


def db_safe_dict(dictionary):
    """
    Return dictionary.

    If dictionary is a dictionary, return a new dictionary, making sure that
    keys in the new dictionary are safe to be stored. Right now we do this if a
    query filter is to be stored, where the "$" and "." in keys are not
    allowed.
    """
    if not isinstance(dictionary, dict):
        return dictionary
    new = {}
    for k, v in dictionary.items():
        if isinstance(v, dict):
            v = db_safe_dict(v)
        if isinstance(v, list):
            tmp_v = []
            for item in v:
                if isinstance(item, dict):
                    tmp_v.append(db_safe_dict(item))
                else:
                    tmp_v.append(item)
            v = tmp_v
        new[k.replace('$', 'dbm:$').replace('.', '_dot_')] = v
    return new


def get_first_keys_of_indexes(indexes_dict):
    """
    Return a set of first key indexes from a collection index dictionary.

    In case of multiple keys, the first key is picked because MongoDB will make
    use of the index if query contains the first key from a multikey(if the
    index contains 2 keys).
    """
    keys = [value['key'] for value in indexes_dict.values()]
    first_keys = [element[0][0] for element in keys]
    return set(first_keys)


def get_filter_keys(filtr):
    """Return a set of the keys that a Mongo query contains."""
    keys = []
    if isinstance(filtr, dict):
        for key, value in filtr.items():
            if key.startswith('$'):
                keys.extend(get_filter_keys(value))
            else:
                keys.append(key)
                keys.append(key.split('.')[0])
    elif isinstance(filtr, list):
        for element in filtr:
            keys.extend(get_filter_keys(element))
    return set(keys)


def insert_foxpro_events(
    request, data, query_function, *args, check_empty=False, **kwargs
):
    """
    Generate fpqueries using the data and function provided and save the events to the
    database.
    """
    common_event_data = [
        ('token', request.session_or_token_id),
        ('tenant_id', request.requested_tenant_id),
        ('username', request.cached_user.get('username', request.cached_user['_id'])),
        *args,
    ]
    fpqueries = [
        {
            'confirmed': False,
            'method': method,
            'fpquery': fpquery,
            'tenant_id': [request.requested_tenant_id],
        }
        for method, fpquery in query_function(data, *common_event_data, **kwargs)
    ]
    if check_empty and not fpqueries:
        return
    request.db.events.insert_many(fpqueries)
