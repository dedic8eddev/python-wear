"""Custom exceptions for spynl.mongo package."""

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


class DuplicateTransaction(SpynlException):
    def __init__(self, numbers, *args, **kwargs):
        message = _('duplicate-transaction', mapping={'numbers': numbers})
        super().__init__(message=message, *args, **kwargs)


class CannotFindLinkedData(SpynlException):
    """Raised when data that links to a user does not exist in database."""

    def __init__(self, data):
        """Set the data that cannot be found on the database."""
        message = _('cannot-find-linked-data', mapping={'data': data})
        super().__init__(message=message)


class UnindexedQuery(SpynlException):
    """Raise when a query to database does not include any index key."""

    pass
