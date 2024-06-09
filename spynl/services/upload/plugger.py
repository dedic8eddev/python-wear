"""
plugger.py is used by spynl Plugins to say
which endpoints and resources it will use.
"""

import logging
import os

from pyramid.security import NO_PERMISSION_REQUIRED

from spynl.services.upload import Images, Logos
from spynl.services.upload.endpoints import add_image, add_logo, no_get, remove_logo
from spynl.services.upload.utils import check_s3_credentials


def includeme(config):
    """Add the functions add/get as endpoints."""
    log = logging.getLogger(__name__)

    if not os.environ.get('S3_UPLOAD_BUCKET'):
        log.warning('Environmental variable S3_UPLOAD_BUCKET is not declared!')
    else:
        result = check_s3_credentials()
        if result:
            log.warning(result)

    config.add_endpoint(add_image, 'add', context=Images, permission='add')
    config.add_endpoint(add_logo, 'add', context=Logos, permission='add')
    config.add_endpoint(remove_logo, 'remove', context=Logos, permission='add')
    config.add_endpoint(no_get, '/', context=Images, permission=NO_PERMISSION_REQUIRED)
    config.add_endpoint(no_get, '/', context=Logos, permission=NO_PERMISSION_REQUIRED)
