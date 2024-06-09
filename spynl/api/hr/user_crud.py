"""View for the creation, listing and deletion of users."""


from bson import ObjectId

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalParameter, SpynlException
from spynl.main.utils import required_args

from spynl.api.auth.session_cycle import (
    TENANT_FIELDS,
    USER_DATA_WHITELIST,
    USER_EDIT_WHITELIST,
)
from spynl.api.auth.tenantid_utils import MASTER_TENANT_ID, get_allowed_tenant_ids
from spynl.api.hr.exceptions import UserDoesNotExist
from spynl.api.hr.utils import (
    check_user_belongs_to_tenant,
    create_user,
    send_pwdreset_key,
    validate_device_id,
)
from spynl.api.mongo.db_access import edit as db_edit
from spynl.api.mongo.db_endpoints import count as generic_count
from spynl.api.mongo.db_endpoints import get as generic_get


@required_args('username', 'type')
def add_user(ctx, request):
    """
    Create a new user.

    ---

    post:
      tags:
        - data
      description: >
        Create a new user for the requested tenant, given a username and a user
        type.
        Potentially also a user object with some initial data.

        A password reset key is sent to the email address.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        username  | string       | &#10004; | username for new user\n
        type      | string       | &#10004; | user type ('device', 'api', or
        'standard')\n
        user      | object       |          | user object with information
        about the new user\n


        ### Response

        JSON keys | Type | Description\n
        --------- | ---- | -----------\n
        status    | string | 'ok' or 'error'\n
        message   | string | succes or error description\n

    """
    args = request.args
    tid = request.requested_tenant_id

    # get user object from request
    new_user = args.get('user', {})
    new_user['username'] = args.get('username')
    new_user['email'] = args.get('email')
    new_user['type'] = args.get('type')

    create_user(
        request,
        new_user=new_user,
        tenant_id=tid,
        auth_userid=request.authenticated_userid,
        action='users/add',
    )

    # Send password reset key to the new user or tenant owner
    sent_to = send_pwdreset_key(request, new_user, first=True)
    if sent_to:
        msg = _('add-user-return-1', mapping={'sent_to': ','.join(sent_to)})
        return {'status': 'ok', 'message': msg}
    else:
        msg = _('add-user-return-2')
        return {'status': 'error', 'message': msg}


@required_args('_id', 'data')
def edit_user(ctx, request):
    """
    Edit a user.

    ---
    post:
      tags:
        - data
        - account management
      description: >
        Takes data which is set on a user record. Only white-listed fields can
        be edited, others will be ignored.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        _id       | string or dict | &#10004; | To identify record(s).
        A filter dict (e.g. with $in) or the user's _id as a string.\n
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
    return _update_user(ctx, request, '$set')


def _update_user(ctx, request, action):
    """
    Update a user, used by edit_user and remove_user.

    action is either $set or $unset
    """
    user_id = request.args['_id']
    if (
        not isinstance(user_id, ObjectId)
        and not isinstance(user_id, str)
        and not isinstance(user_id, dict)
    ):
        raise IllegalParameter(_('update-user-error-1'))
    data = request.args['data']

    # Data must be a dict
    if not isinstance(data, dict):
        raise IllegalParameter(_('update-user-error-2'))

    # An empty data dict is not allowed, it will cause a MongoDB error
    if len(data.keys()) == 0:
        raise SpynlException(_('update-user-error-3'))

    affected_fields = []

    user = request.db[ctx].find_one({'_id': user_id}, ['_id', 'tenant_id', 'deviceId'])

    if not user:
        raise UserDoesNotExist(user_id)

    check_user_belongs_to_tenant(request.requested_tenant_id, user)

    # Only allow whitelisted properties to be edited.
    action_data = {}
    for key in data:
        # Handle dot notation i.e. key.someproperty
        parent_key = key.split('.')[0]
        if parent_key in USER_EDIT_WHITELIST:
            affected_fields.append(key)
            action_data[key] = data[key]

    if len(action_data.keys()) == 0:
        raise SpynlException(_('update-user-error-4'))

    if data.get('deviceId') and data['deviceId'] != user.get('deviceId'):
        validate_device_id(request.db, data['deviceId'], request.requested_tenant_id)

    # determine if data was skipped before stamp adds keys
    data_skipped = False
    if len(action_data.keys()) < len(data.keys()):
        data_skipped = True

    # Save user(s) in mongo
    db_edit(ctx, request, {'_id': user_id}, {action: action_data})

    message = _('update-user-return-ok', mapping={'user_id': user_id}).translate(
        request.localizer
    )
    if data_skipped:
        message += _('update-user-return-not-all-fields-affected').translate(
            request.localizer
        )

    return {'message': message, 'affected_fields': affected_fields}


def get_users(ctx, request):
    """
    Get users.

    ---

    post:
      tags:
        - data
      description: >
        Gets users which the authenticated user has access to,
        but cleans sensitive data before returning.

        The number of actual data entries returned will never be more than
        the maximum limit. This means that there might be more
        data that can be retrieved using skip.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        filter    | object | | the query to run against MongoDB\n
        fields    | array  | | a list of fields to return
        ['field1', 'field2']\n
        limit     | int    | | the number of documents to return\n
        skip      | int    | | the number of documents to skip\n
        sort      | array  | | a list of lists of fields and sort order ex.
        [['field', 1]]\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error \n
        data      | object | the actual result of the request.\n
        limit     | int | the limit used, either
        the maximum limit, or smaller if requested\n
        skip      | int | number of entries to skip\n

    """
    response = generic_get(ctx, request)
    loggedin_user_tenants = get_allowed_tenant_ids(request)
    # Remove sensitive data from users in response
    for doc in response['data']:
        for key in doc.copy():
            if key not in USER_DATA_WHITELIST:
                doc.pop(key, None)
        for field in TENANT_FIELDS:
            if field in doc and isinstance(doc[field], dict):
                for tenant in doc[field].copy():
                    if (
                        tenant not in loggedin_user_tenants
                        and request.current_tenant_id != MASTER_TENANT_ID
                    ):
                        doc[field].pop(tenant, None)

    return response


def count_users(ctx, request):
    """
    Count users.

    ---
    post:
      tags:
        - data
      description: >
        Count the users returned by the given filter.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        filter    | object | | the query to select what subset to count\n


        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error\n
        count     | int | number of $resource
    """
    return generic_count(ctx, request)
