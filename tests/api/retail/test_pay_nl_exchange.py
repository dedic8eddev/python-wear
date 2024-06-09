import uuid

import pytest


@pytest.mark.parametrize('method', ['get', 'post'])
def test_exchange_post(app, spynl_data_db, method):
    app.extra_environ.update({'REMOTE_ADDR': '127.0.0.1'})

    params = {'a': uuid.uuid4().hex}
    if method == 'post':
        response = app.post_json('/pay-nl-exchange', params)
    elif method == 'get':
        response = app.get('/pay-nl-exchange', params)

    assert spynl_data_db.pay_nl_exchange.count_documents(params) == 1
    assert response.content_type == 'text/plain'
    assert response.text == 'TRUE'


# def test_exchange_fail(app, spynl_data_db):
#     app.extra_environ.update({'REMOTE_ADDR': '0.0.0.0'})
#     params = {'a': uuid.uuid4().hex}
#     app.get('/pay-nl-exchange', params, status=401)


def test_exchange_no_params(app, spynl_data_db):
    app.extra_environ.update({'REMOTE_ADDR': '127.0.0.1'})
    app.post_json('/pay-nl-exchange', status=400)
