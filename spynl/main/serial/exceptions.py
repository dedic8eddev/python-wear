"""Custom (de)serialisation Exceptions."""


from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


class UndeterminedContentTypeException(SpynlException):
    """Undetermined Content Type."""

    def __init__(self):
        """Exception message."""
        message = _('undetermined-content-type-exception')
        super().__init__(message=message)


class UnsupportedContentTypeException(SpynlException):
    """Unsupported Content Type."""

    def __init__(self, content_type):
        """Exception message."""
        message = _(
            'unsupported-content-type-exception', mapping={'type': content_type}
        )
        super().__init__(message=message)


class DeserializationUnsupportedException(SpynlException):
    """Deserialisation not supported."""

    def __init__(self, content_type):
        """Exception message."""
        message = _(
            'deserialization-unsupported-exception', mapping={'type': content_type}
        )
        super().__init__(message=message)


class SerializationUnsupportedException(SpynlException):
    """Serialization not supported."""

    def __init__(self, content_type):
        """Exception message."""
        message = _(
            'serialization-unsupported-exception', mapping={'type': content_type}
        )
        super().__init__(message=message)


class MalformedRequestException(SpynlException):
    """Malformed reqeust - first give message then content type."""

    def __init__(self, content_type, error_cause=None):
        """Exception message."""
        if error_cause:
            message = _(
                'malformed-request-exception-type',
                mapping={'type': content_type, 'request': error_cause},
            )
        else:
            message = _('malformed-request-exception', mapping={'type': content_type})
        super().__init__(message=message)
