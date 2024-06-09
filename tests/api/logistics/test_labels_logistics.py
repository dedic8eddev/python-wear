""" tests for labels endpoints """
import pytest

from spynl.api.auth.testutils import mkuser


@pytest.fixture(autouse=True)
def set_db(db, app):
    """fill the db"""
    db.tenants.insert_one({'_id': 'a_tenant', 'name': 'A tenant'})
    mkuser(
        db,
        'admin_user',
        'blah',
        ['a_tenant'],
        tenant_roles={'a_tenant': ['account-admin']},
    )

    app.post_json('/login', {'username': 'admin_user', 'password': 'blah'})
    yield
    app.get('/logout')
