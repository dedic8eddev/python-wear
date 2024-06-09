"""Custom handling of images uploaded through spynl.upload."""


import base64
import binascii
import logging
import os
from io import BytesIO
from urllib.parse import urljoin, urlparse

import boto3
import botocore
from PIL import Image

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException
from spynl.main.utils import get_settings

from spynl.api.auth.utils import lookup_tenant

from spynl.services.upload.exceptions import (
    ImageError,
    ImageNotFound,
    S3ConnectionError,
)
from spynl.services.upload.utils import check_s3_credentials

MAX_FILE_SIZE = 5120000


class BaseImage:
    """Functionality to handle an Image."""

    supported_formats = {'JPEG', 'PNG', 'GIF'}

    def __init__(self, input_string, filename=''):
        """Save the image input_string and the filename to be written to."""
        self.filename = filename
        self.img = input_string

    @property
    def img_bstring(self):
        """Return the byte-string of the loaded image."""
        return self._img_bstring

    @img_bstring.setter
    def img_bstring(self, value):
        """
        Decode string to base64 byte-string.

        Handle any metadata in string before decoding it.
        If value is bytes, then it means that after image was shrinked, a new
        byte-string will be set to _img_bstring.
        """
        if isinstance(value, str):
            if ',' in value:
                value = value.split(',')[1]
            value = value.encode('utf-8')
            try:
                self._img_bstring = base64.b64decode(value, validate=True)
            except binascii.Error as err:
                raise ImageError(_('no-base64-image')) from err
        elif isinstance(value, bytes):
            self._img_bstring = value

    @property
    def img(self):
        """Return the loaded image."""
        return self._img

    @img.setter
    def img(self, value):
        """
        Load image from either string or byte-string.

        First set the img_bstring before loading the image, it will be handy to
        get the current byte size of loaded image when lowering it's size.
        Raise exception if image format is not supported.
        """
        self.img_bstring = value
        try:
            self._img = Image.open(BytesIO(self.img_bstring))
        except IOError as err:
            raise ImageError(
                _('not-image-file', mapping={'filename': self.filename})
            ) from err
        if self._img.format not in self.supported_formats:
            raise SpynlException(_('unsupported-image'))

    @property
    def byte_size(self):
        """Return the file size of the decoded image string."""
        return len(self.img_bstring)

    @property
    def max_file_size(self):
        """Return the maximum accepted file size."""
        return MAX_FILE_SIZE

    @property
    def extension(self):
        """Return the image file format."""
        return self.img.format.lower()

    @staticmethod
    def s3_domain():
        """Construct the s3 domain from the settings and return it."""
        return 'https://cdn.' + get_settings()['spynl.domain']

    def is_larger(self, width, height):
        """Return True if image is larger than given width/height."""
        if self.img.size[0] > width or self.img.size[1] > height:
            return True
        return False

    def ensure_file_extension(self):
        """Add image extension if <filename> doesn't end with that."""
        if not self.filename.endswith(self.extension):
            self.filename = self.filename.rstrip('.')
            self.filename += '.' + self.extension

    def shrink_by_quality(self):
        """
        Shrink the image size by reducing quality by a factor of 10.

        From Pillow library: <quality> is a scale from 1 (worst) to 95 (best).
        The default is 75. Values above 95 should be avoided; 100 disables
        portions of the JPEG compression algorithm, and results in large files
        with hardly any gain in image quality.
        The save method from pillow is used as it provides access to the
        quality setting of the JPEG library.
        """
        quality = 71
        while quality > 1:
            with BytesIO() as fob:
                try:
                    self.img.verify()

                    temp_img = self.img.copy()
                    temp_img.save(fob, format='JPEG', quality=quality)
                except Exception as err:
                    self.handle_shrinking_error(err)
                else:
                    temp_img_bstring = fob.getvalue()

                    if len(temp_img_bstring) <= self.max_file_size:
                        self.img = temp_img_bstring
                        break
                    quality -= 10

    def shrink_by_size(self, size):
        """
        Shrink the image to the given size.

        The save method from pillow is called because by saving in a file-like
        object, we return the data into the format bot will accept
        (base64-encoded bytestring - the .tobytes() method exists but returns
        raw pixel data).
        """
        with BytesIO() as fob:
            try:
                self.img.thumbnail(size, Image.Resampling.LANCZOS)
                self.img.save(fob, format=self.img.format)
            except Exception as err:
                self.handle_shrinking_error(err)
            else:
                self.img = fob.getvalue()

    @staticmethod
    def handle_shrinking_error(err):
        """
        Reraise ImageError in case something goes bad in shrinking funcs.

        Log the error too.
        """
        logging.getLogger(__name__).error(
            'There was a problem while lowering the image size: %s', err
        )
        raise ImageError(_('img-error-shrinking'))

    def _upload(self, file_path=''):
        """Upload the image to a bucket in AWS and return it's url."""
        conn_problems = check_s3_credentials()
        if conn_problems != '':
            raise S3ConnectionError(conn_problems)
        s3 = boto3.resource('s3')
        s3.Object(os.environ['S3_UPLOAD_BUCKET'], file_path).put(
            Body=self.img_bstring, ContentType='image/' + self.extension
        )

        return urljoin(self.s3_domain(), file_path)

    @staticmethod
    def _remove(file_path=''):
        """Delete the image from a bucket in AWS."""
        conn_problems = check_s3_credentials()
        if conn_problems != '':
            raise S3ConnectionError(conn_problems)
        # if a url is given instead of just the file path, remove the s3
        # domain part:
        file_path = urlparse(file_path).path.lstrip('/')
        s3 = boto3.client('s3')
        kwargs = dict(Bucket=os.environ['S3_UPLOAD_BUCKET'], Key=file_path)
        try:
            s3.head_object(**kwargs)
        except botocore.exceptions.ClientError as err:
            if err.response['Error']['Code'] == "404":
                raise ImageNotFound(file_path) from err
            else:
                raise
        s3.delete_object(**kwargs)


class SpynlImage(BaseImage):
    """Like BaseImage but with size limits."""

    size_limits = (2048, 2048)

    def save(self, tenant_dir=''):
        """Shrink image if necessary, upload it to AWS and return it's url."""
        if self.is_larger(*self.size_limits):
            self.shrink_by_size(self.size_limits)
            if self.byte_size > self.max_file_size:
                self.shrink_by_quality()
            if self.byte_size > self.max_file_size:
                raise ImageError(_('img-err-oversized'))
            self.ensure_file_extension()
        file_path = tenant_dir.strip('/') + '/' + self.filename
        image_url = self._upload(file_path=file_path)

        return image_url


class SpynlLogo(BaseImage):
    """Like SpynlImage but with lower size limits."""

    size_limits = {'fullsize': (512, 512), 'medium': (256, 256), 'thumbnail': (64, 64)}

    def save(self, request, tenant_dir='', tenant_id=None):
        """
        Save logo image to AWS and return their urls.

        Make copies to all defined sizes, suffix filenames with their sizes
        and upload them to AWS.
        Removes previous images if there are any.
        Lastly save their urls to tenant's settings.
        """
        tenant_dir = tenant_dir.strip('/')
        tenant = lookup_tenant(request.db, tenant_id)

        size_urls = {'fullsize': '', 'medium': '', 'thumbnail': ''}
        uploaded_filenames = []
        for size in ('fullsize', 'medium', 'thumbnail'):
            if self.is_larger(*self.size_limits[size]):
                self.shrink_by_size(self.size_limits[size])
                self.ensure_file_extension()
                filename = self.suffixed_filename(self.img.size)
            else:
                filename = self.filename

            file_path = tenant_dir + '/' + filename
            if filename not in uploaded_filenames:
                uploaded_filenames.append(filename)
                url = self._upload(file_path=file_path)
            else:
                url = self.s3_domain() + '/' + file_path
            old_url = tenant.get('settings', {}).get('logoUrl', {}).get(size)
            # only remove if the old url is different from the new one.
            # NOTE: this will go wrong if the old logo has a different
            # s3_domain
            if old_url and old_url != url:
                try:
                    self._remove(old_url)
                except ImageNotFound:
                    pass  # no need to remove if it doesn't exist
            size_urls[size] = url

        query = {
            '$set': {'settings.logoUrl.' + key: url for key, url in size_urls.items()}
        }
        request.db.tenants.update_one({'_id': tenant_id}, query)
        return size_urls

    @classmethod
    def remove(cls, request, tenant_id=None):
        """
        Remove all Logo images from AWS and clear the url's in settings.
        """
        tenant = lookup_tenant(request.db, tenant_id)
        sizes = ('fullsize', 'medium', 'thumbnail')
        for size in sizes:
            url = tenant.get('settings', {}).get('logoUrl', {}).get(size)
            if url:
                try:
                    cls._remove(url)
                except ImageNotFound:
                    pass  # no need to remove if it doesn't exist

        # remove urls from settings:
        logoUrl = {size: None for size in sizes}
        request.db.tenants.update_one(
            {'_id': tenant_id}, {'$set': {'settings.logoUrl': logoUrl}}
        )

    def suffixed_filename(self, size):
        """Add the size to the end of the filename."""
        ext = '.' + self.extension
        if self.filename.endswith(ext):
            filename = self.filename[: -len(ext)]
        else:
            filename = self.filename

        suffix = '_{}x{}'.format(*size)
        filename += suffix + ext
        return filename
