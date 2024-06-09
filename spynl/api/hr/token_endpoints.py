import uuid

from spynl_schemas import TokenSchema

from spynl.locale import SpynlTranslationString as _

from spynl.main.utils import get_settings, required_args

from spynl.api.auth.token_authentication import generate, legacy_token_request, revoke
from spynl.api.auth.utils import MASTER_TENANT_ID, audit_log, get_user_info
from spynl.api.hr.exceptions import TokenError

AUTH_TOKEN = 'auth-token'
ROLES = ['token-webshop-admin']


@audit_log(message='Token request')
def generate_token(request):
    """
    Generate a token for a user.

    ---
    post:
      description: >
        Request a token for authentication. Usage is through the
        "Authorization" header. This is the single time the token is sent
        without obfuscation. If you lose it it cannot be recovered. This is
        done either by the owner, or by an admin for a specific tenant. In the
        latter case the token will be assigned to the first owner found on the
        tenant.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        description | string    | | A comment to distinguish the token from others.

        ### Response

        JSON keys         | Type   | Description\n
        ------------      | ------ | -----------\n
        status            | string | 'ok' or 'error'\n
        data              | object | The token object containing its value \
                                     and metadata.\n
        developer_message | string | Example usage.

      tags:
        - tokens
    """
    tenant_id = request.requested_tenant_id
    user_info = get_user_info(request, purpose='stamp')['user']

    if (
        request.current_tenant_id == MASTER_TENANT_ID
        and request.current_tenant_id != request.requested_tenant_id
    ):
        tenant = request.db.tenants.pymongo_find_one(tenant_id)
        if not tenant.get('active'):
            raise TokenError(_('auth-no-active-tenant', mapping={'tenant': tenant_id}))

        try:
            owner_id = tenant['owners'][0]
        except (KeyError, IndexError):
            raise TokenError(_('no-owner-on-tenant', mapping={'tenant_id': tenant_id}))

        token_user_id = request.db.users.find_one({'_id': owner_id}, {'_id': 1})['_id']
    else:
        token_user_id = user_info['_id']

    new_token = uuid.uuid4()
    description = request.args.get('description', '')
    legacy_token_request(new_token, request, description=description)

    token = generate(
        request.db,
        token_user_id,
        tenant_id,
        usage_plan=get_settings('spynl.swapi_usage_plan'),
        payload={
            'type': AUTH_TOKEN,
            'roles': ROLES,
            'description': description,
        },
        token_=new_token,
    )

    response = dict(
        data=TokenSchema().dump(token),
        status='ok',
        developer_message='Example: "Authorization: Bearer [TOKEN]"',
    )
    return response


@required_args('token')
def revoke_token(request):
    """
    Revoke a token.

    ---
    post:
      description: >
        Revoke a token.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        token        | string    | &#10004; | The token or its id.

        ### Response

        JSON keys         | Type   | Description\n
        ------------      | ------ | -----------\n
        status            | string | 'ok' or 'error'\n

      tags:
        - tokens
    """
    try:
        token = revoke(request.db, request.args['token'])
    except ValueError:
        raise TokenError(_('cant-revoke-token'))

    legacy_token_request(token, request, revoke=True)

    return {'status': 'ok'}


def list_tokens(request):
    """
    Return a list of tokens.

    The token values are obfuscated and presented for a human readable overview
    only.

    ---
    get:
      description: >
        Request a list of tokens, active and revoked.

        ### Response

        JSON keys         | Type   | Description\n
        ------------      | ------ | -----------\n
        status            | string | 'ok' or 'error'\n
        data              | object | Arrays of active and revoked tokens.

      tags:
        - tokens
    """
    schema = TokenSchema(context={'obfuscate': True}, many=True)
    result = request.db.tokens.find(
        {'type': AUTH_TOKEN, 'tenant_id': request.requested_tenant_id},
        sort=[['revoked', 1]],
    )
    tokens = schema.dump(result)
    i = 0
    for i, token in enumerate(tokens):
        if token['revoked']:
            break
    else:
        # if no tokens have been revoked, we slice after the last element.
        i += 1

    return {'data': {'active': tokens[:i], 'revoked': tokens[i:]}}
