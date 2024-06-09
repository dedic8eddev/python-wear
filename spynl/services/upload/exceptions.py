"""Exceptions for spynl.upload."""

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


class S3ConnectionError(SpynlException):
    """Exception message for errors in establishing S3 connections."""

    def __init__(self, error):
        """Exception message."""
        message = _('s3-connection', mapping={'error': error})
        super().__init__(message=message)


class ImageError(SpynlException):
    """Exception message for errors in handling the images."""

    def __init__(self, error):
        """Exception message."""
        message = _('image-error', mapping={'error': error})
        super().__init__(message=message)


class ImageNotFound(SpynlException):
    """Exception message for a file that is not found."""

    def __init__(self, path):
        """Exception message."""
        # TODO: there is a difference between the url and the path, I don't
        # know which would be more descriptive
        message = _('image-not-found', mapping={'path': path})
        super().__init__(message=message)
