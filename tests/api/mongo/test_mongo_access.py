"""Tests regarding accessing mongo database."""
import pytest

from spynl.api.auth.testutils import mkuser


@pytest.fixture(autouse=True)
def set_db_tenants_users(db):
    """Fill database with data for tests to use."""
    db.tenants.insert_one(
        {'_id': 'test_tenant', 'name': 'tenant 1', 'applications': ['pos']}
    )
    mkuser(db, 'user1', 'password', ['test_tenant'], {'test_tenant': ['pos-device']})

    db.tenants.insert_one({'_id': 'master', 'name': 'Master Tenant'})
    mkuser(db, 'master_user', 'password', ['master'], {'master': ['sw-admin']})


@pytest.fixture
def set_db_data(db):
    """Fill with some data the test_collection."""
    tenant_id = ['test_tenant']
    db.test_collection.insert_one({'a': 1, 'b': 2, 'tenant_id': tenant_id})
    db.test_collection.insert_one({'a': 3, 'b': 4, 'tenant_id': tenant_id})
    db.test_collection.insert_one({'a': 5, 'b': 4, 'tenant_id': tenant_id})
    db.test_collection.insert_one({'a': 7, 'b': 6, 'tenant_id': tenant_id})
    db.test_collection.insert_one({'a': 3, 'b': 4, 'tenant_id': 'test_tenant_2'})
    db.test_collection.insert_one({'a': 3, 'b': 4, 'tenant_id': 'test_tenant_3'})


@pytest.fixture
def set_db_2(db):
    """Fill with some data the test_collection."""
    db.test_collection.insert_one({'a': 1, 'b': 2, 'tenant_id': ['test_tenant']})
    db.test_collection.insert_one({'a': 3, 'b': 4, 'tenant_id': ['test_tenant']})
    db.test_collection.insert_one(
        {'a': 5, 'b': {'c': True}, 'tenant_id': ['test_tenant']}
    )


@pytest.fixture
def set_db_3(db):
    """Fill with some data the test_collection."""
    db.test_collection.insert_one(
        {'_id': 1234, 'a': 1, 'b': 2, 'tenant_id': ['test_tenant']}
    )
    db.test_collection.insert_one(
        {'_id': 'abcd', 'a': 3, 'b': 4, 'tenant_id': ['test_tenant']}
    )
    # Public Document
    db.test_collection.insert_one({'_id': 'public', 'abc': 3, 'property': 4})


@pytest.fixture
def set_db_4(db, set_db_2):
    """Use set_db_2 fixture adding one public document."""
    # Public Document
    db.test_collection.insert_one({'_id': 'public', 'abc': 3, 'property': 4})


def test_get_tenants_own_doc(set_db_data, app):
    """Only one doc exists with a=1."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'a': 1}}
    response = app.post_json('/test/get', payload, status=200)
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['a'] == 1
    assert response.json['data'][0]['b'] == 2


def test_get_passing_filter_that_includes_docs_from_other_tenants(set_db_data, app):
    """It should return only docs from logged in tenant."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'b': {'$gt': 3}}}
    response = app.post_json('/test/get', payload, status=200)
    assert len(response.json['data']) == 3


def test_get_with_lte_operator(set_db_data, app):
    """Only 1 doc exists for current tenant with a < 1."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'a': {'$lte': 3}}}
    response = app.post_json('/test/get', payload, status=200)
    assert len(response.json['data']) == 2


def test_get_with_or_operator(set_db_data, app):
    """Only 3 docs exist for current tenant with a == 1 OR b == 4."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'$or': [{'a': 1}, {'b': 4}]}}
    response = app.post_json('/test/get', payload, status=200)
    assert len(response.json['data']) == 3


def test_get_with_and_operator(set_db_data, app):
    """Only 1 doc exists for current tenant with a == 7 AND b == 6."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'$and': [{'a': 7}, {'b': 6}]}}
    response = app.post_json('/test/get', payload, status=200)
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['a'] == 7
    assert response.json['data'][0]['b'] == 6


def test_get_with_and_operator_but_wrong_format(set_db_data, app):
    """Operator $and should be a list of dicts with expected keys/values."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'$and': 'incorrect'}}
    app.post_json('/test/get', payload, status=500)


def test_get_with_or_operator_but_wrong_format(set_db_data, app):
    """Operator $or should be a list of dicts with expected keys/values."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'$or': 'incorrect'}}
    app.post_json('/test/get', payload, status=500)


@pytest.mark.parametrize('payload', ({'filter': {}}, {}))
def test_get_without_filter(set_db_data, app, payload):
    """It should return only the docs for current tenant."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    response = app.post_json('/test/get', payload, status=200)
    assert len(response.json['data']) == 4


def test_get_by_tenant_id(set_db_data, app):
    """It should raise an error instead of return current tenant's docs."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    tenant_query = [
        {'tenant_id': {'$in': ['test_tenant_2']}},
        {'tenant_id': {'$exists': True}},
    ]
    payload = {'filter': {'$and': [{'$or': tenant_query}]}}
    response = app.post_json('/test/get', payload, status=400)
    assert 'Searching by tenant_id is not allowed' in response.json['message']


def test_master_tenant_gets_docs_filtered_by_tenant_id(set_db_data, app, db):
    """Master tenant is allowed to filter by tenant id."""
    app.post_json('/login', {'username': 'master_user', 'password': 'password'})
    response = app.post_json('/tenants/test_tenant_2/test/get')
    docs = list(db.test_collection.find({'tenant_id': 'test_tenant_2'}))
    for doc in docs:
        doc['_id'] = str(doc['_id'])
    assert response.json['data'] and response.json['data'] == docs


def test_master_gets_results_for_requested_tenant_when_accessing_cross_tenant_endpoint(
    app, set_db_data, db
):
    """
    Ensure that master gets docs for the requested tenant(the one in the url path).
    """
    app.post_json(
        '/login', {'username': 'master_user', 'password': 'password'}, status=200
    )
    response = app.post_json('/tenants/test_tenant_2/test/get')
    docs = list(db.test_collection.find({'tenant_id': 'test_tenant_2'}))
    for doc in docs:
        doc['_id'] = str(doc['_id'])
    assert response.json['data'] and response.json['data'] == docs


def test_count_with_simple_tenant(db, set_db_data, app):
    """
    Test counting documents from the database with simple tenant."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    db.test_collection.insert_one({'a': 7, 'b': 4})

    payload = {'filter': {'a': {'$lt': 5}}}
    response = app.post_json('/test/count', payload, status=200)
    assert response.json['count'] == 2

    payload = {'filter': {'b': 4}}
    response = app.post_json('/test/count', payload, status=200)
    assert response.json['count'] == 2


def test_count_with_master_tenant(db, set_db_data, app):
    """
    Test counting documents from the database with master tenant.

    There is one public document which always gets counted, the others
    depend on the tenant which is set for the user.
    """
    app.post_json('/login', {'username': 'master_user', 'password': 'password'})
    db.test_collection.insert_one({'a': 7, 'b': 4})
    payload = {'filter': {'a': {'$lt': 5}}}
    response = app.post_json('/test/count', payload, status=200)
    assert response.json['count'] == 4

    payload = {'filter': {'b': 4}}
    response = app.post_json('/test/count', payload, status=200)
    assert response.json['count'] == 5


def test_remove(db, app):
    """Test removing documents from database."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    # One private document
    db.test_collection.insert_one({'a': 1, 'tenant_id': ['test_tenant']})
    # One public document
    db.test_collection.insert_one({'_id': 'public', 'a': 1})
    assert db.test_collection.count_documents({'a': 1}) == 2

    # Remove the private one
    payload = {'filter': {'a': 1}}
    app.post_json('/test/remove', payload, status=200)
    assert db.test_collection.count_documents({'a': 1}) == 1

    # Test injecting tenant_id
    query = {'a': 1, '$or': [{'tenant_id': {'$exists': True}}]}
    payload = {'filter': query}
    response = app.post_json('/test/remove', payload, status=400)
    assert 'Searching by tenant_id is not allowed' in response.json['message']

    # Test removing public document
    query = {'_id': 'public'}
    payload = {'filter': query}
    app.post_json('/test/remove', payload, status=200)
    assert db.test_collection.count_documents({'_id': 'public'}) == 1


def test_save(db, app):
    """Test saving documents to database."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    db.test_collection.insert_one(
        {'_id': '1234', 'a': 1, 'b': 2, 'tenant_id': ['test_tenant']}
    )
    db.test_collection.insert_one(
        {'_id': 'abcd', 'a': 3, 'b': 4, 'tenant_id': ['test_tenant']}
    )

    payload = {'data': {'_id': '1234', 'a': True, 'b': 2}}
    app.post_json('/test/save', payload, status=200)
    assert db.test_collection.count_documents({'a': 1}) == 0
    assert db.test_collection.count_documents({'a': True}) == 1
    assert db.test_collection.count_documents({'b': 2}) == 1
    assert db.test_collection.count_documents({'a': 3}) == 1
    assert db.test_collection.count_documents({'b': 4}) == 1


def test_changing_tenant_id_through_filter(db, set_db_2, app):
    """Changing the tenant_id is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'a': 5}, 'data': {'$set': {'tenant_id': 'x_tenant'}}}

    response = app.post_json('/test/edit', payload, status=400)
    assert 'not allowed to modify the tenant Id' in response.json['message']
    assert db.test_collection.count_documents({'a': 5}) == 1
    assert (
        db.test_collection.count_documents({'tenant_id': {'$in': ['test_tenant']}}) == 3
    )


def test_deleting_tenant_id_through_the_filter(db, set_db_2, app):
    """Deleting the tenant_id is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'a': 5}, 'data': {'$unset': {'tenant_id': 'test_tenant'}}}
    response = app.post_json('/test/edit', payload, status=400)
    assert 'not allowed to modify the tenant Id' in response.json['message']
    assert db.test_collection.count_documents({'a': 5}) == 1
    assert (
        db.test_collection.count_documents({'tenant_id': {'$in': ['test_tenant']}}) == 3
    )


def test_filtering_tenant_id_passing_random_argument(db, set_db_2, app):
    """Not expected argument should raise error."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    query = {'a': 1, '$or': [{'tenant_id': {'$exists': True}}]}
    payload = {'filter': query, 'data': {'$set': {'a': 2}}}
    response = app.post_json('/test/edit', payload, status=400)
    assert 'Searching by tenant_id is not allowed' in response.json['message']


def test_changing_a_public_document(set_db_3, db, app):
    """Changing public document is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'data': {'_id': 'public', 'abc': True, 'b': 2}}
    # internal server error because of duplicate key error
    app.post_json('/test/save', payload, status=500)
    assert db.test_collection.count_documents({'abc': 3}) == 1
    public = db.test_collection.find_one({'_id': 'public'})
    assert public.get('tenant_id') is None


def test_setting_tenant_id(db, set_db_4, app):
    """Setting the tenant_id is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'a': 5}, 'data': {'$set': {'tenant_id': 'xxx_tenant'}}}
    response = app.post_json('/test', payload, status=400)
    assert 'not allowed to modify the tenant Id' in response.json['message']
    assert db.test_collection.count_documents({'a': 5}) == 1
    assert (
        db.test_collection.count_documents({'tenant_id': {'$in': ['test_tenant']}}) == 3
    )


def test_removing_tenant_id(db, set_db_4, app):
    """Removing the tenant_id is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    payload = {'filter': {'a': 5}, 'data': {'$unset': {'tenant_id': 'test_tenant'}}}
    response = app.post_json('/test', payload, status=400)
    assert 'not allowed to modify the tenant Id' in response.json['message']
    assert db.test_collection.count_documents({'a': 5}) == 1
    assert (
        db.test_collection.count_documents({'tenant_id': {'$in': ['test_tenant']}}) == 3
    )


def test_searching_by_tenant_id(db, set_db_4, app):
    """Injecting the tenant_id is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    query = {'a': 1, '$or': [{'tenant_id': {'$exists': True}}]}
    payload = {'filter': query, 'data': {'a': 2}}
    response = app.post_json('/test', payload, status=400)
    assert 'Searching by tenant_id is not allowed' in response.json['message']


def test_injecting_tenant_id_into_public_document(db, set_db_4, app):
    """Injecting the tenant_id into public document is not allowed."""
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    query = {'_id': 'public'}
    payload = {'filter': query, 'data': {'tenant_id': ['mine']}}
    response = app.post_json('/test', payload, status=400)
    assert response.json['type'] == 'IllegalAction'


def test_overwrite_other_tenants_data(db, set_db_4, app):
    app.post_json('/login', {'username': 'user1', 'password': 'password'}, status=200)
    db.test_collection.insert_one({'_id': '1', 'tenant_id': ['another_tenant']})
    payload = {'data': {'_id': '1', 'bla': 'bla'}}
    # status 500 because of duplicate key error
    app.post_json('/test/save', payload, status=500)
