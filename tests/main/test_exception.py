"""Test functions from spynl.main."""
import pytest
from marshmallow import Schema, fields
from pyramid.httpexceptions import HTTPConflict

from spynl.main.exceptions import SpynlException, catch_mapped_exceptions


@pytest.fixture
def exception_app(app_factory, settings, monkeypatch):
    """Plugin an endpoint that always raises and echo's back information."""

    def patched_plugin_main(config):
        def raise_validation_error(request):
            """
            Always raises a validationerror.
            """

            class S(Schema):
                x = fields.String(required=True)

            S().load({})

        def buggy_endpoint(request):
            """
            This endpoint only raises an external exception that needs to be mapped
            to a SpynlException
            """
            raise ToBeMapped(extra='extra info')

        def echo_raise(request):
            """
            Always raises.

            If some information is passes in the query params it is included
            within the reponse.
            """
            if request.GET:

                class CustomException(SpynlException):
                    def make_response(self):
                        data = super().make_response()
                        data.update(request.GET)
                        return data

                raise CustomException
            raise SpynlException

        config.add_view_deriver(catch_mapped_exceptions)

        config.add_endpoint(echo_raise, 'echo-raise')
        config.add_endpoint(raise_validation_error, 'raise-validation-error')
        config.add_endpoint(buggy_endpoint, 'buggy-endpoint')

    # monkeypatch spynl.main.plugins.main as it is a simple entry point without
    # internal logic where normally external plugins would get included.
    monkeypatch.setattr('spynl.main.plugins.main', patched_plugin_main)
    app = app_factory(settings)

    return app


class ToBeMapped(Exception):
    """
    dummy exception that stands in for an exception from spynl.models
    """

    def __init__(self, extra):
        super().__init__()
        self.extra = extra

    def __str__(self):
        return 'An external message'


@SpynlException.register_external_exception(ToBeMapped)
class Mapped(SpynlException):
    """
    corresponding SpynlException exception to ToBeMapped
    """

    http_excalate_as = HTTPConflict

    def __init__(self):
        message = 'This is a Spynl message'
        super().__init__(message=message)
        self.extra = ''

    def make_response(self):
        """Return the standard response, but add the extra information."""
        response = super().make_response()
        response.update({'extra': self.extra})
        return response

    def set_external_exception(self, external_exception):
        super().set_external_exception(external_exception)
        self.debug_message = str(self._external_exception)
        self.extra = self._external_exception.extra


def test_spynlexception(exception_app):
    """Test regular SpynlException"""
    response = exception_app.get('/echo-raise', expect_errors=True)
    assert response.json == SpynlException().make_response()


def test_overridden_spynlexception(exception_app):
    """Test overridden SpynlException"""
    response = exception_app.get(
        '/echo-raise', params={'custom': 'blah'}, expect_errors=True
    )
    assert response.json.get('custom') == 'blah'


def test_spynlexception_developer_message():
    """Test SpynlException dev message"""
    e = SpynlException(developer_message='blah')
    assert e.make_response()['developer_message'] == 'blah'


def test_spynlexception_debug_message():
    """Test SpynlException debug message"""
    e = SpynlException(debug_message='blah')
    assert 'debug_message' not in e.make_response()


def test_exception_mapping(exception_app):
    """
    ToBeMapped exception should get mapped to the correct SpynlException
    """
    response = exception_app.post_json(
        '/buggy-endpoint', status=409, expect_errors=True
    )
    assert response.json_body['extra'] == 'extra info'
    assert response.json_body['message'] == 'This is a Spynl message'


def test_validation_error(exception_app):
    response = exception_app.get('/raise-validation-error', expect_errors=True)
    expected = dict(
        status='error',
        type='ValidationError',
        validationError={'x': ['Missing data for required field.']},
    )
    assert response.status_code == 400 and all(
        i in response.json_body.items() for i in expected.items()
    )
