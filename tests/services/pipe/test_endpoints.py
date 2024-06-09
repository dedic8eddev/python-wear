import pytest
import responses

from spynl.api.auth.testutils import mkuser


@pytest.fixture(autouse=True, scope='function')
def user(app, db, monkeypatch):
    mkuser(
        db,
        'user',
        'pwd',
        ['1'],
        settings={'payNLStoreId': '1', 'payNLDeviceId': '1', 'pinProvider': 'payNL'},
    )
    mkuser(
        db,
        'user2',
        'pwd',
        ['1'],
        settings={
            'payNLStoreId': '1',
            'payNLDeviceId': '1',
            'pinProvider': 'payNL',
            'payNLToken': '2',
        },
    )
    mkuser(
        db,
        'user3',
        'pwd',
        ['1'],
        settings={
            'payNLStoreId': '1',
            'payNLDeviceId': '1',
            'pinProvider': 'payNL',
            'payNLToken': '',
        },
    )
    db.tenants.insert_one({'_id': '1', 'settings': {'payNLToken': '1'}, 'active': True})


@pytest.fixture(autouse=True, scope='function')
def response(app, monkeypatch):
    responses.add(
        responses.POST,
        'https://rest-api.pay.nl/v13/Transaction/start/json',
        json={'success': 1},
        status=200,
    )


@responses.activate
def test_pay_nl_request_uses_tenant_token_when_not_available_in_user(app, monkeypatch):
    app.get('/login?username=%s&password=%s' % ('user', 'pwd'))
    app.post_json(
        '/pay-nl',
        {'payNLPayload': {'something': 'something', 'anotherthing': 'anotherthing'}},
        status=200,
    )

    assert (
        responses.calls[0].request.url
        == 'https://rest-api.pay.nl/v13/Transaction/start/json'
    )
    assert responses.calls[0].request.headers['Authorization'] == "Basic 1"
    assert (
        responses.calls[0].request.body
        == 'something=something&anotherthing=anotherthing'
    )


@responses.activate
def test_pay_nl_request_uses_user_token_when_available(app, monkeypatch):
    app.get('/login?username=%s&password=%s' % ('user2', 'pwd'))
    app.post_json(
        '/pay-nl',
        {'payNLPayload': {'something': 'something', 'anotherthing': 'anotherthing'}},
        status=200,
    )

    assert (
        responses.calls[0].request.url
        == 'https://rest-api.pay.nl/v13/Transaction/start/json'
    )
    assert responses.calls[0].request.headers['Authorization'] == "Basic 2"
    assert (
        responses.calls[0].request.body
        == 'something=something&anotherthing=anotherthing'
    )


@responses.activate
def test_pay_nl_request_uses_tenant_token_when_user_token_is_empty(app, monkeypatch):
    app.get('/login?username=%s&password=%s' % ('user3', 'pwd'))
    app.post_json(
        '/pay-nl',
        {'payNLPayload': {'something': 'something', 'anotherthing': 'anotherthing'}},
        status=200,
    )

    assert (
        responses.calls[0].request.url
        == 'https://rest-api.pay.nl/v13/Transaction/start/json'
    )
    assert responses.calls[0].request.headers['Authorization'] == "Basic 1"
    assert (
        responses.calls[0].request.body
        == 'something=something&anotherthing=anotherthing'
    )
