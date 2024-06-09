"""
Tests the procedure of sending PDF files to email addresses.
"""
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime

import pytest
from bson import ObjectId

from spynl_schemas import SaleSchema, TransitSchema

from spynl.api.auth.testutils import login, mkuser

from spynl.services.pdf.pdf import generate_eos_pdf_html, generate_receipt_html_css

PATH = os.path.dirname(os.path.abspath(__file__))
SALE_ID = ObjectId()
TRANSIT_ID = ObjectId()


@pytest.fixture(autouse=True)
def set_db(db, app):
    """Fill in the database with data."""
    db.tenants.insert_one(
        {
            '_id': '91537',
            'name': 'Maddoxx_Tenant',
            'applications': ['pos'],
            'settings': {
                'logoUrl': {
                    'medium': 'file://{}/examples/square_logo.png'.format(PATH)
                },
                'currency': 'EUR',
            },
        }
    )

    mkuser(
        db,
        'maddoxx.aveen',
        'aveen',
        ['91537'],
        tenant_roles={'91537': ['pos-device']},
        language='en-gb',
        settings={
            'email': {
                'sender': '<aveen@maddoxx.nl>',
                'replyTo': 'aveen@maddoxx.nl',
                'body': 'Here is your receipt!',
                'subject': 'Your receipt is here',
            }
        },
    )

    with open('{}/examples/sale.json'.format(PATH)) as f:
        sale = SaleSchema(context={'tenant_id': '91537'}).load(json.loads(f.read()))
    sale['_id'] = SALE_ID
    sale['created'] = {'date': datetime.utcnow()}
    db.transactions.insert_one(sale)

    with open('{}/examples/transit.json'.format(PATH)) as f:
        transit = TransitSchema(context={'tenant_id': '91537'}).load(
            json.loads(f.read())
        )
    transit['_id'] = TRANSIT_ID
    transit['created'] = {'date': datetime.utcnow()}
    db.transactions.insert_one(transit)

    db.warehouses.insert_one(
        {
            'name': 'Amsterdam',
            'wh': '50',
            'tenant_id': ['91537'],
            'addresses': [
                {
                    'city': 'Amsterdam',
                    'houseno': '',
                    'houseadd': '',
                    'street': 'Gelderlandplein 100',
                    'zipcode': '1082LB',
                    'phone': '020-6426306',
                    'primary': True,
                }
            ],
        }
    )
    db.warehouses.insert_one(
        {
            'name': 'Amstelveenn',
            'wh': '51',
            'tenant_id': ['91537'],
            'addresses': [
                {
                    'city': 'Àmştëlvéên',
                    'houseadd': '2',
                    'houseno': '123',
                    'phone': '0612345678',
                    'street': 'Ręmbràndthôf',
                    'zipcode': '1181ZL',
                    'primary': True,
                }
            ],
        }
    )
    db.eos.insert_one(EOS_MOCK_COMPLETED)
    db.eos.insert_one(EOS_MOCK_INCOMPLETE)
    login(app, 'maddoxx.aveen', 'aveen', tenant_id='91537')
    yield
    app.get('/logout')


def test_email_sales_receipt(app, inbox):
    """Check if the email receipt endpoint works as expected"""
    payload = {
        'email': 'bla@bla.com',
        '_id': str(SALE_ID),
        'footer': 'Bedankt en tot ziens.',
        'printExtendedReceipt': True,
    }
    app.post_json('/sales/email', payload, status=200)
    assert inbox[0].sender == 'noreply@uwkassabon.nl'
    assert inbox[0].subject == 'Your receipt is here'
    assert inbox[0].extra_headers == {
        'Reply-To': 'aveen@maddoxx.nl',
        'From': 'aveen maddoxx.nl <noreply@uwkassabon.nl>',
    }
    attachment = inbox[0].attachments[0]
    assert attachment.content_type == 'application/pdf'
    assert sys.getsizeof(attachment) > 0
    assert 'Here is your receipt!' in inbox[0].body.data


def test_download_sales_receipt(app):
    payload = {'_id': str(SALE_ID), 'footer': 'Bedankt en tot ziens.'}
    app.post_json('/sales/download', payload, status=200)


def test_email_transit_pdf(app, inbox):
    """Check if the email transit pdf endpoint works as expected"""
    payload = {'recipients': ['bla@bla.com'], '_id': str(TRANSIT_ID)}
    app.post_json('/transits/email', payload, status=200)
    # assert inbox[0].sender == 'noreply@uwkassabon.nl'
    # assert inbox[0].subject == 'Your receipt is here'
    # assert inbox[0].extra_headers == {
    #     'Reply-To': 'aveen@maddoxx.nl',
    #     'From': 'aveen maddoxx.nl <noreply@uwkassabon.nl>',
    # }
    attachment = inbox[0].attachments[0]
    assert attachment.content_type == 'application/pdf'
    assert sys.getsizeof(attachment) > 0
    # assert 'Here is your receipt!' in inbox[0].body.data


def test_are_fonts_installed():
    """This is not actually a unit test for spynl, but for the install process"""
    font_list = subprocess.check_output('fc-list').decode('utf-8').strip()
    assert '3 of 9 Barcode' in font_list


def test_sales_receipt_html(patch_jinja):
    class Request:
        pass

    with open('{}/examples/sale.json'.format(PATH)) as f:
        sale = SaleSchema(context={'tenant_id': '91537'}).load(json.loads(f.read()))
    sale['created'] = {'date': datetime.utcnow()}
    sale = SaleSchema().prepare_for_pdf(sale)
    html, css = generate_receipt_html_css(
        Request(),
        sale,
        {
            'footer': 'test footer',
            'printLoyaltyPoints': True,
            'printExtendedReceipt': False,
        },
        {},
        {},
    )
    assert 'test footer' in html
    assert '13/Drake T-shirt 16,5/-' not in html
    assert 'Loyalty-points' in html
    # test other options
    html, css = generate_receipt_html_css(
        Request(),
        sale,
        {
            'footer': 'test footer',
            'printLoyaltyPoints': False,
            'printExtendedReceipt': True,
        },
        {},
        {},
    )
    assert '13/Drake T-shirt 16,5/-' in html
    assert 'Loyalty-points' not in html


def test_eos_download(app, db):
    """Check if eos document is complete."""
    response = app.get(
        '/eos/download?_id=e2a62228-d69f-4677-a280-b5e19f6aa2fd', status=200
    )
    assert response.content_type == 'application/pdf'
    assert sys.getsizeof(response) > 0


def test_eos_missing_param(app):
    """Check if _id is missing from the parameters."""
    response = app.post_json('/eos/download', {}, status=400)
    assert response.json['message'] == 'Missing required parameter: _id'


def test_eos_not_found(app):
    """Check if eos document is not found."""
    response = app.post_json('/eos/download?_id=1234', {}, status=400)
    assert (
        response.json['message']
        == 'Sorry, the document you requested could not be found.'
    )


def test_eos_not_complete(app):
    """Check if eos document is complete."""
    response = app.post_json(
        '/eos/download?_id=a8289e40-b97b-4591-98c6-95e3abab3023', {}, status=400
    )
    assert (
        'The Closing of Day procedure should be completed first'
        in response.json['message']
    )


def test_eos_email(app, inbox):
    """Check eos pdf email endpoint."""
    payload = {
        '_id': 'e2a62228-d69f-4677-a280-b5e19f6aa2fd',
        'recipients': ['one@bla.com', 'two@bla.com'],
    }
    app.post_json('/eos/email', payload, status=200)
    for email in inbox:
        assert email.sender == 'noreply@uwkassabon.nl'
        assert (
            email.subject
            == 'Closing of Shift 8/6/19, 12:00 AM - 8/6/19, 11:59 PM maddoxx.aveen'
        )
        assert email.extra_headers == {
            'Reply-To': 'aveen@maddoxx.nl',
            'From': 'aveen maddoxx.nl <noreply@uwkassabon.nl>',
        }
        attachment = email.attachments[0]
        assert attachment.content_type == 'application/pdf'
        assert sys.getsizeof(attachment) > 0
    assert inbox[0].recipients == ['one@bla.com']
    assert inbox[1].recipients == ['two@bla.com']


def test_eos_pdf_html(patch_jinja):
    mock_eos = deepcopy(EOS_MOCK_COMPLETED)
    mock_eos['cashInDrawer'] = {
        item['value']: item['qty'] for item in mock_eos['cashInDrawer']
    }
    html = generate_eos_pdf_html(mock_eos, None, 'nl', 'EUR', 'Europe/Amsterdam')
    assert '06-08-2019 00:00' in html
    assert '06-08-2019 23:59' in html
    assert '>Some remarks' in html  # > makes sure there's no extra whitespace
    assert 'John The Cashier' in html
    assert '270,00' in html
    assert '-9,99' in html
    assert '5.414,10' in html


EOS_MOCK_COMPLETED = {
    '_id': 'e2a62228-d69f-4677-a280-b5e19f6aa2fd',
    'cashInDrawer': [
        {'qty': 0, 'value': 0.01},
        {'qty': 0, 'value': 0.02},
        {'qty': 0, 'value': 0.05},
        {'qty': 1, 'value': 0.1},
        {'qty': 0, 'value': 0.2},
        {'qty': 0, 'value': 0.5},
        {'qty': 4, 'value': 1},
        {'qty': 0, 'value': 2},
        {'qty': 0, 'value': 5},
        {'qty': 1, 'value': 10},
        {'qty': 0, 'value': 20},
        {'qty': 0, 'value': 50},
        {'qty': 4, 'value': 100},
        {'qty': 0, 'value': 200},
        {'qty': 10, 'value': 500},
    ],
    'cashier': {'id': '1234', 'fullname': 'John The Cashier', 'name': '11'},
    'cycleID': 'c024a558-95d6-4835-926e-1a5c2c253086',
    'deposit': 0,
    'device': {'id': 'YSJSU', 'name': 'maddoxx.aveen'},
    'difference': 9.99,
    'edited': True,
    'endBalance': 5414.1,
    'final': {
        'cash': -9.99,
        'net_cash': -9.99,
        'change': 0,
        'consignment': 270.00,
        'couponin': 0,
        'couponout': 0,
        'creditcard': 10.00,
        'creditreceipt': 4.00,
        'creditreceiptin': 0,
        'deposit': 0,
        'pin': 200,
        'storecredit': 0,
        'storecreditin': 0,
        'withdrawel': 0,
    },
    'openingBalance': 5414.1,
    'original': {
        'cash': -9.99,
        'change': 0,
        'consignment': 260.49,
        'couponin': 0,
        'couponout': 0,
        'creditcard': 10.00,
        'creditreceipt': 10.00,
        'creditreceiptin': 5.00,
        'deposit': 0,
        'pin': 200,
        'storecredit': 0,
        'storecreditin': 0,
        'withdrawel': 4.00,
    },
    'periodEnd': datetime.strptime('2019-08-06T21:59:00.000', '%Y-%m-%dT%H:%M:%S.%f'),
    'periodStart': datetime.strptime('2019-08-05T22:00:00.000', '%Y-%m-%dT%H:%M:%S.%f'),
    'remarks': 'Some remarks.\nThey contain a newline. Totals are wrong.',
    'shift': '1',
    'shop': {'id': '51', 'name': 'Amstelveen'},
    'status': 'completed',
    'totalCashInDrawer': 5414.1,
    'turnover': -9.99,
    'tenant_id': ['91537'],
    'vat': {'zeroAmount': 0, 'lowAmount': 2, 'highAmount': 200},
}

EOS_MOCK_INCOMPLETE = {
    '_id': 'a8289e40-b97b-4591-98c6-95e3abab3023',
    'status': 'generated',
    'tenant_id': ['91537'],
}
