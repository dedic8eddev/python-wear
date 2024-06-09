"""
tenant ID - related utilities
"""

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalParameter, SpynlException

# import MASTER_TENANT_ID, because a lot of files import it from this file:
from spynl.api.auth.utils import MASTER_TENANT_ID  # noqa: F401
from spynl.api.auth.utils import check_key, get_user_info
from spynl.api.mongo import MongoResource
from spynl.api.mongo.utils import extend_filter


def get_allowed_tenant_ids(request):
    """Return a list of allowed tenant IDs for the current user."""
    userid = request.authenticated_userid
    if userid:
        user_info = get_user_info(request, 'cached_user')
        return user_info.get('tenant_id', [])
    else:
        return []


def extend_filter_by_tenant_id(filtr, tenants, context, include_public=False):
    """
    Make sure the user's tenant_id is/are in there.

    The parameter "tenants" is a list of tenant IDs.
    We prefer == over $in for speed.
    If include_public is True and the context is one known
    for containing (also) public documents, the filter will also affect
    documents without tenant_id. This slows down queries, so we use it
    with care. Checking for None allows public documents to be retrieved
    (requires index on tenant_id to work correctly).

    Special treatment is needed for the 'tenants' collection, because there
    the field to look at is '_id' instead of 'tenant_id'
    """
    if len(tenants) == 1:
        tenant_filter = tenants[0]
    else:
        tenant_filter = {'$in': tenants}

    extended_filtr = extend_filter(filtr, {'tenant_id': tenant_filter})

    if isinstance(context, MongoResource):
        # use a different id filter for 'tenants' collection
        if context.collection == 'tenants':
            extended_filtr = extend_filter(filtr, {'_id': tenant_filter})
        # also search for public documents if applicable
        elif include_public and context.contains_public_documents:
            extended_filtr = extend_filter(
                filtr, {'$or': [{'tenant_id': tenant_filter}, {'tenant_id': None}]}
            )
        # We should not allow no tenant at all if the context contains no
        # public documents
        else:
            if tenants == [] or not all(tenants):  # all([]) = True
                raise SpynlException(_('no-tenant-id-in-filter'))

    return extended_filtr


def reject_search_by_tenant_id(filtr):
    """
    If user attempts to search by tenant_id then return a Bad Request.

    Searching by tenant_id can be a security risk as it could potentially allow
    a user to view/manipulate data that does not belong to them.
    """
    if check_key(filtr, 'tenant_id'):
        raise IllegalParameter(_('no-search-by-tenant-id'))


def validate_tenant_id(tid):
    """Tenant has to be a string or None."""
    msg = None
    if tid is not None and not isinstance(tid, str):
        msg = _('tenant-id-not-string', mapping={'type': type(tid)})
    elif tid == '':
        msg = _('tenant-id-null')
    else:
        pass
        # msg = 'Importing public documents is not allowed.'
        # msg = 'No tenants available and user is not admin.'
        # msg = 'Removing public documents is not allowed.'
        # IllegalAction(msg)
    if msg:
        raise SpynlException(msg)
