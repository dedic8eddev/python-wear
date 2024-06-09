import pytest
import responses

from spynl.api.auth.authentication import scramble_password


@pytest.fixture(autouse=True, scope='function')
def user(db):
    db.tenants.insert_one(
        {
            '_id': '1',
            'settings': {'fetchBarcodeFromLatestCollection': True},
            'active': True,
            'applications': ['products', 'pos', 'dashboard'],
        }
    )
    db.users.insert_one(
        {
            'username': 'user',
            'name': 'User Logtest',
            'email': 'user-logtest@email.com',
            'roles': {'1': {'tenant': ['pos-device', 'products-admin']}},
            'default_application': {'1': 'pos'},
            'active': True,
            'hash_type': '1',
            'password_hash': scramble_password('pwd', '', '1'),
            'password_salt': '',
            'tenant_id': ['1'],
        }
    )
    # add access to the latestcollection api


@responses.activate
def test_get_data_from_latest_collection(app):
    user = app.get('/login?username=%s&password=%s' % ('user', 'pwd'))
    user = user.json
    barcode = '12345'
    url_except = (
        'https://latestcollection.fashion/data/'
        '{}/sku?sid={}&id={}&transformer=getRaptorSku'.format(
            user["current_tenant"], user["sid"], barcode
        )
    )

    responses.add(
        responses.GET,
        url_except,
        json={'success': 1},
        status=200,
    )
    payload = {"function": "raptorsku", "query": {"barcode": "12345"}}

    app.post_json('/legacy-api', payload)
    assert responses.calls[0].request.url == url_except
