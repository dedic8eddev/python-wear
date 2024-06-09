import os
import random
import string
import uuid

import pymongo
import pytest
from pymongo.read_preferences import ReadPreference

from spynl_dbaccess import (
    CollectionWrapper,
    Database,
    ForbiddenOperators,
    UnindexedQuery,
)
from spynl_dbaccess.database import default_database_callback

MONGO_URL = os.environ.get(
    'MONGODB_URL', 'mongodb://mongo-user:password@localhost:27020'
)
RAISE = object()
USER = {'username': 'kareem', 'email': 'kareem@softwear.nl'}


class UserResource:
    collection = 'users'
    is_large_collection = True


@pytest.fixture()
def user_id(database):
    return database.users.pymongo_insert_one(USER).inserted_id


db_attributes = [
    ('pymongo_db', lambda x: isinstance(x, pymongo.database.Database)),
    ('pymongo_db', lambda x: x.codec_options.tz_aware),
    ('users', lambda x: isinstance(x, CollectionWrapper)),
    ('pymongo_users', lambda x: isinstance(x, pymongo.collection.Collection)),
    ('pymongo_add_user', lambda x: callable(x)),
]


@pytest.mark.parametrize('name,test', db_attributes)
def test_attribute_access_on_db(name, test, database):
    attr = getattr(database, name)
    assert test(attr)


collection_attributes = [
    ('with_options', RAISE),
    ('pymongo_find_one', lambda x: callable(x)),
    ('_secondary', lambda x: isinstance(x, pymongo.collection.Collection)),
    ('_secondary', lambda x: x.read_preference is ReadPreference.SECONDARY_PREFERRED),
    ('add_user', RAISE),
]


@pytest.mark.parametrize('name,test', collection_attributes)
def test_attribute_access_on_collection(name, test, database):
    collection = CollectionWrapper(database.pymongo_db.users, database)
    if test is RAISE:
        with pytest.raises(AttributeError):
            getattr(collection, name)
    else:
        attr = getattr(collection, name)
        assert test(attr)


def test_ssl():
    db_name = uuid.uuid4().hex
    Database(MONGO_URL, db_name, ssl=True)


@pytest.mark.xfail(
    reason='Url in the pipeline has no username. Should pass locally', strict=False
)
def test_auth_mechanism():
    db_name = uuid.uuid4().hex
    Database(MONGO_URL, db_name, ssl=False, auth_mechanism='SCRAM-SHA-1')


def test_rejected_for_index(database):
    ctx = UserResource()
    database.users.pymongo_create_index('username')
    with pytest.raises(UnindexedQuery):
        database[ctx]._validate_filter({'email': 'kareem@gmail.com'})


def test_not_rejected_for_index(database):
    ctx = UserResource()
    database.users.pymongo_create_index('username')
    try:
        database[ctx]._validate_filter({'username': 'kareem'})
    except UnindexedQuery:
        pytest.fail('Should not have raised %s' % UnindexedQuery)


def test_rejected_for_forbidden_parameters(database):
    with pytest.raises(ForbiddenOperators):
        database.users._validate_filter({'$where': 'function () { return 1 }'})


def test_get(database, user_id):
    user = database.users.get(user_id)
    assert all(item in user.items() for item in USER.items())


def test_get_limit(database, database_with_limits):
    database.users.insert_many([{} for _ in range(20)])
    database_with_limits.users.insert_many([{} for _ in range(20)])

    allusers = database.users.find()
    user = database_with_limits.users.find()
    assert len(list(user)) == 10 and len(list(allusers)) == 20


def test_agg_limit(database, database_with_limits):
    database.users.insert_many([{'number': i} for i in range(20)])
    database_with_limits.users.insert_many([{'number': i} for i in range(20)])

    allresults = database.users.aggregate([{'$group': {'_id': '$_id'}}])
    result = database_with_limits.users.aggregate([{'$group': {'_id': '$_id'}}])
    assert len(list(result)) == 10 and len(list(allresults)) == 20


def test_count(database, user_id):
    assert database.users.count({'_id': user_id}) == 1


def test_count_documents(database, user_id):
    assert database.users.count_documents({'_id': user_id}) == 1


def test_find(database, user_id):
    result = list(database.users.find({'username': 'kareem'}))
    assert len(result) == 1 and all(item in result[0].items() for item in USER.items())


def test_find_with_skip(database, user_id):
    result = database.users.find({}, skip=1)
    with pytest.raises(StopIteration):
        result.next()


def test_find_with_fields(database, user_id):
    result = list(database.users.find({}, ['_id']))
    result == [{'_id': user_id}]


def test_when_resource_doesnt_have_collection_attr_raises_error(database, monkeypatch):
    monkeypatch.delattr(UserResource, 'collection')
    with pytest.raises(ValueError):
        database[UserResource()]


def test_resource_without__is_large_collection_attr__defaults_to_false(
    database, monkeypatch
):
    monkeypatch.delattr(UserResource, 'is_large_collection')
    collection = database[UserResource()]
    assert collection._large is False


def test_upsert_one(database):
    database.users.upsert_one({'username': 'kareem'}, {'username': 'mohammed'})
    users = list(database.users.find())
    assert len(users) == 1 and users[0]['username'] == 'mohammed'


def test_upsert_one_keeps_created_timestamp(database):
    database.users.upsert_one({'username': 'kareem'}, {'username': 'mohammed'})
    mohammed_created = database.users.find_one({'username': 'mohammed'})['created']

    database.users.upsert_one({'username': 'mohammed'}, {'username': 'kareem'})
    kareem_created = database.users.find_one({'username': 'kareem'})['created']
    assert mohammed_created == kareem_created


def test_upsert_one_keeps_immutable_fields(database):
    database.users.upsert_one({'username': 'kareem'}, {'username': 'mohammed'})
    database.users.upsert_one(
        {'username': 'mohammed'}, {'username': 'kareem'}, immutable_fields=['username']
    )
    assert (
        database.users.count({'username': 'kareem'}) == 0
        and database.users.count({'username': 'mohammed'}) == 1
    )


def test_timestamps_insert_one(database):
    result = database.col.insert_one({})
    doc = database.col.find_one({'_id': result.inserted_id})
    try:
        assert doc['created'] == doc['modified']
    except KeyError:
        pytest.fail('new documents should contain both created and modified')


def test_timestamps_upsert_one(database):
    result = database.col.upsert_one({}, {})
    doc = database.col.find_one({'_id': result.upserted_id})
    try:
        assert doc['created'] == doc['modified']
    except KeyError:
        pytest.fail('new documents should contain both created and modified')


def test_timestamps_insert_many(database):
    result = database.col.insert_many([{}])
    doc = database.col.find_one({'_id': result.inserted_ids[0]})
    try:
        assert doc['created'] == doc['modified']
    except KeyError:
        pytest.fail('new documents should contain both created and modified')


def test_timestamps_modified_history(database, monkeypatch):
    monkeypatch.setattr('spynl_dbaccess.database.MODIFIED_HISTORY_CAP', 1)
    result = database.col.insert_one({})
    doc_id = result.inserted_id
    doc = database.col.find_one({'_id': doc_id})
    try:
        assert doc['created'] == doc['modified'] == doc['modified_history'][0]
    except KeyError:
        pytest.fail('new documents should contain both created, modified and history')
    assert len(doc['modified_history']) == 1
    # edit once
    database.col.upsert_one({'_id': doc_id}, {**doc, 'test': 'test'})
    doc = database.col.find_one({'_id': doc_id})
    assert doc['created'] == doc['modified_history'][0]
    assert doc['modified'] == doc['modified_history'][1]
    assert len(doc['modified_history']) == 2
    # edit twice (only 1 is retained when copying over before adding one, max=2)
    database.col.upsert_one({'_id': doc_id}, {**doc, 'test': 'test2'})
    doc = database.col.find_one({'_id': doc_id})
    assert doc['created'] != doc['modified_history'][0]
    assert doc['modified'] == doc['modified_history'][1]
    assert len(doc['modified_history']) == 2


@pytest.mark.xfail(reason='mongo is sometimes too fast.', strict=False)
def test_get_max_time_ms(database_with_limits):
    database_with_limits.docs.insert_many(
        [
            {
                random.choice(string.ascii_letters + string.digits): {
                    random.choice(string.ascii_letters + string.digits): random.choice(
                        string.printable
                    )
                }
            }
            for _ in range(100000)
        ]
    )
    q = {
        '$or': [
            {'a.b': {'$regex': 'a'}},
            {'c.d': {'$regex': 'a'}},
            {'e.f': {'$regex': 'a'}},
            {'g.h': {'$regex': 'a'}},
            {'i.j': {'$regex': 'a'}},
        ]
    }
    with pytest.raises(pymongo.errors.ExecutionTimeout):
        next(database_with_limits.docs.find(q))

    with pytest.raises(pymongo.errors.ExecutionTimeout):
        database_with_limits.docs.find_one(q)

    with pytest.raises(pymongo.errors.ExecutionTimeout):
        database_with_limits.docs.count_documents(q)

    with pytest.raises(pymongo.errors.ExecutionTimeout):
        database_with_limits.docs.aggregate([{'$match': q}])


def test_reset_callbacks(database):
    for c in ['find_callback', 'save_callback', 'aggregate_callback']:
        assert getattr(database, c) == default_database_callback
        setattr(database, c, lambda: None)

    database.reset_callbacks()
    for c in ['find_callback', 'save_callback', 'aggregate_callback']:
        assert getattr(database, c) == default_database_callback
