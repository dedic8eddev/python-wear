import uuid

from bson import ObjectId

from spynl.api.auth.exceptions import CannotRetrieveUser, UserNotActive


def get_current_tenant_id(request):
    """
    Return the tenant ID on whose behalf the authenticated
    user is working for this session.
    """
    if not request.authenticated_userid:
        return None

    tid = None

    token = validate_token(request)
    if token and 'tenant_id' in token:
        tid = token['tenant_id']
    elif 'tenant_id' in request.session:
        tid = request.session['tenant_id']

    if ObjectId.is_valid(tid):
        tid = ObjectId(tid)
    return tid


def get_requested_tenant_id(request):
    """
    Return the tenant ID on whose data this request
    should work on.
    This is by default the current tenant (see get_current_tenant_id),
    unless the request has requested a different one specifically
    by using a tenant-based URL route (see plugger.py).
    """
    if request.matchdict and 'tenant_id' in request.matchdict:
        return request.matchdict['tenant_id']
    else:
        return get_current_tenant_id(request)


def validate_token(request):
    """
    Retrieve the token from the Authorization header and return its payload.
    """
    if 'Authorization' in request.headers:
        try:
            realm, token = request.headers['Authorization'].split(' ', 1)
        except ValueError:
            return None

        if realm.lower() != 'bearer':
            return None
    elif 'X-Swapi-Authorization' in request.headers:
        token = request.headers['X-Swapi-Authorization']
    else:
        return None

    try:
        token = uuid.UUID(token)
    except ValueError:
        return None

    return request.pymongo_db.tokens.find_one({'token': token, 'revoked': False})


def get_authenticated_user(request):
    """
    Get the user entry for the authenticated user from the database,
    return None if there is no authenticated user to be found.

    This function is used to cache the current user data per request (see
    plugger.py)
    """
    userid = request.authenticated_userid
    if userid is None:
        return None
    user = request.pymongo_db.users.find_one({'_id': userid})

    if not user:
        raise CannotRetrieveUser()
    if not user.get('active'):
        raise UserNotActive(user['username'])

    return user
