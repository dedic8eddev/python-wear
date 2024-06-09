""" Views for handling tenants """

from bson import ObjectId

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalParameter, SpynlException
from spynl.main.utils import required_args

from spynl.api.auth.exceptions import TenantDoesNotExist
from spynl.api.mongo.db_access import edit as db_edit
from spynl.api.mongo.db_endpoints import get as generic_get

# Whitelist for editing tenants, there are specific endpoints for editing
# settings and applications.
TENANT_EDIT_WHITELIST = (
    'vatNumber',
    'addresses',
    'legalname',
    'bic',
    'gln',
    'bankAccountName',
    'bankAccountNumber',
    'website',
    'active',
    'dimension4',
    'name',
    'cocNumber',
    'contacts',
    'wholesale',
    'retail',
)
# The whitelist for viewing tenants is the editing whitelist plus more
TENANT_DATA_WHITELIST = TENANT_EDIT_WHITELIST + (
    '_id',
    'owners',
    'created',
    'modified',
    'applications',
    'countryCode',
)


def get_tenants(ctx, request):
    """
    Get tenants and restrict to whitelisted properties

    ---
    get:
      description: >
        Get function for tenants. Only whitelisted properties are returned.

        The filter parameter can be used to select a specific set of $resource.
        Returns status (ok|error), and if status=ok also a data array with
        actual data and meta info: limit, and skip.

        The number of actual data entries returned will never be more than
        the maximum limit. This means that there might be more
        data that can be retrieved using skip.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        filter    | object | | the query to run against MongoDB\n
        limit     | int    | | the number of documents to return\n
        skip      | int    | | the number of documents to skip\n
        fields    | array  | | a list of fields to return
        ['field1', 'field2']\n
        sort      | array  | | a list of lists of fields and sort order ex.
        [['field', 1]]\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error \n
        data      | object | the actual result of the request.\n
        limit     | int | the limit used, either
        the max limit, or smaller if requested\n
        skip      | int | number of entries to skip\n

      tags:
        - data
    """
    response = generic_get(ctx, request)

    # Remove sensitive data from users in response
    for doc in response['data']:
        for key in doc.copy():
            if key not in TENANT_DATA_WHITELIST:
                doc.pop(key, None)

    return response


@required_args('data')
def edit_tenant(ctx, request):
    """
    Edit a tenant, only whitelisted properties can be edited

    ---
    post:
      tags:
        - data
        - account management
      description: >
        Takes data which is set on a tenant record. Only white-listed fields can
        be edited, others will be ignored. Only users with sw-roles can edit
        tenants.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        data      | dict         | &#10004; | Data to be updated, will become
        a parameter to the MongoDB $set operator.\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error'\n
        message   | string | succes or error description\n
        affected_fields | list | list of fields which were affected (only
        white-listed fields are applied to the DB)
    """
    tenant_id = request.requested_tenant_id
    if not isinstance(tenant_id, (ObjectId, str)):
        raise IllegalParameter(_('edit-tenant-error-1'))
    data = request.args['data']

    # Data must be a dict, and cannot be empty, it will cause a MongoDB error
    if not isinstance(data, dict):
        raise IllegalParameter(_('edit-tenant-error-2'))
    if not data:
        raise SpynlException(_('edit-tenant-error-3'))

    affected_fields = []

    if not request.db[ctx].find_one({'_id': tenant_id}, ['_id']):
        raise TenantDoesNotExist(tenant_id)

    # Only allow whitelisted properties to be edited.
    action_data = {}
    for key in data:
        # Handle dot notation i.e. key.someproperty
        parent_key = key.split('.')[0]
        if parent_key in TENANT_EDIT_WHITELIST:
            affected_fields.append(key)
            action_data[key] = data[key]

    if not action_data:
        raise SpynlException(_('edit-tenant-error-5'))
    # determine if data was skipped before stamp adds keys
    data_skipped = len(action_data) < len(data)

    # Save tenant in mongo
    db_edit(ctx, request, {'_id': tenant_id}, {'$set': action_data})

    message = _('edit-tenant-return-1', mapping={'tenant_id': tenant_id}).translate(
        request.localizer
    )
    if data_skipped:
        message += _('edit-tenant-return-2').translate(request.localizer)

    return {'message': message, 'affected_fields': affected_fields}
