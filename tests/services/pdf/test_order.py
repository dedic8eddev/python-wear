import json
import os
import sys
import uuid
from copy import deepcopy
from datetime import datetime

import pytest
from bson.objectid import ObjectId

from spynl_schemas import PackingListSchema, SalesOrderSchema

from spynl.api.auth.testutils import login, mkuser

PATH = os.path.dirname(os.path.abspath(__file__))
ORDER_TERMS_ID = uuid.uuid4()
ORDER_WITHOUT_LANGUAGE_ID = uuid.uuid4()
PACKING_LIST_ID = uuid.uuid4()


@pytest.fixture
def set_db(db):
    """
    add user and tenant and example sales order
    """
    with open('{}/examples/example-sales-order-model.json'.format(PATH)) as f:
        base_order = json.loads(f.read())
    order = SalesOrderSchema(context={'db': db}).load(deepcopy(base_order))[0]
    db.sales_orders.insert_one(order)

    order['_id'] = ORDER_WITHOUT_LANGUAGE_ID
    order['customer']['language'] = ''
    db.sales_orders.insert_one(order)

    order_terms = order['orderTerms']
    order_terms['_id'] = ORDER_TERMS_ID
    order_terms['tenant_id'] = ['wholesale_tenant']

    db.order_terms.insert_one(order_terms)

    packing_list = PackingListSchema(context={'db': db, 'user_id': 'user A'}).load(
        {**base_order, 'numberOfParcels': 1}
    )[0]
    packing_list['_id'] = PACKING_LIST_ID
    packing_list['status'] = 'pending'
    packing_list['modified'] = {'date': datetime.utcnow()}
    packing_list['products'][0]['customsProperties'] = [
        {'name': 'show', 'value': 'This should be there'},
        {'name': 'also_show', 'value': 'This should also be there'},
    ]
    packing_list['products'].append(packing_list['products'][0])
    # For when we want to add the sales orders to the packing list:
    # packing_list['products'][0]['skus'][0]['salesOrder'] = ORDER_WITHOUT_LANGUAGE_ID
    # packing_list['products'][0]['skus'][1]['salesOrder'] = ORDER_WITHOUT_LANGUAGE_ID
    # packing_list['products'][1]['skus'][1]['salesOrder'] = ORDER_WITHOUT_LANGUAGE_ID
    # packing_list['products'][1]['skus'][2]['salesOrder'] = uuid.UUID(
    #     '1b2d47ed-cf4c-4d26-ba7b-f696e1932c09'
    # )

    db.sales_orders.insert_one(packing_list)

    template_settings = {
        'agentName': True,
        'discountLine1': True,
        'discountLine2': True,
        'nettTerm': True,
        'remarks': True,
        'shippingCarrier': True,
        'fixDate': True,
        'reservationDate': True,
        'productPhoto': True,
        'brand': True,
        'collection': True,
        'articleGroup': True,
        'suggestedRetailPrice': True,
        'colorDescription': True,
        'propertiesOnOrder': ['show', 'Type'],
    }

    db.tenants.insert_one(
        {
            '_id': 'wholesale_tenant',
            'applications': ['sales', 'picking'],
            'settings': {
                'sales': {
                    'orderTemplate': template_settings,
                    'imageRoot': 'file://{}/examples/'.format(PATH),
                    'confirmationEmail': [
                        'confirm@confirm.com',
                        'confirm2@confirm.com',
                    ],
                }
            },
        }
    )

    mkuser(
        db,
        'agent_user',
        'bla',
        ['wholesale_tenant'],
        tenant_roles={'wholesale_tenant': ['sales-user']},
        custom_id=ObjectId('59f30cecca03842293621bfb'),
        settings={'email': {'sender': 'AgentA'}},
    )

    mkuser(
        db,
        'picking_user',
        'bla',
        ['wholesale_tenant'],
        tenant_roles={'wholesale_tenant': ['picking-admin']},
    )


def test_email_sales_order_pdf(app, set_db, inbox):
    """
    Generating the pdf takes a bit of time, so we do all the asserts in one test

    It might be good to make a more bare bones example for quicker tests.
    """
    login(app, 'agent_user', 'bla')
    payload = {'_id': '1b2d47ed-cf4c-4d26-ba7b-f696e1932c09'}
    response = app.post_json('/sales-orders/email', payload, status=200)
    assert response.json['data']['recipients'] == [
        'confirm@confirm.com',
        'confirm2@confirm.com',
        'aadje@softwear.nl',
        'agent_user@blah.com',
    ]
    assert inbox[0].extra_headers == {'From': 'AgentA <info@spynl.com>'}
    attachment = inbox[0].attachments[0]
    assert attachment.content_type == 'application/pdf'
    assert attachment.filename == '123456.pdf'
    assert sys.getsizeof(attachment) > 0
    attachment = inbox[0].attachments[1]
    assert attachment.content_type == 'application/pdf'
    assert attachment.filename == '123456_tos.pdf'
    assert sys.getsizeof(attachment) > 0
    assert inbox[0].recipients == [
        'confirm@confirm.com',
        'confirm2@confirm.com',
        'aadje@softwear.nl',
        'agent_user@blah.com',
    ]


def test_email_sales_order_pdf_bcc_recipients(app, set_db, inbox):
    """
    Check that none of the standard recipients get added, and that the specified
    recipients get added as bcc.
    """
    login(app, 'agent_user', 'bla')
    payload = {
        '_id': '1b2d47ed-cf4c-4d26-ba7b-f696e1932c09',
        'recipients': ['bcc@bcc.com', 'bcc2@bcc.com'],
    }
    response = app.post_json('/sales-orders/email', payload, status=200)
    assert response.json['data']['recipients'] == [
        'agent_user@blah.com',
        'bcc@bcc.com',
        'bcc2@bcc.com',
    ]
    assert inbox[0].extra_headers == {'From': 'AgentA <info@spynl.com>'}
    attachment = inbox[0].attachments[0]
    assert attachment.content_type == 'application/pdf'
    assert attachment.filename == '123456.pdf'
    assert sys.getsizeof(attachment) > 0
    assert inbox[0].recipients == ['agent_user@blah.com']
    assert inbox[0].bcc == ['bcc@bcc.com', 'bcc2@bcc.com']


def test_email_sales_order_customer_without_language(app, set_db, db):
    """this was a bug"""
    login(app, 'agent_user', 'bla')
    payload = {'_id': str(ORDER_WITHOUT_LANGUAGE_ID)}
    app.post_json('/sales-orders/email', payload, status=200)


def test_download_sales_order_pdf(app, set_db):
    login(app, 'agent_user', 'bla')
    payload = {'_id': '1b2d47ed-cf4c-4d26-ba7b-f696e1932c09'}
    app.post_json('/sales-orders/download', payload, status=200)


def test_preview_sales_order_pdf(app, set_db):
    login(app, 'agent_user', 'bla')
    payload = {'filter': {'orderTermsId': str(ORDER_TERMS_ID)}}
    app.post_json('/sales-orders/preview', payload, status=200)


def test_preview_sales_order_pdf_invalid_uuid(app, set_db):
    login(app, 'agent_user', 'bla')
    payload = {'filter': {'orderTermsId': '3A123'}}
    app.post_json('/sales-orders/preview', payload, status=400)


def test_download_packing_list_pdf(app, set_db):
    login(app, 'picking_user', 'bla')
    payload = {'_id': str(PACKING_LIST_ID)}
    app.post_json('/packing-lists/download', payload, status=200)
