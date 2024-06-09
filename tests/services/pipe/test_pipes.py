"""Tests for spynl.pipe."""


import json

import pytest
import requests

from spynl.main.exceptions import SpynlException

from spynl.services.pipe.utils import piping


class MockResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError

    def json(self):
        try:
            return json.loads(self.body)
        except json.decoder.JSONDecodeError:
            raise ValueError


def test_piping_success(monkeypatch):
    class R:
        path_url = 'www.swcloud.nl'
        args = {}

    @piping
    def f(ctx, request):
        return '', None

    def patched_request(*args, **kwargs):
        return MockResponse(200, '{"test": "ok"}')

    monkeypatch.setattr('requests.request', patched_request)
    response = f(None, R())
    assert response['data'] == {'test': 'ok'}


def test_piping_fail(monkeypatch):
    class R:
        path_url = 'www.swcloud.nl'
        args = {}

    @piping
    def f(ctx, request):
        return '', None

    def patched_request(*args, **kwargs):
        return MockResponse(400, '{"test": "error"}')

    monkeypatch.setattr('requests.request', patched_request)

    with pytest.raises(SpynlException):
        f(None, R())


def test_piping_redirect(monkeypatch):
    class R:
        path_url = 'www.swcloud.nl'
        args = {}

    @piping
    def f(ctx, request):
        return '', None

    def patched_request(*args, **kwargs):
        return MockResponse(300, '{"test": "redirect"}')

    monkeypatch.setattr('requests.request', patched_request)

    response = f(None, R())
    assert response['data'] == {'test': 'redirect'}


def test_piping_fp_error(monkeypatch):
    class R:
        path_url = 'www.swcloud.nl'
        args = {}

    @piping
    def f(ctx, request):
        return '', None

    def patched_request(*args, **kwargs):
        return MockResponse(200, '{"error": "blah", "response": "123"}')

    monkeypatch.setattr('requests.request', patched_request)

    with pytest.raises(SpynlException) as e:
        f(None, R())
    assert e.value.message == 'blah'


def test_piping_no_json(monkeypatch):
    class R:
        path_url = 'www.swcloud.nl'
        args = {}

    @piping
    def f(ctx, request):
        return '', None

    def patched_request(*args, **kwargs):
        return MockResponse(300, '"{key": ')

    monkeypatch.setattr('requests.request', patched_request)

    with pytest.raises(SpynlException):
        f(None, R())
