"""
This module defines an intentionally leaky abstraction over the Pymongo
database and collecion objects.

The reason for this is that we want to provide a little bit of extra logic
to basic operations related to security, (non-)indexed queries, limits and
atomic updates.

Both the Database and CollectionWrapper allow direct access to pymongo
attributes by prefixing attribute lookup with `pymongo_`. So for example

db.users.pymongo_find_one would use the original find_one. Whereas
db.users.find_one would use our version.
"""

import datetime
import re

import pkg_resources
from bson.codec_options import CodecOptions
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from pymongo.read_preferences import ReadPreference

__all__ = [
    'CollectionWrapper',
    'Database',
    'DocumentNotFound',
    'ForbiddenOperators',
    'UnindexedQuery',
]


UPDATE_OPERATORS = {
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
FORBIDDEN_OPERATORS = {'$where'}
MAX_LIMIT = 1000
MAX_AGG_LIMIT = 5000
MAX_TIME_MS = 60 * 2 * 1000  # 2 minutes
VERSION = pkg_resources.get_distribution('spynl.data').version
# The max number of items is CAP+1, because it retains max cap and then adds the newest.
MODIFIED_HISTORY_CAP = 200


class DocumentNotFound(PyMongoError):
    """Raised when a document cannot be found by the get method."""


class UnindexedQuery(PyMongoError):
    """Raised when attempting to do an unindexed query."""


class ForbiddenOperators(PyMongoError):
    """Raised when a query contains forbidden operators."""


class ForbiddenOperation(PyMongoError):
    """Raised when a query contains forbidden operators."""


def default_database_callback(d, *args, **kwargs):
    return d


def default_timestamp_callback(
    data, collection, update_filter=None, user=None, action=None, versions=None
):
    """Format a datetime stamp for use with create and update methods."""
    timestamp = {
        'date': datetime.datetime.utcnow(),
        'user': user,
        'action': action,
        'versions': versions,
    }

    # new document
    if not update_filter:
        data.update(
            {
                'created': timestamp,
                'modified': timestamp,
                'modified_history': [timestamp],
            }
        )
    # update or upsert
    else:
        original = collection.pymongo_find_one(update_filter) or {}

        data.update(
            {
                'modified': timestamp,
                'created': original.get('created', timestamp),
                'modified_history': [
                    *original.get('modified_history', [])[-MODIFIED_HISTORY_CAP:],
                    timestamp,
                ],
            }
        )
    return data


class Database:
    """A thin wrapper around a pymongo database object.

    Attributes prefixed with `pymongo_` are proxied to the pymongo database
    object.
    """

    def __init__(
        self,
        host=None,
        database_name=None,
        ssl=True,
        auth_mechanism=None,
        *args,
        **kwargs
    ):
        self._max_limit = kwargs.pop('max_limit', MAX_LIMIT)
        self._max_agg_limit = kwargs.pop('max_agg_limit', MAX_AGG_LIMIT)
        self._max_time_ms = kwargs.pop('max_time_ms', MAX_TIME_MS)
        self.reset_callbacks()

        client_kwargs = {'ssl': ssl}
        if ssl:
            client_kwargs.update(
                tlsAllowInvalidHostnames=True, tlsAllowInvalidCertificates=True
            )
        if auth_mechanism:
            client_kwargs['authMechanism'] = auth_mechanism

        self._client = MongoClient(host, **client_kwargs)

        kwargs.setdefault(
            'codec_options', CodecOptions(uuid_representation=4, tz_aware=True)
        )

        self._db = self._client.get_database(database_name, *args, **kwargs)

    def reset_callbacks(self):
        self.find_callback = default_database_callback
        self.save_callback = default_database_callback
        self.aggregate_callback = default_database_callback
        self.timestamp_callback = default_timestamp_callback

    def __getattr__(self, name):
        """Fallback attribute access.

        If name is prefixed with `pymongo_` then we will call getattr on the
        pymongo database object.

        Otherwise we attempt to retrieve a collection and wrap it in
        CollectionWrapper.

        If what is returned in not a collection we raise AttributeError.
        """
        if name.lower().startswith('pymongo_'):
            return getattr(self._db, name.replace('pymongo_', ''))

        attr = getattr(self._db, name)
        if isinstance(attr, Collection):
            return CollectionWrapper(attr, self)

        raise AttributeError(
            "'{}' has no attribute '{}'".format(self.__class__.__name__, name)
        )

    def __getitem__(self, value):
        """Item access to retrieve a collection.

        Value may be a string or an object that specifies the collection and
        whether it should be treated as a large collection.
        """
        if isinstance(value, str):
            return self.pymongo_db.get_collection(value)

        try:
            collection_name = value.collection
        except AttributeError:
            raise ValueError(
                "Non-string subscription values must have a 'collection' attribute "
                "specifying the collection to retrieve."
            )
        large = getattr(value, 'is_large_collection', False)
        collection = self.pymongo_db.get_collection(collection_name)
        return CollectionWrapper(collection, self, large)

    @property
    def pymongo_db(self):
        """Return the pymongo database object. For direct operations."""
        return self._db

    @property
    def pymongo_client(self):
        """Return the pymongo client object. For direct operations."""
        return self._client

    def __repr__(self):
        return '<wrapped %s' % self.pymongo_db


class CollectionWrapper:
    """A thin wrapper around a pymongo collection.

    Implements a number of methods with our defaults. Attributes prefixed with
    `pymongo_` are proxied to the pymongo collection object.
    """

    def __init__(self, collection, db, large=False):
        self._collection = collection
        self._db = db
        self._large = large

    def __getattr__(self, name):
        """Fallback attribute access.

        If name prefixed with pymongo_ then we will get the attribute from
        the pymongo database object.

        Otherwise we raise AttributeError
        """
        if name.lower().startswith('pymongo_'):
            return getattr(self._collection, name.replace('pymongo_', ''))

        raise AttributeError(
            "'{}' has no attribute '{}'".format(self.__class__.__name__, name)
        )

    @property
    def pymongo_collection(self):
        return self._collection

    @property
    def _secondary(self):
        """Return a collection that will prefer the secondary in querying."""
        return self._collection.with_options(
            read_preference=ReadPreference.SECONDARY_PREFERRED
        )

    @staticmethod
    def _get_filter_keys(filter):
        keys = []
        if isinstance(filter, list):
            for q in filter:
                keys.extend(CollectionWrapper._get_filter_keys(q))

        elif isinstance(filter, dict):
            for key, value in filter.items():
                if key.startswith('$'):
                    keys.extend(CollectionWrapper._get_filter_keys(value))
                else:
                    # append the key
                    keys.append(key)
                    # if it was dotnotation append the root key.
                    if '.' in key:
                        keys.append(key.split('.')[0])
        return keys

    def _validate_filter(
        self, filter, sort=None, validate_operators=True, validate_indexes=True
    ):
        if filter is None:
            filter = {}
        if validate_operators:
            # escape the leading $
            forbidden_operators = {
                '\\' + op for op in FORBIDDEN_OPERATORS if op.startswith('$')
            }

            # match keys for forbidden operators
            pattern = re.compile(r'({}).*:'.format(('|').join(forbidden_operators)))
            if filter and pattern.findall(str(filter)):
                raise ForbiddenOperators

        # if this is registered as a large collection
        if validate_indexes and self._large:
            filter_keys = CollectionWrapper._get_filter_keys(filter)
            indexes = self._secondary.index_information().values()
            indexed_keys = [idx['key'][0][0] for idx in indexes]
            #                          │  └─ The field name.
            #                          └─ The first of the fields in the index.
            if (
                indexed_keys
                and filter
                and not set(filter_keys).intersection(indexed_keys)
            ):
                raise UnindexedQuery

            # We care about the first sort
            if sort and sort[0][0] != '_id' and sort[0][0] not in indexed_keys:
                #            │  └─ The the fieldname on which to sort.
                #            └─ The first sort.
                raise UnindexedQuery

    def get(self, id):
        document = self.pymongo_find_one({'_id': id})
        if not document:
            raise DocumentNotFound
        return document

    def find_one(self, filter=None, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        kwargs.update(max_time_ms=self._db._max_time_ms)

        self._validate_filter(filter)
        filter = self._db.find_callback(filter, self)

        return self.pymongo_find_one(filter, *args, **kwargs)

    def find(self, filter=None, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        kwargs.update(max_time_ms=self._db._max_time_ms)

        sort = kwargs.get('sort')
        self._validate_filter(filter, sort)
        filter = self._db.find_callback(filter, self)

        limit = kwargs.get('limit')
        if not limit or limit > self._db._max_limit:
            kwargs['limit'] = self._db._max_limit

        return self.pymongo_find(filter, *args, **kwargs)

    def count_documents(self, filter=None, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        kwargs.update(maxTimeMS=self._db._max_time_ms)
        self._validate_filter(filter)
        filter = self._db.find_callback(filter, self)
        filter = filter or {}
        return self._secondary.count_documents(filter, *args, **kwargs)

    def count(self, filter=None, *args, **kwargs):
        if not filter:
            filter = {}
        return self.count_documents(filter, *args, **kwargs)

    def delete_one(self, filter=None, *args, **kwargs):
        self._validate_filter(filter, validate_indexes=False)
        filter = self._db.find_callback(filter, self)
        return self.pymongo_delete_one(filter, *args, **kwargs)

    def delete_many(self, filter, *args, **kwargs):
        self._validate_filter(filter, validate_indexes=False)
        filter = self._db.find_callback(filter, self)
        return self.pymongo_delete_many(filter, *args, **kwargs)

    def insert_one(self, data, *args, user=None, action=None, **kwargs):
        data = self._db.save_callback(data, self)
        data = self._db.timestamp_callback(data, self, user=user, action=action)
        return self.pymongo_insert_one(data, *args, **kwargs)

    def insert_many(self, data, *args, user=None, action=None, **kwargs):
        for r in data:
            r = self._db.save_callback(r, self)
            r = self._db.timestamp_callback(r, self, user=user, action=action)
        return self.pymongo_insert_many(data, *args, **kwargs)

    def update_one(self, filter, update, *args, user=None, action=None, **kwargs):
        self._validate_filter(filter, validate_indexes=False)
        filter = self._db.find_callback(filter, self)
        if not UPDATE_OPERATORS & update.keys():
            raise ForbiddenOperation(
                'Must use one or more of the following '
                'operators for update: %s.' % ', '.join(UPDATE_OPERATORS)
            )
        update['$set'] = self._db.timestamp_callback(
            update.get('$set', {}), self, update_filter=filter, user=user, action=action
        )

        return self.pymongo_update_one(filter, update, *args, **kwargs)

    def update_many(self, filter, update, *args, user=None, action=None, **kwargs):
        self._validate_filter(filter, validate_indexes=False)
        filter = self._db.find_callback(filter, self)
        if not UPDATE_OPERATORS & update.keys():
            raise ForbiddenOperation(
                'Must use one or more of the following '
                'operators for update: %s.' % ', '.join(UPDATE_OPERATORS)
            )
        update['$set'] = self._db.timestamp_callback(
            update.get('$set', {}), self, update_filter=filter, user=user, action=action
        )

        return self.pymongo_update_many(filter, update, *args, **kwargs)

    def aggregate(self, pipeline, *args, **kwargs):
        if not kwargs:
            kwargs = {}
        kwargs.update(maxTimeMS=self._db._max_time_ms)

        pipeline = self._db.aggregate_callback(pipeline, self)

        max_limit = self._db._max_agg_limit
        limit_set = False
        for stage in pipeline:
            if '$limit' in stage:
                limit_set = True
                if stage['$limit'] > max_limit:
                    stage['$limit'] = max_limit

        if not limit_set:
            pipeline.append({'$limit': max_limit})
        return self._secondary.aggregate(pipeline, *args, **kwargs)

    def upsert_one(
        self,
        filter,
        replacement,
        user=None,
        immutable_fields=None,
        action=None,
        **kwargs
    ):
        """
        Performs an upsert

        It keeps the created timestamp and any fields provided in
        immutable_fields. If an immutable_field is not present in the original,
        you can use upsert_one to add it.
        """

        projection = {'_id': 0, 'created': 1}
        if immutable_fields:
            projection.update({key: 1 for key in immutable_fields})

        # use the find_callback, so you cannot overwrite another tenant's data.
        self._validate_filter(filter)
        filter = self._db.find_callback(filter, self)
        original = (
            self.pymongo_find_one(
                filter, projection=projection, max_time_ms=self._db._max_time_ms
            )
            or {}
        )

        replacement.update(original)
        replacement = self._db.save_callback(replacement, self)

        replacement = self._db.timestamp_callback(
            replacement, self, update_filter=filter, user=user, action=action
        )
        return self.pymongo_replace_one(filter, replacement, upsert=True, **kwargs)
