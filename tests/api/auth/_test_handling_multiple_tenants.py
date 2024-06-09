"""
These tests were salvaged from spynl.mongo when we removed auth handling
from there. Might be easy to get them going again here.
"""
# flake8: noqa


def test_add_documents_for_multiple_tenants():
    """Adding documents for multiple tenants is not allowed."""
    payload = {'data': [{'first_doc': 'first'}, {'second_doc': 'second'}]}
    with pytest.raises(SpynlException) as err:
        db_add(
            'unittest_collection',
            payload,
            ['unittest_tenant1', 'unittest_tenant2'],
            None,
            None,
        )
    assert str(err.value).startswith("The tenant_id is not a <string>")


def test_edit_documents_for_multiple_tenants():
    """Editing documents for multiple tenants is not allowed."""
    filtr = {'some_field': 'some_value'}
    operation = {'$set': {'some_field': 'edited_value'}}
    with pytest.raises(SpynlException) as err:
        db_edit(
            'unittest_collection',
            filtr,
            operation,
            ['unittest_tenant1', 'unittest_tenant2'],
            None,
            None,
        )
    assert str(err.value).startswith("The tenant_id is not a <string>")


def test_save_documents_for_multiple_tenants():
    """Saving documents for multiple tenants is not allowed."""
    documents = [
        {'first_doc': 'first', 'tenant_id': ['unittest_tenant1']},
        {'second_doc': 'second', 'tenant_id': ['unittest_tenant2']},
    ]
    with pytest.raises(SpynlException) as err:
        db_save(
            'unittest_collection',
            documents,
            ['unittest_tenant1', 'unittest_tenant2'],
            None,
            None,
        )
    assert str(err.value).startswith("The tenant_id is not a <string>")


def test_import_documents_for_multiple_tenants():
    """Importing documents for multiple tenants is not allowed."""
    documents = [{'first_doc': 'first'}, {'second_doc': 'second'}]
    with pytest.raises(SpynlException) as err:
        run_import(
            'unittest_collection',
            documents,
            ['unittest_tenant1', 'unittest_tenant2'],
            None,
            None,
        )
    assert str(err.value).startswith("The tenant_id is not a <string>")


def test_getting_documents_for_multiple_tenants(app, db_set_data5, login_out_user2):
    """
    Getting documents for multiple tenants is allowed.
    """
    payload = {
        'filter': {'email': 'user2@email.com'},
        'tenant_ids': ['unittest_tenant1', 'unittest_tenant2', 'unittest_tenant3'],
    }
    resp = post(app, '/users/get', payload)
    assert resp['status'] == 'ok'
    assert resp['data'][0]['email'] == 'user2@email.com'


def test_aggregating_documents_for_multiple_tenants(app, db_set_data5, login_out_user2):
    """
    Aggregate documents for multiple tenants is allowed.

    Dont set tenant and ask doc which is for multiple tenants.
    """
    payload = {
        'filter': [{'$group': {'_id': '$email'}}],
        'tenant_ids': ['unittest_tenant1', 'unittest_tenant2', 'unittest_tenant3'],
    }
    resp = post(app, '/users/agg', payload)
    assert resp['status'] == 'ok'
    assert resp['data']['result'][0]['_id'] == 'user2@email.com'


def test_counting_documents_for_multiple_tenants(app, db_set_data5, login_out_user2):
    """
    Count documents for multiple tenants is allowed.

    Dont set tenant and ask doc which is for multiple tenants.
    """
    payload = {
        'filter': {'email': 'user2@email.com'},
        'tenant_ids': ['unittest_tenant1', 'unittest_tenant2', 'unittest_tenant3'],
    }
    resp = post(app, '/users/count', payload)
    assert resp['status'] == 'ok'
    assert resp['count'] == 1
