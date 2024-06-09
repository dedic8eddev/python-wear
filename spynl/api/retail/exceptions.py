"""Exceptions."""

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


class InvalidParameter(SpynlException):
    """Given parameter has bad value."""

    def __init__(self, param):
        message = _('invalid-parameter', mapping={'param': param})
        super().__init__(message=message)


class IllegalPeriod(SpynlException):
    """Selected period cannot be used."""

    def __init__(self, period):
        """Exception message."""
        message = _('illegal-period', mapping={'period': period})
        super().__init__(message=message)


class DuplicateTransaction(SpynlException):
    """Raise when a transaction is duplicate."""

    message = _('transaction-error-duplicate-transaction')

    def __init__(self, developer_message=''):
        """Pass the standard message along with any custom information to developers."""
        super().__init__(message=self.message, developer_message=developer_message)


class TransactionError(SpynlException):
    """Raise when transaction is invalid and manually inform Sentry."""

    message = ''

    def __init__(self, *args, **kwargs):
        """Set custom message and call super class."""
        kwargs['message'] = self.message
        super().__init__(*args, **kwargs)


class WarehouseNotFound(TransactionError):
    """Raise when warehouse cannot be found."""

    message = _('warehouse-not-found')


class NoDataToExport(SpynlException):
    monitor = False

    def __init__(self):
        message = _('no-data-to-export')
        super().__init__(message=message)
