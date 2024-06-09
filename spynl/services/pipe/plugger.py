"""
plugger.py is used by spynl Plugins to say
which endpoints and resources it will use.
"""

from pyramid.authorization import Authenticated
from pyramid.security import NO_PERMISSION_REQUIRED

from spynl.services.pipe import Foxpro
from spynl.services.pipe.contact import contact_us
from spynl.services.pipe.endpoints import pay_nl, url_shortener
from spynl.services.pipe.foxpro import get as fp_get


def includeme(config):
    """Add the functions fp_get/vw_get as endpoints."""
    config.add_endpoint(fp_get, '/', context=Foxpro, permission='read')

    config.add_endpoint(contact_us, 'contact-us', permission=NO_PERMISSION_REQUIRED)

    config.add_endpoint(url_shortener, 'url-shortener', permission=Authenticated)

    config.add_endpoint(pay_nl, 'pay-nl', permission=Authenticated)
