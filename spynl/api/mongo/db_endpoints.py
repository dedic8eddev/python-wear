"""View functions for the spynl.mongo module."""

import sys

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import date_to_str, now
from spynl.main.utils import required_args

from spynl.api.mongo import db_access
from spynl.api.mongo.query_schemas import SortSchema
from spynl.api.retail.exceptions import InvalidParameter


def db_connection_health(request):
    """
    Returns current health of database connection.

    If it is out, give error code 503 (Service Unavailable)
    ---
    get:
      description: >
        Returns status 'healthy' if the database connection is ok, and status
        'error' with a message if there is a problem. If the database is out,
        **error code 503** is given (Service Unavailable)

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | 'healthy' or 'error'\n
        time      | string | time\n
        message   | string | information about the database connection (not
        present if status is healthy)\n

      tags:
        - contact
    """
    response = dict(time=date_to_str(now()))
    try:
        if not all(
            (
                request.db.users.find_one(),
                request.db.transactions.find_one(),
                request.db.customers.find_one(),
            )
        ):
            response['message'] = _('db-connection-health')
            response['status'] = 'error'
            request.response.status_int = 503
        else:
            response['status'] = 'healthy'
    except Exception:
        response['status'] = 'error'
        response['message'] = sys.exc_info()[0].__name__
        request.response.status_int = 503

    return response


def get(ctx, request):
    """
    (old) Get data from the $resource collection.

    ---
    get:
      description: >
        Get function for **$resource**. The filter parameter can be used to
        select a specific set of $resource. Returns status (ok|error), and if
        status=ok
        also a data array with actual data and meta info: limit, and skip.\n

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
        [['field', 1]], or an array of dicts: An array of objects each containing a
        'field' and 'direction' key. (e.g. [{'field': 'x', 'direction': 1}]\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error \n
        data      | object | the actual result of the request.\n
        limit     | int | the limit used, either
        the maximum limit, or smaller if requested\n
        skip      | int | number of entries to skip\n

      tags:
        - data
    """
    args = {}
    for key in 'limit', 'skip':
        try:
            args[key] = int(request.args.get(key, 0))  # 0 means no limit or no skip
        except ValueError:
            raise InvalidParameter(key)

    filtr = request.args.get('filter', {})
    fields = request.args.get('fields', {'modified_history': 0})
    sort = request.args.get('sort')
    if sort:
        sort = SortSchema(many=True).load(sort)

    return db_access.get(ctx, request, filtr, fields, args['limit'], args['skip'], sort)


def get_include_public_documents(ctx, request):
    """
    (old) Get data from the $resource collection, include public documents.

    ---
    get:
      description: >
        Get function for **$resource**. The filter parameter can be used to
        select a specific set of $resource. Returns status (ok|error), and if
        status=ok
        also a data array with actual data and meta info: limit, and skip.\n

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
        [['field', 1]], or an array of dicts: An array of objects each containing a
        'field' and 'direction' key. (e.g. [{'field': 'x', 'direction': 1}]\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error \n
        data      | object | the actual result of the request.\n
        limit     | int | the limit used, either
        the maximum limit, or smaller if requested\n
        skip      | int | number of entries to skip\n

      tags:
        - data
    """
    args = {}
    for key in 'limit', 'skip':
        try:
            args[key] = int(request.args.get(key, 0))  # 0 means no limit or no skip
        except ValueError:
            raise InvalidParameter(key)

    filtr = request.args.get('filter', {})
    fields = request.args.get('fields')
    sort = request.args.get('sort')
    if sort:
        sort = SortSchema(many=True).load(sort)

    return db_access.get_include_public_documents(
        ctx, request, filtr, fields, args['limit'], args['skip'], sort
    )


def count(ctx, request):
    """
    (old) Counts documents in the $resource collection.

    ---
    get:
      description: >
        Counts documents in the **$resource** collection.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        filter    | object | | the query to select what subset to count\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error\n
        count     | int | number of $resource

      tags:
        - data
    """
    filtr = request.args.get('filter', {})
    response = db_access.count(ctx, request, filtr)

    return response


@required_args('data')
def add(ctx, request):
    """
    (old) Add one or more entries to $resource.
    ---
    post:
      description: >
        This view adds one or more entries to the **$resource** collection.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        data      | object (array) | &#10004; |the data to be added, can also
        be an array to add multiple entries\n
        action    | string |          | used in the timestamp of a document to
        show what the last action was performed on the document, this string
        will be included in all entries added. (None by default)\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error\n
        data      | array | array of new entry id's.

      tags:
        - data
    """
    # documents should be in a list, if not create a list
    if not isinstance(request.args['data'], list):
        request.args['data'] = [request.args['data']]

    response = db_access.add(ctx, request, request.args['data'])

    return response


@required_args('filter', 'data')
def single_edit(ctx, request):
    """
    (old) Edit a single $resource entry.

    Handle single document edit requests.

    ---
    post:
      description: >
        View to edit a single entry of the **$resource** collection.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        filter    | object | &#10004; | filter to select the entry to be
        edited.\n
        data      | object | &#10004; | the edit that needs to be made.
        '$inc', '$mul', '$rename', '$set', '$unset', '$min', '$max' and
        '$currentDate' are accepted operators.\n


        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error\n
        data      | object | some meta-data about the edit\n

      tags:
        - data
    """
    filtr = request.args['filter']
    data = request.args['data']

    result = db_access.edit(ctx, request, filtr, data)
    return result


@required_args('data')
def save(ctx, request):
    """
    (old) Save documents to the $resource collection.

    ---
    post:
      description: >
        Save documents in the **$resource** collection, using
        replace_one(upsert=True).

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        data      | object (array) | &#10004; | Document to be saved. Can also
        be an array of objects.\n
        action    | string | &#10004; | used in the 'created' or 'modified'
        timestamp of a document to show what the last action was performed
        on the document, this string will be included in all entries added.
        (None by default)\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error\n
        data      | object | some meta-data about the save\n

      tags:
        - data
    """
    documents = request.args['data']

    # documents should be in a list, if not create a list
    if not isinstance(documents, list):
        documents = [documents]

    response = db_access.save(ctx, request, documents)
    return response


@required_args('filter')
def remove(ctx, request):
    """
    (old) Remove a document from $resource.

    ---
    post:
      description: >
        Remove a document from the $resource collection. The document is
        selected by the filter. If the filter matches more than one document
        only one is deleted.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        filter    | object | &#10004; | filter to select the entry to be
        removed.\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | ok or error\n
        data['ok']| int | 1 (number of documents deleted)\n

      tags:
        - data
    """
    response = db_access.remove(ctx, request, request.args['filter'])

    return response
