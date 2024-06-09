import datetime
import json
import os

import pytest

from spynl_schemas import ReceivingSchema

from spynl.api.auth.testutils import login, mkuser

PATH = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def set_db(db):
    """
    add user and tenant and example receiving order
    """
    with open('{}/examples/example-receivings.json'.format(PATH)) as f:
        order = ReceivingSchema().load(json.loads(f.read()))
    # load does not load created:
    order['created'] = {
        'user': {'_id': '5c7fee844524c1ff7bcadc89', 'username': 'maddoxx.logistics'},
        'action': 'receivings/save',
        'date': datetime.datetime.utcnow(),
    }

    db.receivings.insert_one(order)
    db.warehouses.insert_one(
        {'_id': "91537_$AAAB", 'name': 'Amsterdam', 'tenant_id': ['a_tenant']}
    )
    db.tenants.insert_one(
        {
            '_id': 'a_tenant',
            'applications': ['logistics'],
            'settings': {
                'logoUrl': {'medium': 'file://{}/examples/square_logo.png'.format(PATH)}
            },
        }
    )

    mkuser(
        db,
        'receivings_user',
        'bla',
        ['a_tenant'],
        tenant_roles={'a_tenant': ['logistics-receivings_user']},
        language='nl-nl',
    )


def imageroot(tenant):
    return 'file://{}/examples/images/size0/'.format(PATH)


def test_receivings_pdf(app, set_db, inbox, monkeypatch):
    monkeypatch.setattr('spynl.services.pdf.endpoints.get_image_location', imageroot)
    login(app, 'receivings_user', 'bla')
    payload = {'_id': '1b2d47ed-cf4c-4d26-ba7b-f696e1932c09'}
    app.post_json('/receivings/download', payload, status=200)
