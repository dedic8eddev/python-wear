""" Test documentation endpoints """

import pytest

from spynl.api.auth.testutils import mkuser


@pytest.fixture()
def set_db(db):
    """add tenants and users to the db"""
    db.tenants.insert_one(
        {
            '_id': 'tenantid',
            'name': 'A Tenant',
            'applications': ['account', 'dashboard', 'pos'],
        }
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    mkuser(db, 'normal_user', 'blah', ['tenantid'])
    mkuser(db, 'master_user', 'blah', ['master'], tenant_roles={'master': ['sw-admin']})


def test_do_not_show_internal_apps_normal_user(app, set_db):
    """/about/appliations should not show internal apps to normal users"""
    app.post_json('/login', {'username': 'normal_user', 'password': 'blah'})
    response = app.post_json('/about/applications', {'json': True})
    for app in response.json['applications']:
        assert not app.get('internal', False)


def test_show_internal_apps_master_user(app, set_db):
    """/about/appliations should show internal apps to master users"""
    app.post_json('/login', {'username': 'master_user', 'password': 'blah'})
    response = app.post_json('/about/applications', {'json': True})
    count = 0
    for app in response.json['applications']:
        if app.get('internal', False):
            count += 1
    assert count == 1


def test_app_application_key(app, set_db):
    """/about/appliations with json response should add application as key."""
    app.post_json('/login', {'username': 'normal_user', 'password': 'blah'})
    response = app.post_json('/about/applications', {'json': True})
    assert all(('application' in a for a in response.json['applications']))
