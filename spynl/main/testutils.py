"""Helper functions for tests to use."""


import json


def post(
    application,
    view,
    params=None,
    content_type='application/json',
    expect_errors=False,
    return_headers=False,
):
    """
    Make a POST request and get a json object back.

    Helper method to save typing.
    """
    if params is None:
        params = {}
    if 'json' in content_type:
        paramstr = json.dumps(params)
    response = application.post(
        view,
        params=paramstr,
        headers={'Content-Type': content_type},
        expect_errors=expect_errors,
    )
    if response.text:
        rtext = json.loads(response.text)
        if return_headers:
            return rtext, response.headers
        else:
            return rtext
    if return_headers:
        return response.headers


def get(application, path, expect_errors=False, return_headers=False, headers=None):
    """
    Make a GET request and get a json object back.

    Helper method to save typing.
    """
    response = application.get(path, expect_errors=expect_errors, headers=headers)
    if response.text:
        rtext = json.loads(response.text)
        if return_headers:
            return rtext, response.headers
        else:
            return rtext
    if return_headers:
        return response.headers
