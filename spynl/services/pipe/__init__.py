"""
This module defines how piping to third-party endpoints is done.
"""

from pyramid.authorization import DENY_ALL, Allow

from spynl.main.routing import Resource


class Foxpro(Resource):
    """Resource for Foxpro endpoints"""

    paths = ['legacy-api']

    __acl__ = [
        (Allow, 'role:pos-device', 'read'),
        (Allow, 'role:sales-user', 'read'),
        (Allow, 'role:sales-admin', 'read'),
        (Allow, 'role:polytex-user', 'read'),
        (Allow, 'role:logistics-receivings_user', 'read'),
        (Allow, 'role:owner', 'read'),
        DENY_ALL,
    ]
