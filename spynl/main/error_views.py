"""
Error views for 4xx and 5xx HTTP errors
"""
import itertools
import os
import traceback

from pyramid.authorization import ACLDenied
from pyramid.httpexceptions import HTTPForbidden, HTTPInternalServerError, HTTPNotFound

from spynl.locale import SpynlTranslationString as _

from spynl.main.utils import log_error


def validation_error(exc, request):
    """
    Handle raised ValidationErrors from marshmallow.
    """
    request.response.status_int = 400
    request.response.content_type = 'application/json'  # this is Spynl default

    top_msg = "Spynl Error of type %s with errors: '%s'"
    log_error(exc, request, top_msg, error_msg=exc.normalized_messages())
    message = _('validation-error')
    return dict(
        status='error',
        type=exc.__class__.__name__,
        message=message,
        validationError=exc.normalized_messages(),
    )


def spynl_error(exc, request):
    """
    Handle raised SpynlExceptions.

    Get meta info from the assorted HTTP Error, log information and return
    a typical Spynl response.
    """
    http_exc = exc.http_escalate_as()
    request.response.status = http_exc.status
    request.response.status_int = http_exc.status_int
    request.response.content_type = 'application/json'  # this is Spynl default

    top_msg = "Spynl Error of type %s with message: '%s'"
    log_error(exc, request, top_msg)

    return exc.make_response()


def error400(exc, request):
    """
    Handle all HTTPErrors.

    We collect information about the original error as best as possible.
    We log information and return a typical Spynl response.
    """
    # Set response meta data
    request.response.status = exc.status
    request.response.status_int = exc.status_int
    request.response.content_type = 'application/json'  # this is Spynl default

    error_type = exc.__class__.__name__

    if isinstance(exc, HTTPNotFound):
        message = _('no-endpoint-for-path', mapping={'path': request.path_info})
    elif (
        isinstance(exc, HTTPForbidden)
        and hasattr(exc, 'result')
        and exc.result is not None
    ):
        if isinstance(exc.result, ACLDenied):
            message = _(
                'permission-denial',
                mapping={
                    'context': request.context.__class__.__name__,
                    'permission': exc.result.permission,
                },
            )
            # TODO: log exc.result as detail info
        else:
            message = exc.result.msg
    elif isinstance(exc, HTTPInternalServerError):
        message = _('internal-server-error')
    else:
        message = exc.explanation
        if exc.detail:
            if ":" in exc.detail:
                error_type, message = exc.detail.split(':', 1)
            else:
                message = exc.detail

    top_msg = "HTTP Error of type %s with message: '%s'."
    log_error(exc, request, top_msg, error_type=error_type, error_msg=message)

    response = {'status': 'error', 'type': error_type, 'message': message}
    if hasattr(exc, 'details') and exc.details:
        response['details'] = exc.details

    return response


def error500(exc, request):
    """
    Handle all failures we do not anticipate in error.

    Give back json, set the error status to 500,
    and only include minimal information (to decrease attack vector).
    However, we log all information we can about the error for debugging.
    """
    # First set some response metadata
    request.response.status_int = 500
    request.response.content_type = 'application/json'  # this is Spynl default

    top_msg = "Server Error (500) of type '%s' with message: '%s'."
    log_error(exc, request, top_msg)

    response = {'status': 'error', 'message': _('internal-server-error')}

    if os.environ.get('SPYNL_INCLUDE_TRACEBACK_IN_500_ERROR_RESPONSE') == 'true':
        tb = itertools.chain.from_iterable(
            line.split('\n', 1) for line in traceback.format_tb(exc.__traceback__)
        )
        response['traceback'] = list(tb)

    return response
