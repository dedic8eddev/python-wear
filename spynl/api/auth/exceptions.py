"""SpynlExceptions for spynl.auth package."""


from pyramid.httpexceptions import HTTPForbidden, HTTPUnauthorized

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


class Forbidden(SpynlException):
    """Raise if an action is forbidden."""

    http_escalate_as = HTTPForbidden


class MissingTenantID(SpynlException):
    """Raise when the tenant ID is missing in the session or request."""

    http_escalate_as = HTTPUnauthorized

    def __init__(self):
        super().__init__(message=_('missing-tenant-id'))


class WrongCredentials(SpynlException):
    """Raise if credentials are incorrect."""

    monitor = False
    http_escalate_as = HTTPUnauthorized

    def __init__(self):
        super().__init__(message=_('wrong-credentials'))


class ExpiredCredentials(SpynlException):
    """Raise if credentials are incorrect."""

    monitor = False
    http_escalate_as = HTTPUnauthorized

    def __init__(self):
        super().__init__(message=_('expired-credentials'))


class UserNotActive(SpynlException):
    """Raise if a user is not active."""

    http_escalate_as = HTTPForbidden

    def __init__(self, user):
        message = _('user-not-active', mapping={'user': user})
        super().__init__(message=message)


class TenantDoesNotExist(SpynlException):
    """Raise if a requested tenant does not exist."""

    http_escalate_as = HTTPForbidden

    def __init__(self, tenant):
        message = _('tenant-does-not-exist', mapping={'tenant': tenant})
        super().__init__(message=message)


class ForbiddenTenant(SpynlException):
    """Raise when the tenant ID is forbidden for the user."""

    http_escalate_as = HTTPForbidden

    def __init__(self):
        super().__init__(message=_('forbidden-tenant'))


class TenantNotActive(SpynlException):
    """Raise if a requested tenant is not active."""

    http_escalate_as = HTTPForbidden

    def __init__(self, tenant):
        message = _('tenant-not-active', mapping={'tenant': tenant})
        super().__init__(message=message)


class NoActiveTenantsFound(SpynlException):
    """Raise if a user has no active tenants."""

    http_escalate_as = HTTPForbidden

    def __init__(self):
        super().__init__(message=_('no-active-tenant-found'))


class CannotRetrieveUser(SpynlException):
    """Raise if a desired user cannot be found."""

    def __init__(self, developer_message=None):
        message = _('cannot-retrieve-user')
        super().__init__(message=message, developer_message=developer_message)


class UnrecognisedHashType(SpynlException):
    """Raise if the hash type in the request is unknown."""

    def __init__(self):
        super().__init__(message=_('unrecognise-hash-type'))


class SpynlPasswordRequirementsException(SpynlException):
    """Raise if password does not conform with our requirements."""

    http_escalate_as = HTTPForbidden

    def __init__(self, message=None):
        """Set the translated message."""
        if message is None:
            message = _('password-does-not-meet-requirements')
        super().__init__(message=message)
