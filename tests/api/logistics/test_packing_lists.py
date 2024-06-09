import copy
import datetime
import uuid

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser
from spynl.api.logistics.packing_lists import PackingListFilterSchema

TENANT_ID = '1'
PICKING_USER_ID = ObjectId()
PICKING_ADMIN_ID = ObjectId()
SALES_USER = 'sales'
PICKING_USER = 'picking'
PICKING_ADMIN = 'admin'
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
                'picking': {'packingListPrintq': 'mock'},
                'uploadDirectory': '',
            },
            'counters': {
                'packingList': 0,
            },
        }
    )
    db.tenants.insert_one({'_id': 'master'})
    mkuser(
        db.pymongo_db,
        'master_user',
        PASSWORD,
        ['master'],
        tenant_roles={'master': ['sw-servicedesk']},
    )
    mkuser(
        db.pymongo_db,
        SALES_USER,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: ['sales-user']},
        custom_id=ObjectId(),
    )

    mkuser(
        db.pymongo_db,
        PICKING_USER,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: ['picking-user']},
        custom_id=PICKING_USER_ID,
    )

    mkuser(
        db.pymongo_db,
        PICKING_ADMIN,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: ['picking-admin']},
        custom_id=PICKING_ADMIN_ID,
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


def test_save(app, sales_order, spynl_data_db):
    # generate the initial packing lists from a sales order
    app.get(f'/login?username={SALES_USER}&password={PASSWORD}')
    sales_order = {'data': sales_order}
    resp = app.post_json('/sales-orders/save', sales_order)
    _id = resp.json['type']['packingLists'][0]

    # set status to 'open'
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get', {'filter': {'_id': _id}})
    pl = resp.json['data'][0]
    pl['status'] = 'open'
    resp = app.post_json('/packing-lists/save', {'data': pl})

    # set status to 'picking'
    app.get(f'/login?username={PICKING_USER}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get')
    pl = resp.json['data'][0]
    pl['status'] = 'picking'
    app.post_json('/packing-lists/save', {'data': pl})

    # get updated packing list and complete picking
    resp = app.post_json('/packing-lists/get', {'filter': {'_id': _id}})
    pl = resp.json['data'][0]
    for p in pl['products']:
        for s in p['skus']:
            s['picked'] = s['qty']
    pl['status'] = 'complete'
    pl['numberOfParcels'] = 1
    resp = app.post_json('/packing-lists/save', {'data': pl})


def test_save_incomplete_and_move(app, sales_order, spynl_data_db):
    # generate the initial packing lists from a sales order
    app.get(f'/login?username={SALES_USER}&password={PASSWORD}')
    sales_order = {'data': sales_order}
    resp = app.post_json('/sales-orders/save', sales_order)
    _id = resp.json['type']['packingLists'][0]
    # set status to 'open'
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get', {'filter': {'_id': _id}})
    pl = resp.json['data'][0]
    pl['status'] = 'open'
    resp = app.post_json('/packing-lists/save', {'data': pl})

    # set status to 'picking'
    app.get(f'/login?username={PICKING_USER}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get')
    pl = resp.json['data'][0]
    pl['status'] = 'picking'
    app.post_json('/packing-lists/save', {'data': pl})

    # get updated packing list and complete picking
    resp = app.post_json('/packing-lists/get', {'filter': {'_id': _id}})
    pl = resp.json['data'][0]
    for p in pl['products']:
        for s in p['skus']:
            s['picked'] = s['qty'] // 2
    pl['status'] = 'complete'
    pl['numberOfParcels'] = 1
    resp = app.post_json('/packing-lists/save', {'data': pl})

    # set status to 'complete-and-move'
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get', {'filter': {'_id': _id}})
    pl = resp.json['data'][0]
    pl['status'] = 'complete-and-move'
    resp = app.post_json('/packing-lists/save', {'data': pl})
    pls = spynl_data_db.sales_orders.find(
        {'_id': {'$in': [uuid.UUID(i, version=4) for i in resp.json['data']]}}
    )
    assert len(set(p['orderNumber'] for p in pls)) == 2
    # there is one event already from the sales-orders save above:
    assert spynl_data_db.events.count_documents({}) == 2
    event = spynl_data_db.events.find_one({'modified.action': '/packing-lists/save'})
    assert 'ordernumber__PL%2D2/' in event['fpquery']


def test_get_different_roles(app, sales_order, spynl_data_db):
    now = datetime.datetime.utcnow()
    old = now - datetime.timedelta(minutes=10)
    payload = {
        'filter': {
            'reservationDateMin': str(now - datetime.timedelta(minutes=1)),
            'reservationDateMax': str(now + datetime.timedelta(minutes=1)),
        }
    }

    spynl_data_db.sales_orders.insert_many(
        [
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'pending',
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'open',
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'picking',
                'orderPicker': PICKING_USER_ID,
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'shipping',
                'orderPicker': PICKING_USER_ID,
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'cancelled',
                'orderPicker': PICKING_USER_ID,
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'shipping',
                'orderPicker': PICKING_USER_ID,
                'reservationDate': old,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'picking',
                'orderPicker': PICKING_ADMIN_ID,
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'incomplete',
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'complete',
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'ready-for-shipping',
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'shipping',
                'reservationDate': now,
            },
            {
                'active': True,
                'type': 'packing-list',
                'tenant_id': [TENANT_ID],
                'status': 'cancelled',
                'reservationDate': now,
            },
        ]
    )
    app.get(f'/login?username={PICKING_USER}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get', payload)
    assert len(resp.json['data']) == 6

    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get', payload)
    assert len(resp.json['data']) == 11

    app.get('/login?username=%s&password=%s' % ('master_user', PASSWORD))
    resp = app.post_json(f'/tenants/{TENANT_ID}/packing-lists/get')
    assert len(resp.json['data']) == 12


@pytest.mark.parametrize(
    'filter_',
    [
        {'warehouseId': ['1']},
        {'customerName': ['cust_one']},
        {'articleCode': ['1']},
        {'barcode': ['1']},
    ],
)
def test_packing_list_get_filter(filter_, db, app):
    db.sales_orders.insert_many(
        [
            {
                'tenant_id': [TENANT_ID],
                'type': 'packing-list',
                'warehouseId': '1',
                'active': True,
            },
            {
                'tenant_id': [TENANT_ID],
                'type': 'packing-list',
                'customer': {'name': 'cust_one'},
                'active': True,
            },
            {
                'tenant_id': [TENANT_ID],
                'type': 'packing-list',
                'products': [{'articleCode': '1'}],
                'active': True,
            },
            {
                'tenant_id': [TENANT_ID],
                'type': 'packing-list',
                'products': [{'skus': [{'barcode': '1'}]}],
                'active': True,
            },
        ]
    )

    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/get', {'filter': filter_})
    assert len(resp.json['data']) == 1


def test_reservation_date_filter(spynl_data_db, monkeypatch):
    min = datetime.datetime.utcnow()
    max = datetime.datetime.utcnow() + datetime.timedelta(minutes=1)
    before = datetime.datetime.utcnow() - datetime.timedelta(days=1)

    monkeypatch.setattr(PackingListFilterSchema, 'access_control', lambda a, b: b)
    spynl_data_db.pymongo_db.sales_orders.insert_many(
        [
            # found
            {
                'tenant_id': 1,
                '_id': 1,
                'reservationDate': min,
                'created': {'date': before},
            },
            {
                'tenant_id': 1,
                '_id': 2,
                'reservationDate': max,
                'created': {'date': before},
            },
            {
                'tenant_id': 1,
                '_id': 3,
                'reservationDate': None,
                'created': {'date': min},
            },
            {
                'tenant_id': 1,
                '_id': 4,
                'reservationDate': None,
                'created': {'date': max},
            },
            {'tenant_id': 1, '_id': 5, 'reservationDate': '', 'created': {'date': min}},
            {'tenant_id': 1, '_id': 6, 'reservationDate': '', 'created': {'date': max}},
            {'tenant_id': 1, '_id': 11, 'created': {'date': max}},
            # not found
            {
                'tenant_id': 1,
                '_id': 7,
                'reservationDate': before,
                'created': {'date': min},
            },
            {
                'tenant_id': 1,
                '_id': 8,
                'reservationDate': before,
                'created': {'date': max},
            },
            {
                'tenant_id': 1,
                '_id': 9,
                'reservationDate': before,
                'created': {'date': ''},
            },
            {
                'tenant_id': 1,
                '_id': 10,
                'reservationDate': before,
                'created': {'date': before},
            },
        ]
    )

    payload = {'reservationDateMin': str(min), 'reservationDateMax': str(max)}
    filter_ = PackingListFilterSchema(context={'tenant_id': 1}).load(payload)
    filter_.pop('active')
    filter_.pop('type')
    orders = list(spynl_data_db.sales_orders.find(filter_))
    assert {o['_id'] for o in orders} == {1, 2, 3, 4, 5, 6, 11}


def test_filter_endpoint(app, spynl_data_db):
    packing_lists = [
        {
            'active': True,
            'warehouseId': '6',
            'status': 'pending',
            'customer': {'name': 1},
            'products': [
                {'articleCode': 1, 'skus': [{'barcode': 1}, {'barcode': 2}]},
                {'articleCode': 2, 'skus': [{'barcode': 1}, {'barcode': 3}]},
            ],
        },
        {
            'active': True,
            'status': 'open',
            'customer': {'name': 2},
            'products': [{'articleCode': 3, 'skus': [{'barcode': 4}, {'barcode': 5}]}],
        },
        {
            'active': True,
            'status': 'picking',
            'orderPicker': PICKING_USER_ID,
            'customer': {'name': 3},
            'products': [{'articleCode': 4, 'skus': [{'barcode': 7}, {'barcode': 8}]}],
        },
        {
            'active': True,
            'status': 'picking',
            'orderPicker': PICKING_ADMIN_ID,
            'warehouseId': '5',
            'customer': {'name': 4},
            'products': [{'articleCode': 5, 'skus': [{'barcode': 10}, {'barcode': 9}]}],
        },
    ]

    warehouses = [
        {
            '_id': '5',
            'active': True,
            'addresses': [
                {
                    'street': '',
                    'country': '',
                    'zipcode': '',
                    'company': '',
                    'houseadd': '',
                    'primary': True,
                    'fax': '',
                    'phone': '',
                    'houseno': '',
                    'city': '',
                    'type': '',
                    'street2': '',
                }
            ],
            'created': {
                'user': None,
                'date': {'$date': '2017-12-01T11:24:54.531Z'},
                'action': 'csv2mongo',
            },
            'datafeed': '123454260483121723561',
            'ean': '',
            'email': 'info@softwear.nl',
            'fullname': '',
            'modified': {
                'user': None,
                'date': {'$date': '2017-12-01T11:24:56.449Z'},
                'action': 'csv2mongo',
            },
            'name': 'test-wh',
            'tenant_id': [TENANT_ID],
            'version': {'date': '20140710104913', 'v': 8},
            'wh': '5',
        },
        {
            '_id': '6',
            'active': True,
            'addresses': [
                {
                    'street': '',
                    'country': '',
                    'zipcode': '',
                    'company': '',
                    'houseadd': '',
                    'primary': True,
                    'fax': '',
                    'phone': '',
                    'houseno': '',
                    'city': '',
                    'type': '',
                    'street2': '',
                }
            ],
            'created': {
                'user': None,
                'date': {'$date': '2017-12-01T11:24:54.531Z'},
                'action': 'csv2mongo',
            },
            'datafeed': '123454260483121723561',
            'ean': '',
            'email': 'info@softwear.nl',
            'fullname': '',
            'modified': {
                'user': None,
                'date': {'$date': '2017-12-01T11:24:56.449Z'},
                'action': 'csv2mongo',
            },
            'name': 'test-wh-2',
            'tenant_id': [TENANT_ID],
            'version': {'date': '20140710104913', 'v': 8},
            'wh': '6',
        },
    ]
    for p in packing_lists:
        p.update({'tenant_id': TENANT_ID, 'type': 'packing-list'})
    spynl_data_db.sales_orders.insert_many(packing_lists)
    spynl_data_db.warehouses.insert_many(warehouses)
    app.get(f'/login?username={PICKING_USER}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/filter')
    assert resp.json['data']['filter'] == {
        'articleCode': [3],
        'barcode': [4, 5],
        'customerName': [2],
        'status': ['open'],
        'warehouseName': [],
    }

    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    resp = app.post_json('/packing-lists/filter')
    assert resp.json['data']['filter'] == {
        'articleCode': [1, 2, 3, 4, 5],
        'barcode': [1, 2, 3, 4, 5, 7, 8, 9, 10],
        'customerName': [1, 2, 3, 4],
        'status': ['open', 'pending', 'picking'],
        'warehouseName': ['test-wh', 'test-wh-2'],
    }

    resp = app.post_json(
        '/packing-lists/get', {'filter': {'warehouseName': ['test-wh-2']}}
    )

    assert resp.json['data'] == [
        {
            'active': True,
            'warehouseId': '6',
            'status': 'pending',
            'customer': {'name': 1},
            'products': [
                {'articleCode': 1, 'skus': [{'barcode': 1}, {'barcode': 2}]},
                {'articleCode': 2, 'skus': [{'barcode': 1}, {'barcode': 3}]},
            ],
            'tenant_id': '1',
            'type': 'packing-list',
            # ignore fields
            '_id': resp.json['data'][0]['_id'],
            'created': resp.json['data'][0]['created'],
            'modified': resp.json['data'][0]['modified'],
        }
    ]


def test_shipping_endpoint(mock_shipping_external_functions, sales_order, db, app):
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


def test_shipping_labels(mock_shipping_external_functions, db, app):
    _id = uuid.uuid4()
    db.sales_orders.insert_one(
        {
            '_id': _id,
            'status': 'shipping',
            'numberOfParcels': 2,
            'type': 'packing-list',
            'tenant_id': [TENANT_ID],
            'products': [],
            'parcels': [
                {'id': 123456, 'tracking_number': 'ab123'},
                {'id': 123457, 'tracking_number': 'ab124'},
            ],
        }
    )
    app.get(f'/login?username={PICKING_USER}&password={PASSWORD}')
    app.post_json(
        '/packing-lists/shipping-labels', {'filter': {'_id': str(_id)}}, status=200
    )


def test_cancel(app, db):
    events_count = db.events.count_documents({})
    _id = uuid.uuid4()
    db.sales_orders.insert_one(generate_packing_list(_id))
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    app.post_json('/packing-lists/cancel', {'_id': str(_id)}, status=200)
    packing_list = db.sales_orders.find_one({'_id': _id})
    assert packing_list['status'] == 'cancelled'
    assert db.events.count_documents({}) == events_count + 1


def test_update_packing_list_status_history_check(app, db):
    id = uuid.uuid4()
    packing_list = generate_packing_list_2(id)
    _id = str(id)
    packing_list['status'] = 'open'
    packing_list['numberOfParcels'] = 1
    packing_list['orderPicker'] = PICKING_ADMIN_ID
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    db.sales_orders.insert_one(packing_list)
    app.post_json(
        '/packing-lists/set-status',
        {'status': 'open', '_id': _id},
        status=200,
    )
    app.post_json(
        '/packing-lists/set-status',
        {'status': 'open', '_id': _id},
        status=200,
    )
    app.post_json(
        '/packing-lists/set-status',
        {'status': 'picking', '_id': _id},
        status=200,
    )
    app.post_json(
        '/packing-lists/set-status',
        {'status': 'complete', '_id': _id},
        status=200,
    )
    resp = app.post_json(
        '/packing-lists/set-status',
        {'status': 'complete-and-move', '_id': _id},
        status=200,
    )
    packing_list = resp.json["data"]
    assert len(packing_list['status_history']) == 4


def test_update_packing_list_status_change_picking_twice(app, db):
    id = uuid.uuid4()
    packing_list = generate_packing_list_2(id)
    _id = str(id)
    packing_list['status'] = 'open'
    packing_list['numberOfParcels'] = 1
    packing_list['orderPicker'] = PICKING_ADMIN_ID
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    db.sales_orders.insert_one(packing_list)
    app.post_json(
        '/packing-lists/set-status',
        {'status': 'open', '_id': _id},
        status=200,
    )
    app.post_json(
        '/packing-lists/set-status',
        {'status': 'picking', '_id': _id},
        status=200,
    )
    resp = app.post_json(
        '/packing-lists/set-status',
        {'status': 'picking', '_id': _id},
        status=400,
    )
    assert resp.json['message'] == 'Illegal status update'


def test_cancel_document_does_not_exist(app, db):
    _id = uuid.uuid4()
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    app.post_json('/packing-lists/cancel', {'_id': str(_id)}, status=400)


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


def test_download_excel(app):
    _id = str(uuid.uuid4())
    pl = generate_packing_list_2(_id)
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    app.post_json('/packing-lists/save', {'data': pl})
    app.post_json('/packing-lists/download-excel', {'_id': _id}, status=200)


def test_download_csv(app):
    _id = str(uuid.uuid4())
    pl = generate_packing_list_2(_id)
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    app.post_json('/packing-lists/save', {'data': pl})
    app.post_json('/packing-lists/download-csv', {'_id': _id}, status=200)


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


def generate_packing_list_2(_id):
    return copy.deepcopy(
        {
            '_id': _id,
            'active': True,
            'reservationDate': str(datetime.datetime.utcnow().isoformat()),
            'fixDate': str(datetime.datetime.utcnow().isoformat()),
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
            'status': 'open',
            'tenant_id': ['1'],
            'type': 'packing-list',
        }
    )


def generate_packing_list_status_incomplete(_id):
    return {
        'status': 'incomplete',
        'warehouseId': '630f97c5967efd182d06f2c1',
        'termsAndConditionsAccepted': True,
        'numberOfParcels': 1,
        'orderNumber': 'PLT-1',
        'products': [
            {
                'articleCode': 'C',
                'price': 15,
                'localizedPrice': 10,
                'suggestedRetailPrice': 12,
                'localizedSuggestedRetailPrice': 14,
                'skus': [
                    {
                        'barcode': '123',
                        'color': 'Black',
                        'size': 'M',
                        'qty': 12,
                        'colorCodeSupplier': '',
                        'mainColorCode': 'black',
                        'sizeIndex': 0,
                    },
                    {
                        'barcode': '124',
                        'color': 'Black',
                        'size': 'S',
                        'qty': 10,
                        'colorCodeSupplier': '',
                        'mainColorCode': 'black',
                        'sizeIndex': 1,
                    },
                    {
                        'barcode': '125',
                        'color': 'Black',
                        'size': 'L',
                        'qty': 14,
                        'colorCodeSupplier': '',
                        'mainColorCode': 'black',
                        'sizeIndex': 2,
                    },
                    {
                        'barcode': '126',
                        'color': 'Red',
                        'size': 'L',
                        'qty': 22,
                        'colorCodeSupplier': '',
                        'mainColorCode': 'red',
                        'sizeIndex': 2,
                    },
                    {
                        'barcode': '127',
                        'color': 'Red',
                        'size': 'M',
                        'qty': 22,
                        'colorCodeSupplier': '',
                        'mainColorCode': 'red',
                        'sizeIndex': 0,
                    },
                ],
            }
        ],
        'signature': 'data:image/png;base64,aaaa',
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
            'id': '1',
            '_id': 'ce167fdc-0a2c-5faf-bba7-db2200a441bd',
            'email': 'blah@blah.com',
        },
        'tenant_id': ['1'],
        '_id': _id,
    }


def test_packing_list_change_status_to_complete_and_move(app, spynl_data_db):
    _id = str(uuid.uuid4())
    payload = generate_packing_list_status_incomplete(_id)
    app.get(f'/login?username={PICKING_ADMIN}&password={PASSWORD}')
    app.post_json('/packing-lists/save', {'data': payload})
    # get the current counters
    counters = spynl_data_db.tenants.find_one(
        {'_id': '1'}, {'counters.packingList': 1, '_id': 0}
    ).get('counters', {'packingList': 0})
    new_order_number = f"PL-{counters['packingList'] + 1}"
    app.post_json(
        '/packing-lists/set-status', {'_id': _id, 'status': 'complete-and-move'}
    )
    # get latest sales_order from db
    data = spynl_data_db.sales_orders.find({}).sort([('created', -1)]).limit(1)
    data_old = spynl_data_db.sales_orders.find({'_id': uuid.UUID(_id)})

    assert data[0]['status'] == 'pending'
    assert str(data[0]['_id']) != _id
    assert data_old[0]['status'] == 'ready-for-shipping'
    assert data_old[0]['orderNumber'] != data[0]['orderNumber']
    assert data[0]['orderNumber'] == new_order_number
