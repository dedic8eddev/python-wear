"""SpynlExceptions for spynl.hr package."""


from pyramid.httpexceptions import HTTPForbidden

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


class ExistingUser(SpynlException):
    """Raise if an existing user is attempted to be created."""

    http_escalate_as = HTTPForbidden

    def __init__(self, username=None, email=None):
        """Set User's username or email or both."""
        if username is not None:
            message = _('existing-user-by-username', mapping={'username': username})
        else:
            message = _('existing-user-by-email', mapping={'email': email})
        super().__init__(message=message)


class UserDoesNotExist(SpynlException):
    """Raise if a requested user does not exist."""

    def __init__(self, user):
        """Exception message."""
        message = _('user-does-not-exist', mapping={'user': user})
        super().__init__(message=message)


class ExistingCustomer(SpynlException):
    def __init__(self):
        """Exception message."""
        message = _('customer-already-exists')
        super().__init__(
            message=message,
            developer_message='A customer with this id already exists. Use the save '
            'endpoint to edit a customer.',
        )


class UserHasNoEmail(SpynlException):
    """
    Users like owners and users with multiple tenants have to have an email
    address
    """

    def __init__(self, username, message=""):
        """Exception message."""
        message = _(
            'user-should-have-email', mapping={'username': username, 'message': message}
        )
        super().__init__(message=message)


class EmailNotSet(SpynlException):
    """User has unset his email address."""

    http_escalate_as = HTTPForbidden
    msg = _('resend-email-verification-key-email-is-not-set')

    def __init__(self):
        super().__init__(message=self.msg)


class TokenError(SpynlException):
    """An exception for tokens operatons."""

    def __init__(self, message, **kwargs):
        super().__init__(message=message, **kwargs)


class AccountImportValidationError(SpynlException):
    """An exception for validation errors in account provisioning"""

    def __init__(self, message, **kwargs):
        # in case the structure of the message is different than we expect,
        # we try except.
        try:
            markdown = message_to_markdown(message)
        except:  # noqa E722
            markdown = message
        super().__init__(message=markdown, developer_message=message, **kwargs)


def message_to_markdown(message):
    """
    Turn the validation message into a markdown message so the frontend can
    display it easily in a readable way.
    """
    markdown = 'The index starts at 0, so a user with index 1 is the second user.\n'
    for heading in ('tenants', 'users', 'cashiers', 'warehouses'):
        if heading in message:
            markdown += '# {}\n'.format(heading)
            if isinstance(message[heading], list):
                markdown += '{}\n'.format(message[heading])
            else:
                markdown += '| index | field | error |\n| --- | --- | --- |\n'
                for entry in sorted(message[heading], key=str):
                    if isinstance(message[heading][entry], list):
                        markdown += '|{}| |{}|\n'.format(entry, message[heading][entry])
                    else:
                        first = 1
                        for field in sorted(message[heading][entry]):
                            if first:
                                markdown += '|{}|{}|{}|\n'.format(
                                    entry, field, message[heading][entry][field]
                                )
                                first = 0
                            else:
                                markdown += '| |{}|{}|\n'.format(
                                    field, message[heading][entry][field]
                                )

    return markdown
