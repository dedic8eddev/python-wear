import uuid

import pytest
import requests
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

USERID = ObjectId()
TENANT_ID = '1'
USERNAME = 'user'
PASSWORD = '0' * 10


@pytest.fixture(autouse=True)
def setup_db(db):
    db.tenants.insert_many(
        [
            {'_id': TENANT_ID, 'active': True, 'settings': {}, 'owners': [USERID]},
            {'_id': '4', 'active': True, 'settings': {}, 'owners': ['4']},
            {'_id': '5', 'active': False, 'settings': {}, 'owners': ['5']},
            {'_id': '6', 'active': True, 'settings': {}},
            {'_id': '7', 'active': True, 'settings': {}, 'owners': []},
            {'_id': 'master', 'active': True, 'settings': {}},
        ]
    )

    mkuser(db, 'user', PASSWORD, [TENANT_ID], custom_id=USERID)
    mkuser(db, 'user2', PASSWORD, ['master'], tenant_roles={'master': 'sw-admin'})
    mkuser(db, 'user3', PASSWORD, ['master'], tenant_roles={'master': 'sw-servicedesk'})
    mkuser(db, 'user4', PASSWORD, ['4'], custom_id='4')
    mkuser(db, 'user5', PASSWORD, ['5'], custom_id='5')


class Response(requests.Response):
    def __init__(self, *args, **kwargs):
        self.fail = kwargs.pop('fail', False)
        super().__init__(*args, **kwargs)

    def raise_for_status(self, *args, **kwargs):
        if self.fail:
            raise requests.exceptions.HTTPError


@pytest.fixture(autouse=True)
def patch_foxpro(monkeypatch):
    monkeypatch.setattr(
        'spynl.api.auth.token_authentication.requests.get', lambda _: Response()
    )


@pytest.fixture()
def patch_foxpro_fail(monkeypatch):
    monkeypatch.setattr(
        'spynl.api.auth.token_authentication.requests.get',
        lambda _: Response(fail=True),
    )


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_request_token(app, login):
    """Test requesting tokens"""
    resp = app.get('/tokens/request', status=200)
    try:
        uuid.UUID(resp.json['data']['token'])
    except Exception:
        pytest.fail('token request failed')


@pytest.mark.parametrize(
    'login', [('user2', PASSWORD), ('user3', PASSWORD)], indirect=True
)
def test_request_token_master(app, login, spynl_data_db):
    """Test requesting tokens"""
    resp = app.get('/tenants/%s/tokens/request' % TENANT_ID, status=200)
    try:
        data = resp.json['data']
        uuid.UUID(data['token'])
    except Exception:
        pytest.fail('token request failed')

    log_entry = spynl_data_db.spynl_audit_log.find_one()
    assert log_entry['current_tenant_id'] == 'master'
    assert log_entry['requested_tenant_id'] == '1'
    assert log_entry['message'] == 'Token request'

    # created by master user
    assert data['created']['user']['username'] == login['username']
    # created for the owner
    assert data['user_id'] == str(USERID)


@pytest.mark.parametrize('login', [('user4', PASSWORD)], indirect=True)
def test_request_token_other_tenant(app, login, spynl_data_db):
    """Test requesting tokens"""
    app.get('/tenants/%s/tokens/request' % TENANT_ID, status=403)


@pytest.mark.parametrize('login', [('user2', PASSWORD)], indirect=True)
def test_request_token_inactive_tenant(app, login, spynl_data_db):
    """Test requesting tokens"""
    app.get('/tenants/%s/tokens/request' % '5', status=400)


@pytest.mark.parametrize('login', [('user2', PASSWORD)], indirect=True)
def test_request_token_tenant_no_owner(app, login, spynl_data_db):
    """Test requesting tokens"""
    app.get('/tenants/%s/tokens/request' % '6', status=400)


@pytest.mark.parametrize('login', [('user2', PASSWORD)], indirect=True)
def test_request_token_tenant_no_owner_2(app, login, spynl_data_db):
    """Test requesting tokens"""
    app.get('/tenants/%s/tokens/request' % '7', status=400)


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_request_token_with_description(app, login, spynl_data_db):
    """Test requesting tokens"""
    resp = app.get('/tokens/request', params={'description': 'mycomment'}, status=200)
    token = spynl_data_db.tokens.find_one(
        {'token': uuid.UUID(resp.json['data']['token'], version=4)}
    )
    assert token['description'] == 'mycomment'


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_request_token_with_failing_foxpro(app, login, patch_foxpro_fail):
    """Test requesting tokens"""
    resp = app.get('/tokens/request', status=400)
    assert resp.json['type'] == 'TokenError'


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_active_tokens(app, login):
    """test listing tokens."""
    token = app.get('/tokens/request', status=200).json['data']['token']
    headers = {'Authorization': 'Bearer ' + token}
    response = app.get('/tokens/get', headers=headers)
    obfuscated = response.json['data']['active'][0]['token']
    assert token.endswith(obfuscated.replace('*', ''))


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_list_tokens(app, login):
    """test listing tokens with revoked among them."""
    # we will revoke this one.
    token = app.get('/tokens/request', status=200).json['data']['token']
    # and add another one to leave active
    app.get('/tokens/request', status=200).json['data']['token']

    app.post_json('/tokens/revoke', {'token': token})

    headers = {'Authorization': 'Bearer ' + token}
    data = app.get('/tokens/get', headers=headers).json['data']
    assert all([len(data[key]) == 1 for key in ('revoked', 'active')])


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_revoke_token(app, login):
    """test revoking tokens."""
    token = app.get('/tokens/request', status=200).json['data']['token']
    # revoke it.
    app.post_json('/tokens/revoke', {'token': token}, status=200)


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_cannot_authenticate_with_revoked_token(app, login):
    """test cannot authenticate_with_revoked_token."""
    token = app.get('/tokens/request', status=200).json['data']['token']
    # revoke it.
    app.post_json('/tokens/revoke', {'token': token}, status=200)
    # make sure we it doesn't use the session.
    app.get('/logout')
    # check we cannot be authenticated with this token
    app.get('/about/versions', headers={'Authorization': 'Bearer ' + token}, status=403)


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_revoke_without_id_without_header(app, login):
    app.post_json('/tokens/revoke', {}, status=400)


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_revoke_non_existent_token_id(app, login):
    app.post_json('/tokens/revoke', {'token': str(uuid.uuid4())}, status=400)


@pytest.mark.parametrize('login', [(USERNAME, PASSWORD)], indirect=True)
def test_revoke_non_existent_token(app, login):
    token = uuid.uuid4().hex
    headers = {'Authorization': 'Bearer ' + token}
    app.post_json('/tokens/revoke', headers=headers, status=400)
