import copy
import uuid

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

TENANT_ID = '1'
PICKING_USER_ID = ObjectId()
PICKING_USER = 'picking'
PASSWORD = '00000000'
CUST_ID = uuid.uuid4()


@pytest.fixture(autouse=True, scope='function')
def users(app, spynl_data_db, monkeypatch):
    db = spynl_data_db
    db.tenants.insert_one(
        {
            '_id': TENANT_ID,
            'applications': ['sales', 'picking'],
            'settings': {
                'sendcloudApiToken': '123',
                'sendcloudApiSecret': '123',
                'uploadDirectory': '',
            },
        }
    )
    settings = {
        'picking': {'pickingListPrinterId': 'mock', 'shippingLabelPrinterId': 'mock'},
    }
    db.tenants.insert_one({'_id': 'master'})

    mkuser(
        db.pymongo_db,
        PICKING_USER,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: ['picking-user']},
        custom_id=PICKING_USER_ID,
        settings=settings,
    )
    db.wholesale_customers.insert_one({'_id': CUST_ID, 'tenant_id': [TENANT_ID]})
    yield db


@pytest.fixture
def mock_shipping_external_functions(monkeypatch):
    def mock_labels(*args):
        class DummyResponse:
            pass

        response = DummyResponse()
        response.content = b''
        return response

    def mock_function(*args, **kwargs):
        return

    def mock_parcels(*args):
        parcels = [
            {'id': 123456, 'tracking_number': 'ab123', 'extra': 'extra'},
            {'id': 123457, 'tracking_number': 'ab124'},
        ]
        return parcels

    monkeypatch.setattr(
        'spynl.api.logistics.packing_lists.get_sendcloud_labels', mock_labels
    )
    monkeypatch.setattr('spynl.api.logistics.packing_lists.upload_pdf', mock_function)
    monkeypatch.setattr(
        'spynl.api.logistics.packing_lists.send_document_to_printq',
        mock_function,
    )
    monkeypatch.setattr(
        'spynl.api.logistics.packing_lists.register_sendcloud_parcels', mock_parcels
    )


def test_user_printer_settings_endpoint(
    mock_shipping_external_functions, sales_order, db, app
):
    events_count = db.events.count_documents({})

    _id = uuid.uuid4()
    order = {
        key: value
        for key, value in sales_order.items()
        if key in ['products', 'customer']
    }
    db.sales_orders.insert_one(
        {
            '_id': _id,
            'status': 'ready-for-shipping',
            'numberOfParcels': 2,
            'type': 'packing-list',
            'active': True,
            'tenant_id': [TENANT_ID],
            **order,
        }
    )
    app.get(f'/login?username={PICKING_USER}&password={PASSWORD}')
    app.post_json(
        '/packing-lists/ship',
        {'filter': {'_id': str(_id)}, 'printDocuments': True},
        status=200,
    )
    packing_list = db.sales_orders.find_one({'_id': _id})
    assert packing_list['parcels'] == [
        {'id': 123456, 'tracking_number': 'ab123'},
        {'id': 123457, 'tracking_number': 'ab124'},
    ]
    assert packing_list['status'] == 'shipping'
    assert db.events.count_documents({}) == events_count + 1


@pytest.fixture()
def sales_order():
    return copy.deepcopy(
        {
            'status': 'complete',
            'termsAndConditionsAccepted': True,
            'products': [
                {
                    'articleCode': 'A',
                    'price': 0.0,
                    'localizedPrice': 0.0,
                    'suggestedRetailPrice': 0.0,
                    'localizedSuggestedRetailPrice': 0.0,
                    'directDelivery': 'on',
                    'skus': [
                        {
                            'barcode': '123',
                            'color': 'Black',
                            'size': 'M',
                            'qty': 12,
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                            'sizeIndex': 0,
                        }
                    ],
                }
            ],
            'signature': 'data:image/png;base64,aaaa',
            'numberOfParcels': 1,
            'signedBy': 'kareem',
            'customer': {
                'address': {
                    'address': '1',
                    'zipcode': '1',
                    'city': '1',
                    'country': '1',
                    'telephone': '123',
                },
                'deliveryAddress': {
                    'address': '1',
                    'zipcode': '1',
                    'city': '1',
                    'country': '1',
                    'telephone': '123',
                },
                'legalName': 'name',
                'vatNumber': '1',
                'cocNumber': '1',
                'bankNumber': '1',
                'clientNumber': '1',
                'currency': '1',
                '_id': str(CUST_ID),
                'email': 'blah@blah.com',
            },
        }
    )


def generate_packing_list(_id):
    return copy.deepcopy(
        {
            '_id': _id,
            'active': True,
            'customer': {
                '_id': 'f8aaaddf-b8a8-4c25-96b2-0b5e5e5aa6d0',
                'address': {
                    'address': '1',
                    'city': '1',
                    'country': '1',
                    'telephone': '123',
                    'zipcode': '1',
                },
                'bankNumber': '1',
                'clientNumber': '1',
                'cocNumber': '1',
                'currency': {
                    'label': '1',
                    'saleFactor': 1.0,
                    'uuid': '362841a7-66d5-49d2-b8bd-a6f00e8dc320',
                },
                'deliveryAddress': {
                    'address': '1',
                    'city': '1',
                    'country': '1',
                    'telephone': '123',
                    'zipcode': '1',
                },
                'email': 'blah@blah.com',
                'legalName': 'name',
                'vatNumber': '1',
            },
            'docNumber': 'e2dbf68b-0909-4175-b10a-c278962bb46f',
            'orderNumber': 'PL-1',
            'products': [
                {
                    'articleCode': 'A',
                    'deliveryPeriod': '',
                    'localizedPrice': 0.0,
                    'localizedSuggestedRetailPrice': 0.0,
                    'price': 0.0,
                    'skus': [
                        {
                            'barcode': '123',
                            'color': 'Black',
                            'colorCodeSupplier': '',
                            'link': ['d77504ac-7b05-4ae4-8924-19115a4cf083'],
                            'mainColorCode': '',
                            'picked': 4,
                            'qty': 12,
                            'size': 'M',
                            'sizeIndex': 0,
                        }
                    ],
                    'suggestedRetailPrice': 0.0,
                }
            ],
            'status': 'picking',
            'status_history': [
                {
                    'date': '2021-08-24T11:16:25+0200',
                    'status': 'picking',
                    'user': '6124b81e391c92fab47c3911',
                },
                {
                    'date': '2021-08-24T10:29:53+0200',
                    'status': 'open',
                    'user': '6124adff1d53f5ea3c8669e9',
                },
                {
                    'date': '2021-08-24T10:29:53+0200',
                    'status': 'open',
                    'user': '6124ae011d53f5ea3c8669f0',
                },
            ],
            'tenant_id': ['1'],
            'type': 'packing-list',
        }
    )
