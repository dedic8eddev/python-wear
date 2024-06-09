"""
Defines methods to access MongoDB collections.

Used by views in here and in other spynl.* modules.

In general, we try to read from secondary MongoDB clusters
in order to protect database performance but write to
primary.
"""

from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction, SpynlException
from spynl.main.utils import get_logger, get_settings

from spynl.api.mongo.protection import reject_excluded_operators
from spynl.api.mongo.utils import log_db_query


@log_db_query
def get(ctx, request, filtr, fields, limit=0, skip=0, sort=None):
    """
    Find data in a MongoDB collection.

    Returns the data and three flags, the limit imposed (never more than
    max_limit from settings) and the skip used.
    """
    if sort and isinstance(sort, tuple):  # TODO: how does JSON support tuples?
        sort = [sort]
    reject_excluded_operators(filtr)

    settings = get_settings()
    max_limit = int(settings.get('spynl.mongo.max_limit'))
    if limit > max_limit or limit == 0:
        limit = max_limit

    data = request.db[ctx].find(filtr, fields, skip=skip, limit=limit, sort=sort)

    return {'data': list(data), 'limit': limit, 'skip': skip}


@log_db_query
def get_include_public_documents(
    ctx, request, filtr, fields, limit=0, skip=0, sort=None
):
    """
    Find data in a MongoDB collection, but include public documents

    Returns the data and three flags, the limit imposed (never more than
    max_limit from settings) and the skip used.
    """
    if sort and isinstance(sort, tuple):  # TODO: how does JSON support tuples?
        sort = [sort]
    reject_excluded_operators(filtr)

    settings = get_settings()
    max_limit = int(settings.get('spynl.mongo.max_limit'))
    if limit > max_limit or limit == 0:
        limit = max_limit

    filtr['tenant_id'] = {'$in': [request.requested_tenant_id, None]}

    data = request.db[ctx].pymongo_find(
        filtr, fields, skip=skip, limit=limit, sort=sort
    )

    return {'data': list(data), 'limit': limit, 'skip': skip}


@log_db_query
def count(ctx, request, filtr):
    """
    The count function returns the count of a MongoDB collection.

    We prefer to read from secondary MongoDB nodes as these operations
    can be expensive but data does not need to be absolutely fresh.
    """
    reject_excluded_operators(filtr)

    count_num = request.db[ctx].count_documents(filtr)

    return {'count': count_num}


@log_db_query
def add(ctx, request, data):
    """
    Invoke MongoDBs insert method with the requested arguments.

    Data should be a list of new documents.
    Returns new IDs of the inserted documents as 'data'.
    """
    for doc in data:
        doc.setdefault('active', True)

    # insert all records from incoming data and return their new representation
    new_ids = [
        str(request.db[ctx].insert_one(document).inserted_id) for document in data
    ]
    response = {'data': new_ids}

    return response


@log_db_query
def edit(ctx, request, filtr, update):
    """Invoke MongoDBs update function with the requested arguments."""
    reject_excluded_operators(filtr)

    matched_docs = list(request.db[ctx].find(filtr, ['_id']))
    if not matched_docs:
        raise IllegalAction(_('no-document-found'))

    operators = {
        '$inc',
        '$mul',
        '$rename',
        '$set',
        '$unset',
        '$min',
        '$max',
        '$currentDate',
        '$push',
        '$pop',
        '$pull',
        '$slice',
        '$addToSet',
    }
    #  Check what operators will be used.
    #  It also works if user passes something completely different as operator.
    operators_used = set(update) & operators
    if not operators_used:
        raise IllegalAction(_('editing-without-mongodb-operator'))
    else:  # Make sure 'created' and 'modified' don't exist in ANY operator.
        for operator in operators_used:
            update[operator].pop('created', None)
            update[operator].pop('modified', None)

    if len(matched_docs) == 1:
        result = request.db[ctx].update_one(filtr, update)
    else:
        result = request.db[ctx].update_many(filtr, update)
        get_logger().error(
            'Single edit is being used to update_many. This is deprecated.'
        )

    result = {
        'ok': result.acknowledged,
        'n': result.modified_count,
        'updatedExisting': result.matched_count,
    }

    return {'data': result}


@log_db_query
def save(ctx, request, documents):
    """Invoke MongoDBs save function with the requested arguments."""

    results = []
    for document in documents:
        document.setdefault('active', True)
        if document.get('_id'):
            result = request.db[ctx].upsert_one({'_id': document['_id']}, document)
            if result.upserted_id:
                results.append(result.upserted_id)
            else:
                results.append(document['_id'])
        else:
            result = request.db[ctx].insert_one(document)
            results.append(result.inserted_id)
    return {'data': results}


@log_db_query
def save_with_incremental_id(ctx, request, documents):
    """
    For each document, find the next numeric _id incrementally, set it on the
    document and then insert to the DB.
    Return list of inserted ids.
    """
    ids = []
    for document in documents:
        lowerbound = 100000
        max_ = request.db[ctx].find_one(
            {'_id': {'$regex': '^[0-9]{6,}$'}}, {'_id': 1}, sort=[('_id', DESCENDING)]
        )
        if not max_:
            id = lowerbound
        else:
            id = int(max_['_id']) + 1

        for i in range(1000):
            document['_id'] = str(id)
            try:
                result = request.db[ctx].insert_one(document)
                ids.append(result.inserted_id)
                break
            except DuplicateKeyError:
                id += 1
        else:
            raise SpynlException(_('cannot-find-next-incremental-id'))

    return ids


@log_db_query
def remove(ctx, request, filtr):
    """Invoke MongoDBs delete function with the requested arguments."""
    reject_excluded_operators(filtr)

    result = request.db[ctx].delete_one(filtr)

    return {'data': {'ok': result.deleted_count}}
