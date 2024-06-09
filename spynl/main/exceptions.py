"""Generic custom exceptions for all packages to use."""

from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden

from spynl.locale import SpynlTranslationString as _


class SpynlException(Exception):
    """
    The Superclass for all Spynl-specific Exceptions.

    If your Exception inherits from this, the Spynl Error handling
    can treat it differently, e.g. show its message.
    You can also specify with which HTTP exception it should be
    escalated.

    param message: A message for the enduser. Exposed, should NOT contain
                   sensitive data.
    param developer_message: A message for 3rd party users of our API.
                             Exposed, should NOT contain sensitive data.
    param debug_message: A message for internal use when debugging.

    External exceptions can be mapped to internal SpynlExceptions by registering
    the external error with the 'register_external_exception' decorator at the
    internal SpynlException. For the mapping to work, the
    catch_mapped_exceptions function needs to be registered as a view deriver.
    """

    http_escalate_as = HTTPBadRequest
    monitor = True

    def __init__(
        self,
        message='an internal error has occured',
        developer_message=None,
        debug_message=None,
        monitor=None,
    ):
        super().__init__(*self.args)
        # set messages
        self.message = message
        self.developer_message = developer_message
        if developer_message and not debug_message:
            debug_message = developer_message

        self.debug_message = debug_message
        # Pass False if you don't want the exception to be sent to sentry
        if monitor is not None:
            self.monitor = monitor

    def make_response(self):
        """
        Return a response as a dictionary.

        If an exception needs to store additional information in the reponse
        it can be overriden in the following way.

        >>> def make_reponse(self):
                response = super().make_response()
                response.update({
                    'extra': 'Some extra information'
                })
                return response
        """
        response = {
            'status': 'error',
            'type': self.__class__.__name__,
            'message': self.message,
            'developer_message': getattr(self, 'developer_message', self.message),
        }

        return response

    def __str__(self):
        """
        This will return a str version of the message. If the message is a
        SpynlTranslationString, it will return an interpolated version of the
        default (no translation).
        """
        return str(self.message)

    # Dictonary of exception mappings, keys are external exception classes,
    # values are the corresponding internal exception classes
    _exception_mapping = {}

    @classmethod
    def register_external_exception(cls, external_class):
        """
        A decorator to map the decorated SpynlException class to an external
        exception class.
        """

        def decorator(internal_class):
            # Make sure a failure occurs at start up, and not during runtime:
            if not issubclass(internal_class, cls):
                raise Exception(
                    'You can only map an external exception to a SpynlException.'
                )
            cls._exception_mapping[external_class] = internal_class
            return internal_class

        return decorator

    @classmethod
    def create_mapped_exception(cls, external_exception):
        """
        return the internal exception corresponding to the external exception
        """
        internal_class = cls._exception_mapping.get(external_exception.__class__)
        if internal_class:
            internal_exception = internal_class()
            internal_exception.set_external_exception(external_exception)
            return internal_exception
        return None

    def set_external_exception(self, external_exception):
        """
        Set external exception, extend in a subclass to move data from the
        external excpetion to the internal exception.
        """
        self._external_exception = external_exception


# This function is for now not registered in spynl.main itself, and can
# be registered in any plugger.py in case the plugger uses the mapping
# functionality.
def catch_mapped_exceptions(endpoint, info):
    """
    If this function is registered as a view deriver, it will map external
    exceptions to specific SpynlExceptions if the mapping is registered in
    SpynlException.
    """

    def wrapper_view(context, request):
        try:
            return endpoint(context, request)
        except Exception as exception:
            new_exception = SpynlException.create_mapped_exception(exception)
            if new_exception:
                raise new_exception from exception
            raise

    return wrapper_view


class BadOrigin(SpynlException):
    """Bad origin exception."""

    http_escalate_as = HTTPForbidden

    def __init__(self, origin):
        """Set the origin attribute."""
        message = _('bad-origin', mapping={'origin': origin})
        super().__init__(message=message)


class IllegalAction(SpynlException):
    """Raise if the desired action is not allowed."""

    pass


class MissingParameter(SpynlException):
    """Exception when parameter is missing."""

    monitor = False

    def __init__(self, param):
        """Exception message."""
        message = _('missing-parameter', mapping={'param': param})
        super().__init__(message=message)


class IllegalParameter(SpynlException):
    """Exception when parameter is illegal."""

    def __init__(self, param):
        """Exception message."""
        message = _('illegal-parameter', mapping={'param': param})
        super().__init__(message=message)


class InvalidResponse(SpynlException):
    """Exception when the response should be validated, but could not."""

    def __init__(self, error):
        """Exception message."""
        message = _('invalid-response', mapping={'error': error})
        super().__init__(message=message)


class EmailTemplateNotFound(SpynlException):
    """Exception when email template file is not found."""

    def __init__(self, template):
        """Exception message."""
        message = _('email-tmpl-not-found', mapping={'template': template})
        super().__init__(message=message)


class EmailRecipientNotGiven(SpynlException):
    """Exception when there is no recipient for the email"""

    def __init__(self):
        """Exception message."""
        message = _('email-recipient-not-given')
        super().__init__(message=message)
