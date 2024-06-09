import copy
import uuid

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser
from spynl.api.logistics.sales_orders import check_agent_access, generate_list_of_skus

USERNAME = 'user1'
USERNAME_2 = 'user2'
USERNAME_3 = 'user3'
USERNAME_ADMIN = 'admin'
PASSWORD = '0' * 10
USER_ID = ObjectId()
TENANT_ID = '1'
TENANT_ID_2 = '2'
CUST_ID = uuid.uuid4()


@pytest.fixture()
def sales_order():
    return copy.deepcopy(
        {
            'status': 'draft',
            'termsAndConditionsAccepted': True,
            'products': [
                {
                    'articleCode': 'A',
                    'price': 0.0,
                    'localizedPrice': 0.0,
                    'suggestedRetailPrice': 0.0,
                    'localizedSuggestedRetailPrice': 0.0,
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
                '_id': str(CUST_ID),
                'email': 'blah@blah.com',
            },
        }
    )


@pytest.fixture()
def sales_order_empty_product_qty():
    return copy.deepcopy(
        {
            'status': 'draft',
            'termsAndConditionsAccepted': True,
            'products': [
                {
                    'articleCode': 'A',
                    'price': 0.0,
                    'localizedPrice': 0.0,
                    'suggestedRetailPrice': 0.0,
                    'localizedSuggestedRetailPrice': 0.0,
                    'skus': [
                        {
                            'barcode': '123',
                            'color': 'Black',
                            'size': 'M',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                            'sizeIndex': 0,
                        }
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
                '_id': str(CUST_ID),
                'email': 'blah@blah.com',
            },
        }
    )


class Request:
    cached_user = {
        'roles': {'master': [], TENANT_ID: ['sales-user'], TENANT_ID_2: ['sales-admin']}
    }

    def __init__(self, tenant_id, user_id, master=False):
        self.requested_tenant_id = tenant_id
        if master:
            self.current_tenant_id = 'master'
        else:
            self.current_tenant_id = tenant_id
        self.authenticated_userid = user_id


def check_access_as_sales_user():
    """AgentId matches logged in user id."""
    req1 = Request(TENANT_ID, USER_ID)
    check_agent_access(USER_ID, req1)


def check_access_as_sales_user_bad():
    """AgentId does not match logged in user id."""
    req1 = Request(TENANT_ID, USER_ID)
    with pytest.raises(Exception):
        check_agent_access(ObjectId(), req1)


def check_access_as_sales_admin():
    """AgentId does not match logged in user id but has admin role on tenant."""
    req1 = Request(TENANT_ID_2, USER_ID)
    check_agent_access(ObjectId(), req1)


def check_access_as_master():
    """AgentId does not match logged in user id but is admin."""
    req1 = Request(TENANT_ID, USER_ID, master=True)
    check_agent_access(ObjectId(), req1)


@pytest.fixture(scope='module', autouse=True)
def unique_docnumber(spynl_data_db):
    spynl_data_db.sales_orders.pymongo_create_index(
        'docNumber', name='docnr_idx', unique=True
    )
    yield
    spynl_data_db.sales_orders.pymongo_drop_index('docnr_idx')


@pytest.fixture(autouse=True, scope='function')
def login(app, spynl_data_db, monkeypatch):
    monkeypatch.setattr('spynl.api.retail.resources.Sales.is_large_collection', False)

    db = spynl_data_db
    db.tenants.insert_one(
        {'_id': TENANT_ID, 'applications': ['sales', 'pos'], 'settings': {}}
    )
    db.wholesale_customers.insert_one({'_id': CUST_ID, 'tenant_id': [TENANT_ID]})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: ['sales-user', 'pos-device']},
        custom_id=USER_ID,
    )
    mkuser(
        db.pymongo_db,
        USERNAME_2,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-user'},
    )

    mkuser(
        db.pymongo_db,
        USERNAME_3,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-user'},
        settings={'sales': {'region': 'NL'}},
    )

    mkuser(
        db.pymongo_db,
        USERNAME_ADMIN,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'sales-admin'},
    )
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    yield
    app.get('/logout')


def test_save_sales_order_bad(app):
    app.post_json('/sales-orders/save', {'data': {}}, status=400)


def test_save_sales_order(spynl_data_db, app, sales_order):
    app.post_json('/sales-orders/save', {'data': sales_order}, status=200)
    assert spynl_data_db.sales_orders.count_documents() == 1


def test_save_complete_sales_order(spynl_data_db, app, sales_order):
    app.post_json(
        '/sales-orders/save',
        {'data': {**sales_order, 'status': 'complete'}},
        status=200,
    )
    assert spynl_data_db.events.count_documents() == 1


def test_save_sales_order_dup(app, sales_order):
    order = {**sales_order, 'docNumber': str(uuid.uuid4())}
    app.post_json('/sales-orders/save', {'data': order}, status=200)
    app.post_json('/sales-orders/save', {'data': order}, status=400)


def test_we_cannot_overwrite_docnumber(app, spynl_data_db, sales_order):
    order = {**sales_order, '_id': str(uuid.uuid4()), 'docNumber': str(uuid.uuid4())}
    order2 = {**order, 'docNumber': str(uuid.uuid4())}

    app.post_json('/sales-orders/save', {'data': order}, status=200)
    app.post_json('/sales-orders/save', {'data': order2}, status=200)

    resp = app.post_json(
        '/sales-orders/get', {'filter': {'_id': order['_id']}}, status=200
    ).json['data']
    assert len(resp) == 1 and resp[0]['docNumber'] == order['docNumber']


def test_get_sales_order(app, sales_order):
    orders = [{**sales_order, 'docNumber': str(uuid.uuid4())} for _ in range(5)]
    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    resp = app.post_json('/sales-orders/get')
    assert len(resp.json['data']) == 5


def test_get_sales_order_filter_by_docnumber(app, sales_order):
    orders = [{**sales_order, 'docNumber': str(uuid.uuid4())} for _ in range(5)]
    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    resp = app.post_json(
        '/sales-orders/get', {'filter': {'docNumber': orders[0]['docNumber']}}
    )
    assert len(resp.json['data']) == 1


def test_get_sales_order_filter_by_status(app, sales_order):
    orders = [
        {
            **sales_order,
            'docNumber': str(uuid.uuid4()),
            'status': 'complete' if i % 2 else 'draft',
        }
        for i in range(5)
    ]

    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    resp = app.post_json('/sales-orders/get', {'filter': {'status': 'complete'}})
    assert len(resp.json['data']) == 2


def test_get_sales_order_filter_as_admin(app, sales_order):
    orders = [{**sales_order, 'docNumber': str(uuid.uuid4())} for _ in range(5)]
    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))

    resp = app.post_json('/sales-orders/get', {'filter': {'agentId': str(USER_ID)}})
    assert len(resp.json['data']) == 5


def test_get_sales_order_as_other_user(app, sales_order):
    orders = [{**sales_order, 'docNumber': str(uuid.uuid4())} for _ in range(5)]
    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_2, PASSWORD))

    resp = app.post_json('/sales-orders/get')
    assert len(resp.json['data']) == 0


def test_get_sales_order_with_regions(app, sales_order):
    orders = [{**sales_order, 'docNumber': str(uuid.uuid4())} for _ in range(5)]
    regions = ['NL', 'NL2', 'DE1', 'DE2', 'GB']
    for r, o in zip(regions, orders):
        o['customer']['region'] = r
        app.post_json('/sales-orders/save', {'data': o})

    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_3, PASSWORD))

    resp = app.post_json('/sales-orders/get')
    assert len(resp.json['data']) == 2


def test_get_sales_order_as_other_user_not_allowed(app, sales_order):
    orders = [{**sales_order, 'docNumber': str(uuid.uuid4())} for _ in range(5)]
    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_2, PASSWORD))

    response = app.post_json(
        '/sales-orders/get', {'filter': {'agentId': str(USER_ID)}}, status=200
    )
    assert response.json == {'data': [], 'status': 'ok'}


def test_edit_sales_order(app, spynl_data_db, sales_order):
    sales_order = {'data': sales_order}
    resp = app.post_json('/sales-orders/save', sales_order)
    sales_order['data'].update(
        {
            'status': 'complete',
            'agentId': str(USER_ID),
            '_id': str(uuid.UUID(resp.json['data'][0])),
        }
    )
    app.post_json('/sales-orders/save', sales_order, status=200)
    assert spynl_data_db.sales_orders.count_documents({'status': 'draft'}) == 0
    assert spynl_data_db.sales_orders.count_documents({'status': 'complete'}) == 1


def test_edit_draft_sales_order(app, spynl_data_db, sales_order):
    sales_order = {'data': sales_order}
    sales_order['data']['status'] = 'draft'

    app.post_json('/sales-orders/save', sales_order, status=200)
    assert spynl_data_db.sales_orders.count_documents({'status': 'draft'}) == 1
    assert spynl_data_db.sales_orders.count_documents({'status': 'complete'}) == 0
    assert spynl_data_db.events.count_documents() == 0


def test_remove_sales_order(app, spynl_data_db, sales_order):
    sales_order = {'data': sales_order}
    resp = app.post_json('/sales-orders/save', sales_order)
    _id = resp.json['data'][0]
    sales_order['data'].update(
        {'status': 'complete', 'agentId': str(USER_ID), '_id': _id}
    )
    app.post_json('/sales-orders/remove', {'filter': {'_id': _id}}, status=200)
    assert (
        spynl_data_db.sales_orders.find_one({'_id': uuid.UUID(_id)})['active'] is False
    )


def test_edit_sales_order_not_allowed(app, sales_order):
    sales_order = {
        'data': {**sales_order, '_id': str(uuid.uuid4()), 'agentId': str(ObjectId())}
    }
    app.post_json('/sales-orders/save', sales_order, status=403)


def test_edit_sales_order_complete_not_allowed(app, sales_order):
    sales_order = {'data': {**sales_order, 'status': 'complete'}}
    resp = app.post_json('/sales-orders/save', sales_order)
    sales_order['data'].update(
        {'agentId': str(USER_ID), '_id': str(uuid.UUID(resp.json['data'][0]))}
    )
    app.post_json('/sales-orders/save', sales_order, status=400)


def test_split_sales_order(spynl_data_db, app, sales_order):
    spynl_data_db.tenants.update_one(
        {'_id': TENANT_ID},
        {'$set': {'counters.salesOrder': 40, 'counters.packingList': 31}},
    )
    counters = spynl_data_db.tenants.find_one(
        {'_id': TENANT_ID},
        {'counters.salesOrder': 1, 'counters.packingList': 1, '_id': 0},
    )['counters']

    sales_order['products'].append(
        {**copy.deepcopy(sales_order['products'][0]), 'directDelivery': 'on'}
    )
    sales_order['status'] = 'complete'
    sales_order = {'data': sales_order}
    resp = app.post_json('/sales-orders/save', sales_order)
    assert len(resp.json['data']) == 3
    assert spynl_data_db.sales_orders.count_documents() == 3
    events = list(spynl_data_db.events.find({}))
    assert len(events) == 2
    assert '/action__ordero/' in events[0]['fpquery']
    assert '/action__pakbon/' in events[1]['fpquery']

    counters_after = spynl_data_db.tenants.find_one(
        {'_id': TENANT_ID},
        {'counters.salesOrder': 1, 'counters.packingList': 1, '_id': 0},
    )['counters']
    assert counters_after['salesOrder'] - counters['salesOrder'] == 2
    assert counters_after['packingList'] - counters['packingList'] == 1


def test_split_sales_order_no_packing_list(spynl_data_db, app, sales_order):
    spynl_data_db.tenants.update_one(
        {'_id': TENANT_ID},
        {
            '$set': {
                'counters.salesOrder': 40,
                'counters.packingList': 31,
                'settings.sales.directDeliveryPackingList': False,
            }
        },
    )
    counters = spynl_data_db.tenants.find_one(
        {'_id': TENANT_ID},
        {'counters.salesOrder': 1, 'counters.packingList': 1, '_id': 0},
    )['counters']

    sales_order['products'].append(
        {**copy.deepcopy(sales_order['products'][0]), 'directDelivery': 'on'}
    )
    sales_order['status'] = 'complete'
    sales_order = {'data': sales_order}
    resp = app.post_json('/sales-orders/save', sales_order)
    assert len(resp.json['data']) == 2
    assert spynl_data_db.sales_orders.count_documents() == 2
    events = list(spynl_data_db.events.find({}))
    assert len(events) == 2
    assert '/action__ordero/' in events[0]['fpquery']
    assert '/action__order/' in events[1]['fpquery']

    counters_after = spynl_data_db.tenants.find_one(
        {'_id': TENANT_ID},
        {'counters.salesOrder': 1, 'counters.packingList': 1, '_id': 0},
    )['counters']
    assert counters_after['salesOrder'] - counters['salesOrder'] == 2


def test_get_sales_order_filter_by_text(app, sales_order):
    orders = [
        {
            **copy.deepcopy(sales_order),
            'docNumber': str(uuid.uuid4()),
            '_id': str(uuid.uuid4()),
        }
        for _ in range(5)
    ]

    orders[0]['products'][0]['collection'] = 'Summer'
    orders[1]['customer']['address']['city'] = 'Maarssen'
    orders[2]['customer']['deliveryAddress']['city'] = 'Breukelen'
    orders[3]['customer']['legalName'] = 'Kareem'
    orders[4]['customer']['name'] = 'Mohammed'

    for o in orders:
        app.post_json('/sales-orders/save', {'data': o})

    for i, t in enumerate(('mer', 'Rss', 'bRe', 'eem', 'moh')):
        resp = app.post_json('/sales-orders/get', {'filter': {'text': t}})
        assert (
            len(resp.json['data']) == 1
            and resp.json['data'][0]['_id'] == orders[i]['_id']
        )


def test_open_order(app, sales_order, spynl_data_db):
    sales_order = {'data': sales_order}
    sales_order['data'].update({'status': 'complete', 'agentId': str(USER_ID)})
    response = app.post_json('/sales-orders/save', sales_order, status=200)
    _id = response.json['data'][0]
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))

    app.post_json('/sales-orders/open-for-edit', {'_id': _id})
    order = spynl_data_db.sales_orders.find_one({'_id': uuid.UUID(_id)})
    assert order['status'] == 'complete-open-for-edit'
    assert order['audit_trail'][0]['opened']['username'] == USERNAME_ADMIN
    audit_doc = spynl_data_db.sales_order_audit_trail.find_one(
        {'_id': order['audit_trail'][0]['original_version_id']}
    )
    assert audit_doc['status'] == 'complete'


def test_open_order_order_does_not_exist(app, sales_order):
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))

    app.post_json('/sales-orders/open-for-edit', {'_id': str(uuid.uuid4())}, status=400)


def test_open_order_no_admin(app, sales_order):
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))

    app.post_json('/sales-orders/open-for-edit', status=403)


def test_edit_opened_order(app, sales_order, spynl_data_db):
    sales_order.update({'status': 'complete', 'agentId': str(USER_ID)})
    response = app.post_json('/sales-orders/save', {'data': sales_order}, status=200)
    _id = response.json['data'][0]
    sales_order['_id'] = _id
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))
    app.post_json('/sales-orders/open-for-edit', {'_id': _id})
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    response = app.post_json(
        '/sales-orders/save',
        {'data': sales_order, 'auditRemark': 'Editing now'},
        status=200,
    )
    sales_order = spynl_data_db.sales_orders.find_one({'_id': uuid.UUID(_id)})
    assert sales_order['audit_trail'][0]['remark'] == 'Editing now'
    assert sales_order['status'] == 'complete'


def test_edit_opened_remark_is_required(app, sales_order):
    sales_order.update({'status': 'complete', 'agentId': str(USER_ID)})
    response = app.post_json('/sales-orders/save', {'data': sales_order}, status=200)
    _id = response.json['data'][0]
    sales_order['_id'] = _id
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))
    app.post_json('/sales-orders/open-for-edit', {'_id': _id})
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    response = app.post_json('/sales-orders/save', {'data': sales_order}, status=400)


def test_edit_opened_counters_do_not_get_incremented(app, sales_order, spynl_data_db):
    # prepare order
    sales_order.update({'status': 'complete', 'agentId': str(USER_ID)})
    response = app.post_json('/sales-orders/save', {'data': sales_order}, status=200)
    _id = response.json['data'][0]
    sales_order['_id'] = _id
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))
    app.post_json('/sales-orders/open-for-edit', {'_id': _id})
    # reset counters
    spynl_data_db.tenants.update_one(
        {'_id': TENANT_ID},
        {'$set': {'counters.salesOrder': 40, 'counters.packingList': 31}},
    )
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    response = app.post_json(
        '/sales-orders/save',
        {'data': sales_order, 'auditRemark': 'Editing now'},
        status=200,
    )
    counters = spynl_data_db.tenants.find_one(
        {'_id': TENANT_ID},
        {'counters.salesOrder': 1, 'counters.packingList': 1, '_id': 0},
    )['counters']
    assert counters == {'packingList': 31, 'salesOrder': 40}


def test_cannot_overwrite_signature_fields(app, sales_order, spynl_data_db):
    sales_order.update({'status': 'complete', 'agentId': str(USER_ID)})
    response = app.post_json('/sales-orders/save', {'data': sales_order}, status=200)
    _id = response.json['data'][0]
    sales_order['_id'] = _id
    original_sales_order = copy.deepcopy(sales_order)
    sales_order['signature'] = 'data:image/png;base64,bbbb'
    sales_order['signedBy'] = 'bla'
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME_ADMIN, PASSWORD))
    app.post_json('/sales-orders/open-for-edit', {'_id': _id})
    app.get('/logout')
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    response = app.post_json(
        '/sales-orders/save',
        {'data': sales_order, 'auditRemark': 'Editing now'},
        status=200,
    )
    sales_order = spynl_data_db.sales_orders.find_one({'_id': uuid.UUID(_id)})
    assert sales_order['audit_trail'][0]['remark'] == 'Editing now'
    assert sales_order['signature'] == original_sales_order['signature']
    assert sales_order['signedBy'] == original_sales_order['signedBy']


def test_generate_sku_list():
    order = {
        'customer': {
            'address': {'address': '1', 'city': '1', 'country': '1', 'zipcode': '1'}
        },
        'products': [
            {
                'articleCode': 'A',
                'localizedPrice': 0.0,
                'localizedSuggestedRetailPrice': 0.0,
                'skus': [{'barcode': '123', 'qty': 12, 'size': 'M'}],
            },
            {
                'articleCode': 'B',
                'localizedPrice': 0.0,
                'localizedSuggestedRetailPrice': 0.0,
                'skus': [
                    {'barcode': '223', 'qty': 12, 'size': 'M'},
                    {'barcode': '224', 'qty': 10, 'size': 'L'},
                ],
            },
        ],
        'type': 'sales-order',
    }
    assert generate_list_of_skus(order) == [
        {
            'articleCode': 'A',
            'barcode': '123',
            'customer': {
                'address': {'address': '1', 'city': '1', 'country': '1', 'zipcode': '1'}
            },
            'localizedPrice': 0.0,
            'localizedSuggestedRetailPrice': 0.0,
            'qty': 12,
            'size': 'M',
            'type': 'sales-order',
        },
        {
            'articleCode': 'B',
            'barcode': '223',
            'customer': {
                'address': {'address': '1', 'city': '1', 'country': '1', 'zipcode': '1'}
            },
            'localizedPrice': 0.0,
            'localizedSuggestedRetailPrice': 0.0,
            'qty': 12,
            'size': 'M',
            'type': 'sales-order',
        },
        {
            'articleCode': 'B',
            'barcode': '224',
            'customer': {
                'address': {'address': '1', 'city': '1', 'country': '1', 'zipcode': '1'}
            },
            'localizedPrice': 0.0,
            'localizedSuggestedRetailPrice': 0.0,
            'qty': 10,
            'size': 'L',
            'type': 'sales-order',
        },
    ]


def test_download_excel(app, sales_order):
    _id = str(uuid.uuid4())
    order = {
        **copy.deepcopy(sales_order),
        'docNumber': str(uuid.uuid4()),
        '_id': _id,
    }
    order['customReference'] = 'custom!'
    order['products'].append(
        {
            'articleCode': 'B',
            'price': 0.0,
            'localizedPrice': 0.0,
            'suggestedRetailPrice': 0.0,
            'localizedSuggestedRetailPrice': 0.0,
            'skus': [
                {
                    'barcode': '223',
                    'color': 'Black',
                    'size': 'M',
                    'qty': 12,
                    'colorCodeSupplier': '',
                    'mainColorCode': '',
                    'sizeIndex': 0,
                },
                {
                    'barcode': '224',
                    'color': 'Black',
                    'size': 'L',
                    'qty': 10,
                    'colorCodeSupplier': '',
                    'mainColorCode': '',
                    'sizeIndex': 1,
                },
            ],
        }
    )
    app.post_json('/sales-orders/save', {'data': order})
    app.post_json('/sales-orders/download-excel', {'filter': {'_id': _id}}, status=200)


def test_sale_product_set_to_zero_if_not_exist(app, sales_order_empty_product_qty):
    response = app.post_json(
        '/sales-orders/save', {'data': sales_order_empty_product_qty}, status=200
    )
    assert response.json['status'] == 'ok'
    order = app.post_json(
        '/sales-orders/get', {'filter': {'_id': response.json['data'][0]}}, status=200
    ).json['data']
    # when the product qty is set to 0 the product is ignored on @postload
    # check ProductSchema::remove_zero_qty_items
    assert len(order[0]['products']) == 0
