"""Test utils for spynl.auth functionality."""

import json

from pyramid.authorization import DENY_ALL, Allow, Authenticated
from pyramid.testing import DummyRequest as DummyRequest_

from spynl.main.routing import Resource

from spynl.api.auth import B2BResource
from spynl.api.auth import token_authentication as tokens
from spynl.api.auth.authentication import scramble_password
from spynl.api.mongo import MongoResource


class DummyRequest(DummyRequest_):
    """This defines some extra default values."""

    authenticated_userid = 'test_user_id'
    token_payload = None


def make_auth_header(
    db, user_id, tenant_id, user=None, payload=None, realm='Bearer', swapi=False
):
    # check it with sending bytes and strings.
    user = user or {'_id': user_id}
    token = tokens.generate(db, user_id, tenant_id, payload=payload)['token'].hex
    if not swapi:
        value = '%s %s' % (realm, token)
        return {'Authorization': value}
    else:
        return {'X-Swapi-Authorization': token}


def mkuser(
    db,
    name,
    pwd,
    tenant_ids,
    tenant_roles=None,
    def_app=None,
    settings=None,
    owns=None,
    user_type='standard',
    language=None,
    custom_id=None,
):
    """insert a user"""
    if def_app is None:
        def_app = dict.fromkeys(tenant_ids, {})
    user = {
        'email': '%s@blah.com' % name,
        'username': name,
        'password_hash': scramble_password(pwd, pwd, '2'),
        'password_salt': pwd,
        'hash_type': '2',
        'active': True,
        'tenant_id': tenant_ids,
        'default_application': def_app,
        'type': user_type,
        'tz': 'Europe/Amsterdam',
        'fullname': 'Mister %s' % name,
        'language': language,
    }
    if custom_id is not None:
        user['_id'] = custom_id
    user['roles'] = {}
    if tenant_roles is not None:
        for tenant, roles in tenant_roles.items():
            user['roles'][tenant] = {'tenant': roles}
    if settings is not None:
        user['settings'] = settings

    user_id = db.users.insert_one(user).inserted_id
    if owns is not None:
        for tenant_id in owns:
            db.tenants.update_one({'_id': tenant_id}, {'$push': {'owners': user_id}})


def login(
    application,
    username,
    password,
    tenant_id=None,
    remember_me=False,
    return_headers=False,
    expect_errors=False,
):
    """
    Login to Pyramid application and return the parsed response and
    headers, if wanted.

    If tenant_id was given then set tenant for the current user.
    """
    login_response = application.post(
        '/login',
        json.dumps(dict(username=username, password=password, remember_me=remember_me)),
        expect_errors=expect_errors,
    )
    login_response_text = json.loads(login_response.text)
    if expect_errors:
        return login_response_text
    assert login_response_text['status'] == 'ok'
    if tenant_id:
        set_tenant_response = application.get(
            '/set-tenant?id={}&sid={}'.format(tenant_id, login_response_text['sid'])
        ).text
        assert json.loads(set_tenant_response)["status"] == "ok"
    if return_headers:
        return login_response_text, login_response.headers
    else:
        return login_response_text


class PublicResource(Resource):

    """Represents data all authenticated users can see"""

    paths = ['public']

    __acl__ = [(Allow, Authenticated, 'read'), DENY_ALL]


class POSResource(MongoResource):

    """Represents POS resources"""

    collection = 'dummy_pos'
    paths = ['test-pos']

    __acl__ = [
        (Allow, 'role:pos-device', ('read', 'add', 'edit')),
        # Role that is not in ROLES:
        (Allow, 'role:pos-unknown', ('read', 'add', 'edit')),
    ]


class DashboardResource(MongoResource):

    """Represents Dashboard resources"""

    collection = 'dummy_dashboard'
    paths = ['test-dashboard']

    __acl__ = [
        (Allow, 'role:dashboard-user', ('read', 'add', 'edit')),
        (Allow, 'role:sw-servicedesk', ('read', 'add', 'edit')),
    ]


class ReportingResource(MongoResource):

    """Represents Reporting resources"""

    collection = 'dummy_reporting'
    paths = ['test-reporting']

    __acl__ = [(Allow, 'role:sw-servicedesk', 'read')]


class SharedResource(B2BResource):
    """a resource that can be accessed by a different tenant"""

    paths = ['test-shared']

    __acl__ = [(Allow, 'role:dashboard-user', 'read')]
