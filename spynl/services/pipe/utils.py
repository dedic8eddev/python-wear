import functools
import logging
import time

import requests

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException

# Errors that we do not want to log to sentry:
EXPECTED_ERRORS = [
    'Barcode not found',
    'Client not found',
    'Coupons expired',
    'Coupons redeemed',
    'Customer not found.',
    'No open coupons found',
]


def piping(f):
    """
    This generator is applied to all custom get methods.
    Here, we measure time, actually pipe the request/reponse
    and log what happened. The decorated function needs to return
    a tuple of a url and post data.
    """
    logger = logging.getLogger(__name__)

    @functools.wraps(f)
    def wrapper(ctx, request):
        start_time = time.time()

        url, data = f(ctx, request)
        params = {'timeout': 300, 'headers': {'Content-Type': 'application/json'}}
        if data:
            response = requests.request('POST', url, json=data, **params)
        else:
            response = requests.request('GET', url, **params)

        try:
            response.raise_for_status()
            response = response.json()
        except (requests.HTTPError, ValueError):
            logger.exception(
                'Piped %s to "%s".' % (request.path_url, url),
                extra={
                    'payload': request.args.get('filter', {}),
                    'meta': {
                        'in_url': request.path_url,
                        'out_url': url,
                        'response': response,
                        'execution_time': time.time() - start_time,
                    },
                },
            )
            raise SpynlException(_('pipe-timeout-error'))

        logger.debug(
            'Piped %s to "%s".' % (request.path_url, url),
            extra={
                'payload': request.args.get('filter', {}),
                'meta': {
                    'in_url': request.path_url,
                    'out_url': url,
                    'response': response,
                    'execution_time': time.time() - start_time,
                },
            },
        )

        if 'error' in response:
            if response['error'] in EXPECTED_ERRORS:
                raise SpynlException(response['error'], monitor=False)
            raise SpynlException(response['error'])

        return {'status': 'ok', 'data': response}

    return wrapper
