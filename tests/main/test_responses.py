# coding=UTF8
"""Testing basic attributes of Spynl responding correctly
to various conditions.
We use the endpoints /ping and /request_echo"""


from json import dumps, loads

import pytest
from webtest import AppError


def test_ping(app):
    """Ping test."""
    response = app.get('/ping')
    rbody = loads(response.text)
    assert rbody['greeting'] == 'pong'
    assert response.headers['Content-Type'] == 'application/json'
    assert response.headers['Content-Length'] == '86'
    assert response.headers['Access-Control-Allow-Credentials'] == 'true'
    assert response.headers['Vary'] == 'Accept-Encoding, Origin'


def test_contenttype_json(app):
    """Test correct parsing of json body when header gives type."""
    headers = {'Content-Type': 'application/json'}
    response = loads(app.post('/request_echo', '{}', headers).text)
    assert response == {"status": "ok"}


def test_get_req_dont_parse_body(app):
    """
    The (accidental) body of a get request should not be parsed.

    Whether the content type is defined in Spynl or not.
    """
    response = loads(
        app.request(
            '/request_echo',
            method='GET',
            body=b'THIS_IS_NOT_JSON',
            headers={'Content-Type': 'application/json'},
        ).text
    )
    assert response['status'] == 'ok'
    response = loads(
        app.request(
            '/request_echo',
            method='GET',
            body=b'A=B',
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        ).text
    )
    assert response['status'] == 'ok'


def test_contenttype_unsupported(app):
    """Raise exception when conttenttype is unsupported."""
    with pytest.raises(AppError, match='Content type is niet ondersteund'):
        app.post('/request_echo', 'wtf', headers={'Content-Type': 'text/plain'})


def test_accepted_contenttype_is_all_of_them(app):
    """Do not fail when accepted conttenttype is set to */*."""
    headers = {'Content-Type': 'application/json', 'Accept': '*/*'}
    response = loads(app.post('/request_echo', '{}', headers).text)
    assert response['status'] == 'ok'


def test_contenttype_csv(app):
    """Test contenttype csv, set response type in URL path."""
    data = [{"a": 100, "b": 200}, {"a": 150, "b": 250}]
    response = app.post('/request_echo.csv', dumps({"data": data}), {}).text
    assert any(
        (
            response == 'a,b\r\n100,200\r\n150,250\r\n',
            response == 'b,a\r\n200,100\r\n250,150\r\n',
        )
    )


def test_json(app):
    """Send JSON data in via a data dictionary (pure JSON), returne it back."""
    data = {'a': 1, 'b': [1.2, 4.5], 'c': {'ca': False, 'cb': 'string1'}}
    str_request = dumps({'data': data})
    response = app.post('/request_check', str_request).text
    assert loads(response)['data'] == data


def test_bad_json(app):
    """Test that bad json in the request raises exceptions."""
    headers = {'Content-Type': 'application/json'}

    with pytest.raises(AppError, match='Expecting value: line 1 column 1'):
        app.post('/request_echo', '<a>', headers=headers)
    with pytest.raises(
        AppError,
        match='Expecting property name enclosed in double quotes: line 1 column 2',
    ):
        app.post('/request_echo', '{', headers=headers)


def test_noresource(app):
    """Test no resource, 404 not found error."""
    with pytest.raises(AppError, match='404 Not Found'):
        app.post('/', '{}', {'Content-Type': ''})


def test_options_request(app):
    """Test if an OPTIONS request is handled correctly as we intend."""
    oheaders = app.options('/ping').headers
    assert oheaders['Access-Control-Max-Age'] == '86400'
    assert oheaders['Access-Control-Allow-Credentials'] == 'true'
    assert oheaders['Content-Length'] == '0'
    assert oheaders['Content-Type'] == 'text/plain'


def test_jsonandget(app):
    """
    Tst json get request.

    JSON data comes in, but gets overwritten by GET data dictionary with
    pure JSON.
    """
    returned = {'a': '1', 'b': ['1.2', '4.5'], 'c': {'ca': 'string1'}}
    response = app.post(
        '/request_echo?data={a:1,b:[1.2,4.5],c:{ca:string1}}', dumps({'data': {'a': 2}})
    ).text
    assert loads(response)['data'] == returned


def test_unicode_roundtrip(app):
    """JSON data with unciode gets posted and comes back correctly."""
    data = {'name': 'H\xf6ning', 'price': '€9'}
    response = app.post('/request_echo', dumps({'data': data})).text
    assert loads(response)['data'] == {'name': 'H\xf6ning', 'price': '€9'}
