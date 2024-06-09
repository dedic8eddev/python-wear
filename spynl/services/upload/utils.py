"""Helper functions for spynl.upload."""

import logging
import os
import re
import unicodedata
import uuid

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ParamValidationError

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException


def check_s3_credentials():
    """Make a request to AWS to check if credentials are correct."""
    logging.getLogger('boto').setLevel(logging.CRITICAL)
    bucket_name = os.environ.get('S3_UPLOAD_BUCKET', '')
    result = ''
    try:
        boto3.client('s3').head_bucket(Bucket=bucket_name)
    except NoCredentialsError:
        result = "Can't find S3 credentials."
    except (ClientError, ParamValidationError) as err:
        if (
            isinstance(err, ParamValidationError)
            or int(err.response['Error']['Code']) == 404
        ):
            result = _(
                'bucket-error',
                default="The bucket '${bucket}' does not exist in S3.",
                mapping={'bucket': bucket_name},
            )
        elif int(err.response['Error']['Code']) == 403:
            result = 'The S3 Credentials are invalid.'
        else:
            result = str(err)

    return result


def get_tenant_upload_dir(request, tenant_id):
    """Return tenant's upload directory path."""
    tenant = request.db.tenants.find_one({'_id': tenant_id}, {'settings': 1})
    upload_dir = tenant.get('settings', {}).get('uploadDirectory')
    if upload_dir is None:
        raise SpynlException(
            _('upload-dir-not-set', default='Upload directory is not set.')
        )
    return upload_dir


def make_filename_unique(filename):
    """
    Append a uuid to a filename. Put it before a potential extension.

    If it's already a valid uuid we do nothing.
    If it's a filename with UUID in it, update the UUID part with a new one.
    """
    name, extension = os.path.splitext(filename)
    try:
        uuid.UUID(name, version=4)
        return filename
    except ValueError:
        pass

    uuid4_pattern = (
        r'[0-9a-f]{8}'
        '-[0-9a-f]{4}'
        '-[1-5][0-9a-f]{3}'
        '-[89ab][0-9a-f]{3}'
        '-[0-9a-f]{12}'
    )
    uuid_exists = re.findall(uuid4_pattern, filename)
    if uuid_exists:
        old_uuids = '-'.join(uuid_exists)
        return filename.replace(old_uuids, str(uuid.uuid4()))

    return '{}-{!s}{}'.format(name, uuid.uuid4(), extension)


def secure_filename(s):
    """
    Secure the string to be a valid filename.

    Convert it to ASCII, convert spaces to hyphens, remove non alphanumericals
    and remove any leading or traling whitespace characters.
    """
    value = unicodedata.normalize('NFKC', s)
    # Remove all but(^) keep words(\w), whitespace chars(\s), dots(.),
    # hyphen(-). Remove leading/trailing whitespace and relative path info
    value = re.sub(r'[^\w\s\.-]', '', value).strip().lstrip('./')
    # Replace 1 or more(+) of hyphens(-) or whitespace chars(\s) with hyphen
    value = re.sub(r'[-\s]+', '-', value)
    value = make_filename_unique(value)
    return value
