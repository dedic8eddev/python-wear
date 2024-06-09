import json
import os
import sys

from spynl_dbaccess.database import default_timestamp_callback

from spynl.api.auth.utils import MASTER_TENANT_ID


def find_callback(requested_tenant_id, current_tenant_id, filter, collection):
    collection_name = collection.pymongo_collection.name
    if collection_name == 'users':
        return filter  # add special handling SPAPI-723

    # if a master user is doing a find, and isn't accessing a tenant endpoint via
    # /tenants/tenantid/endpoint, allow them to filter based on tenant themselves.
    if (
        current_tenant_id == MASTER_TENANT_ID
        and current_tenant_id == requested_tenant_id
    ):
        return filter

    if not filter:
        filter = {}

    if collection_name == 'tenants':
        filter['_id'] = requested_tenant_id
    else:
        filter['tenant_id'] = requested_tenant_id

    return filter


def save_callback(tenant_id, data, collection):
    collection_name = collection.pymongo_collection.name
    if collection_name == 'users':
        return data  # add special handling SPAPI-723
    if collection_name == 'tokens':
        data['tenant_id'] = tenant_id
    elif collection_name == 'tenants':
        # Either a new tenant is created, or one is updated. In the update
        # the find callback is used, and changing the _id is not possible.
        pass
    else:
        data['tenant_id'] = [tenant_id]
    return data


def aggregate_callback(tenant_id, pipeline, collection):
    collection_name = collection.pymongo_collection.name
    if collection_name == 'users':
        return pipeline  # add special handling SPAPI-723
    if collection_name == 'tenants':
        pass
    elif not pipeline:
        pipeline = [{'$match': {'tenant_id': tenant_id}}]
    elif '$match' in pipeline[0]:
        pipeline[0]['$match']['tenant_id'] = tenant_id
    else:
        pipeline.insert(0, {'$match': {'tenant_id': tenant_id}})
    return pipeline


try:
    with open(os.path.join(sys.prefix, 'versions.json')) as f:
        VERSIONS = json.loads(f.read())
except FileNotFoundError:
    VERSIONS = None


def timestamp_callback(user_, path, data, collection, update_filter=None, **kwargs):
    return default_timestamp_callback(
        data,
        collection,
        update_filter=update_filter,
        user=user_,
        action=path,
        versions=VERSIONS,
    )
