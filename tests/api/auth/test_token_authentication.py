import uuid

import bson
import pytest
from botocore.exceptions import BotoCoreError
from pyramid.authorization import Allow

from spynl.main.routing import Resource

from spynl.api.auth import token_authentication as tokens
from spynl.api.auth.plugger import includeme
from spynl.api.auth.testutils import make_auth_header, mkuser
from spynl.api.hr.exceptions import TokenError

USERID = bson.ObjectId()
INACTIVE_USER = bson.ObjectId()
AWS_TOKEN_ID = '123'


def patched_includeme(config):
    class TestResource(Resource):
        """Represents POS resources"""

        collection = 'dummy_pos'
        paths = ['test']

        __acl__ = [(Allow, 'role:pos-device', ('read',))]

    includeme(config)
    config.add_endpoint(lambda _: {}, '/', context=TestResource, permission='read')


@pytest.fixture()
def data(db):
    db.tenants.insert_one({'_id': '1', 'name': 'I. Tenant', 'active': True})
    mkuser(db, 'user', '00000000', ['1'], custom_id=USERID)
    mkuser(db, 'user', '00000000', ['1'], custom_id=INACTIVE_USER)
    db.users.update_one({'_id': INACTIVE_USER}, {'$set': {'active': False}})
    yield


def test_token(app, spynl_data_db, data):
    """Test the token authentication

    Tests the auth on an endpoint that only requires the Authenticated
    principals without any roles.
    """
    headers = make_auth_header(spynl_data_db, USERID, '1')
    app.get('/about/versions', headers=headers, status=200)


def test_bad_token(app, spynl_data_db, data):
    """test auth with a non existing token."""
    headers = {'Authorization': 'Bearer ' + uuid.uuid4().hex}
    app.get('/about/versions', headers=headers, status=403)


def test_token_user_does_not_exist(app, spynl_data_db, data):
    """test auth with a non existing user."""
    headers = make_auth_header(spynl_data_db, bson.ObjectId(), '1')
    app.get('/about/versions', headers=headers, status=400)


def test_token_user_inactive(app, spynl_data_db, data):
    """test auth with an inactive user."""
    headers = make_auth_header(spynl_data_db, INACTIVE_USER, '1')
    app.get('/about/versions', headers=headers, status=403)


def test_swapi_token(app, spynl_data_db, data):
    """Test the swapi token authentication

    Tests the auth on an endpoint that only requires the Authenticated
    principals without any roles.
    """
    headers = make_auth_header(spynl_data_db, USERID, '1', swapi=True)
    app.get('/about/versions', headers=headers, status=200)


def test_bad_swapi_token(app, spynl_data_db, data):
    """test auth with a non existing token."""
    headers = {'X-Swapi-Authorization': uuid.uuid4().hex}
    app.get('/about/versions', headers=headers, status=403)


def test_bad_token_invalid_uuid(app, spynl_data_db, data):
    headers = {'Authorization': 'Bearer ' + 'sdfdssdf'}
    app.get('/about/versions', headers=headers, status=403)


def test_token_bad_realm(app, spynl_data_db, data):
    """Test a realm we don't support."""
    headers = make_auth_header(spynl_data_db, USERID, '1', realm='Basic')
    app.get('/about/versions', headers=headers, status=403)


def test_token_bad_tenant_id(app, spynl_data_db, data):
    """Test a non existent tenant."""
    headers = make_auth_header(spynl_data_db, USERID, '2')
    app.get('/test-pos', headers=headers, status=403)


def test_token_tenant_inactive(app, spynl_data_db, data):
    """test auth with an inactive tenant."""
    spynl_data_db.tenants.update_one({'_id': '1'}, {'$set': {'active': False}})
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    app.get('/test-pos', headers=headers, status=403)


def test_roles(app, spynl_data_db, data):
    """Test a access with proper role."""
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    app.get('/test-pos', headers=headers, status=200)


def test_bad_roles(app, spynl_data_db, data):
    """Test a bad role."""
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-dice']}
    )
    app.get('/test-pos', headers=headers, status=403)


def test_no_roles_2(app, spynl_data_db, data):
    """Test no roles."""
    headers = make_auth_header(spynl_data_db, USERID, '1')
    app.get('/test-pos', headers=headers, status=403)


def test_revoke_token(spynl_data_db, data):
    """Test we insert revoked tokens."""
    token = tokens.generate(spynl_data_db, USERID, '1')['token'].hex
    result = tokens.revoke(spynl_data_db, token)
    assert (
        spynl_data_db.tokens.count_documents({'_id': result['_id'], 'revoked': True})
        == 1
    )


def test_revoke_token_multiple(spynl_data_db, data):
    """Test we find only revoked."""
    token = tokens.generate(spynl_data_db, USERID, '1')['token'].hex
    token2 = tokens.generate(spynl_data_db, USERID, '1')['token'].hex
    tokens.generate(spynl_data_db, USERID, '1')['token'].hex

    tokens.revoke(spynl_data_db, token)
    tokens.revoke(spynl_data_db, token2)

    assert spynl_data_db.tokens.count_documents({'revoked': True}) == 2


def test_token_revoked_no_access(app, spynl_data_db, data):
    """Test revoked tokens are denied."""
    headers = make_auth_header(
        spynl_data_db, USERID, '1', payload={'roles': ['pos-device']}
    )
    tokens.revoke(spynl_data_db, headers['Authorization'][7:])
    app.get('/about/versions', headers=headers, status=403)


def fake_client(success):
    """Return a client which mocked return or raises for boto3."""

    class Client:
        def __init__(self, name):
            pass

        def import_api_keys(self, *args, **kwargs):
            if success:
                return {'ids': [AWS_TOKEN_ID]}
            else:
                raise BotoCoreError

        def update_api_key(self, *args, **kwargs):
            return {'enabled': not success}

    return Client


def test_cannot_import(spynl_data_db, monkeypatch):
    monkeypatch.setattr('boto3.client', fake_client(False))
    with pytest.raises(TokenError):
        tokens.generate(spynl_data_db, '1', '1', usage_plan='1')


def test_can_import(spynl_data_db, monkeypatch):
    monkeypatch.setattr('boto3.client', fake_client(True))
    token = tokens.generate(spynl_data_db, '1', '1', usage_plan='1')
    assert token['aws_id'] == AWS_TOKEN_ID


def test_cannot_revoke(spynl_data_db, monkeypatch):
    monkeypatch.setattr('boto3.client', fake_client(True))
    token = tokens.generate(spynl_data_db, '1', '1', usage_plan='1')
    monkeypatch.setattr('boto3.client', fake_client(False))
    with pytest.raises(TokenError):
        tokens.revoke(spynl_data_db, token['_id'])
