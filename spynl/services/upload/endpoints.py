"""
Views for spynl.upload.

This module provides a method to upload an image file to Amazon S3.
"""


from uuid import uuid4

from spynl.locale import SpynlTranslationString as _

from spynl.main.utils import required_args

from spynl.services.upload.image import SpynlImage, SpynlLogo
from spynl.services.upload.utils import get_tenant_upload_dir, secure_filename


@required_args('filename', 'file')
def add_image(request):
    """
    Upload an image to an Amazon S3 bucket.

    Filenames are converted to ASCII, spaces are converted to hyphens, non
    alphanumericals, leading or trailing whitespace characters are removed.
    In addition a unique uuid is inserted before the extension.

    ---
    post:
      tags:
        - services
      description: >
        Usual image types are allowed(jpg, png, bmp, gif).
        \n
        Located in spynl-services.

        ### Parameters

        Parameter | Type         | Req.      | Description\n
        --------- | ------------ | --------- | -----------\n
        filename  | string       | &#10004;  | name of the file\n
        file      | byte array   | &#10004;  | base64 encoded image data\n

        ### Response

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | ok or error\n
        message   | string | description of status\n
        url       | string | url of the uploaded image with unique uuid.(if status=ok)
    """
    input_name = request.args['filename']
    filename = secure_filename(input_name)
    input_file = request.args['file']

    img = SpynlImage(input_file, filename)
    tenant_id = request.requested_tenant_id
    upload_dir = get_tenant_upload_dir(request, tenant_id)
    s3_url = img.save(tenant_dir=upload_dir)

    return {'message': _('upload-complete'), 'url': s3_url}


@required_args('file')
def add_logo(request):
    """
    Upload an image which will be tenant's logo.

    Filenames are converted to ASCII, spaces are converted to hyphens, non
    alphanumericals, leading or trailing whitespace characters are removed.
    In addition a unique uuid is inserted before the extension.

    ---
    post:
      tags:
        - services
      description: >
        Usual image types are allowed(jpg, png, bmp, gif).

        The relevant logo URLs are available as tenant settings
        "logo.fullsize", "logo.medium" and "logo.thumbnail"
        If filename is not given a random uuid4 is created instead.

        Also deletes the files of a previous logo if present.
        \n
        Located in spynl-services.

        ### Parameters

        Parameter | Type         | Req.      | Description\n
        --------- | ------------ | --------- | -----------\n
        filename  | string       | &#10004;  | name of the file\n
        file      | byte array   | &#10004;  | base64 encoded image data\n

        ### Response

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | ok or error\n
        message   | string | description of status\n
        urls      | dict   | urls for uploaded logos with unique uuids. (if status=ok)
    """
    input_name = request.args.get('filename')
    filename = secure_filename(input_name) if input_name else uuid4().hex
    input_file = request.args['file']

    img = SpynlLogo(input_file, filename)
    tenant_id = request.requested_tenant_id
    upload_dir = get_tenant_upload_dir(request, tenant_id) + '/logos'
    size_urls = img.save(request, tenant_dir=upload_dir, tenant_id=tenant_id)

    return {'message': _('upload-complete'), 'urls': size_urls}


def remove_logo(request):
    """
    Remove the logo for a tenant
    ---
    post:
      tags:
        - services
      description: >
        Removes the logo for the requested tenant. Removes the files from S3 and
        sets the logo tenant settings to None.
        \n
        Located in spynl-services.

        ### Response

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | ok or error\n
        message   | string | description of status\n
    """
    SpynlLogo.remove(request, request.requested_tenant_id)
    return {'message': _('upload-logo-removed')}


def no_get(request):
    """Not implemented (yet): function for downloading an image."""
    return {'message': _('only-POST-allowed')}
