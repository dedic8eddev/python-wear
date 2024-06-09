import pytest
from pyramid import testing
from pyramid.exceptions import Forbidden

from spynl.main.endpoints import ping
from spynl.main.testutils import get
from spynl.main.utils import check_origin


@pytest.fixture(autouse=True)
def reset_app(app):
    """Reset app, here our aim is to reset cookies."""
    # request.cookiejar is a http.cookiejar.CookieJar
    yield
    app.cookiejar.clear()


@pytest.mark.parametrize(
    "method,language",
    [(None, 'nl'), ('cookie', 'en'), ('header', 'nl'), ('default', 'nl')],
)
def test_response_message(app, method, language, settings):
    """Test /about, with various methods of specifying the language"""
    headers = {}
    if method == 'cookie':
        app.set_cookie('lang', 'en-GB')
    elif method == 'header':
        headers = {'Accept-Language': 'nl'}
    response = get(app, '/about', headers=headers)
    assert response['language'] == language


def test_exception_message_is_translated():
    """Test not whitelisted origin."""
    headers = {"Origin": "Not-a-Url", "Content-Type": "application/json"}
    dr = testing.DummyRequest(headers=headers)
    dr._LOCALE_ = 'nl_NL'
    with testing.testConfig(request=dr) as my_config:
        my_config.add_translation_dirs('spynl:locale/')
        with pytest.raises(Forbidden) as exc_info:
            check_origin(ping(dr), None)(None, dr)
        assert (
            "Requests naar Spynl zijn niet toegestaan"
            " vanaf origin 'Not-a-Url'." in str(exc_info.value)
        )
