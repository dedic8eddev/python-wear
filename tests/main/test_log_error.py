"""Test functions from spynl.main."""
from pyramid.testing import DummyRequest

from spynl.main.exceptions import SpynlException
from spynl.main.utils import log_error

TOP_MSG = "TEST Error of type %s with message: '%s'"


def test_log_error_msg(caplog):
    """Test casting the exception to string."""

    class Error(Exception):
        def __str__(self):
            return "An error has occurred"

    try:
        raise Error
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)
        for rec in caplog.records:
            assert rec.message.startswith(TOP_MSG % ('Error', 'An error has occurred'))


def test_log_exception_name(caplog):
    """Test stripping of "Exception" from the name."""

    class SomeException(Exception):
        pass

    try:
        raise SomeException
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)
        for rec in caplog.records:
            assert 'Exception' not in rec.message


def test_log_exception_default_message(caplog):
    """
    Test default message.

    When the exception has no .message or str(Exc) returns
    an empty string the default message should be logged.
    """

    try:
        raise Exception
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)
        for rec in caplog.records:
            assert 'no-message-available' in rec.message


def test_log_given_exc_type_and_msg(caplog):
    """Test that the given error_type and msg are used."""

    try:
        raise Exception
    except Exception as exc:
        log_error(
            exc, DummyRequest(), TOP_MSG, error_type="Argh", error_msg="what the hell"
        )
        for rec in caplog.records:
            assert "TEST Error of type Argh" in rec.message


def test_log_message(caplog):
    """Test that the default spynlmessage is logged."""

    try:
        raise SpynlException
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)

        for rec in caplog.records:
            assert SpynlException().message in rec.message


def test_log_custom_message(caplog):
    """Test that the custom is logged."""

    try:
        raise SpynlException(message="blah")
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)
        for rec in caplog.records:
            assert 'blah' in rec.message


def test_log_debug_message(caplog):
    """Test that the debug_message is logged."""

    try:
        raise SpynlException(message="blah", debug_message="HI I AM DEBUG")
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)

        for rec in caplog.records:
            assert "HI I AM DEBUG" in rec.message


def test_log_developer_message(caplog):
    """Test that the developer_message is logged."""

    try:
        raise SpynlException(message="blah", developer_message="HI I AM DEVELOPER")
    except Exception as exc:
        log_error(exc, DummyRequest(), TOP_MSG)
        for rec in caplog.records:
            assert "HI I AM DEVELOPER" in rec.message
