import json
import os
import uuid
from copy import deepcopy

import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser
from spynl.api.retail.sales import SaleFilterSchema

TENANT_ID = '1'
USERNAME = 'test_sale_user'
USERNAME2 = 'master_user'
PASSWORD = '00000000'
USER_ID = ObjectId()
TOKEN = uuid.uuid4()
EXAMPLE_SALES_DIR = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), 'example_sales'
)
CUSTOMER_ID = uuid.uuid4()

with open(os.path.join(EXAMPLE_SALES_DIR, 'sale1.json')) as f:
    SALE = json.loads(f.read())

with open(os.path.join(EXAMPLE_SALES_DIR, 'sale2.json')) as f:
    SALE_WITHOUT_NR_RECEIPTNR = json.loads(f.read())

with open(os.path.join(EXAMPLE_SALES_DIR, 'sale3.json')) as f:
    SALE_REMARK_COMPLEX = json.loads(f.read())

with open(os.path.join(EXAMPLE_SALES_DIR, 'badsale1.json')) as f:
    BADSALE = json.loads(f.read())

with open(os.path.join(EXAMPLE_SALES_DIR, 'withdrawel.json')) as f:
    WITHDRAWEL = json.loads(f.read())

with open(os.path.join(EXAMPLE_SALES_DIR, 'consignment.json')) as f:
    CONSIGNMENT = json.loads(f.read())


@pytest.fixture(autouse=True, scope='function')
def database_setup(app, spynl_data_db, monkeypatch):
    monkeypatch.setattr('spynl.api.retail.resources.Sales.is_large_collection', False)
    monkeypatch.setattr(
        'spynl.api.retail.resources.WebshopSales.is_large_collection', False
    )
    monkeypatch.setattr(
        'spynl.api.retail.resources.Consignments.is_large_collection', False
    )

    db = spynl_data_db
    db.tenants.insert_one(
        {'_id': TENANT_ID, 'applications': ['pos'], 'settings': {}, 'owners': [USER_ID]}
    )
    db.tenants.insert_one({'_id': 'master', 'applications': [], 'settings': {}})
    db.customers.insert_one({'_id': CUSTOMER_ID, 'tenant_id': [TENANT_ID]})
    # customer for consignments:
    db.customers.insert_one({'_id': '1234', 'tenant_id': [TENANT_ID]})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'pos-device'},
        custom_id=USER_ID,
    )
    db.tokens.insert_one(
        {
            'roles': ['token-webshop-admin'],
            'token': TOKEN,
            'user_id': USER_ID,
            'tenant_id': TENANT_ID,
            'revoked': False,
        }
    )
    mkuser(
        db.pymongo_db,
        USERNAME2,
        PASSWORD,
        ['master'],
        tenant_roles={'master': 'sw-admin'},
    )
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    yield db
    app.get('/logout')


def test_warehouses():
    input = {'warehouseId': '1'}
    data = SaleFilterSchema(context=dict(tenant_id='1')).load(input)
    assert data['shop.id'] == '1'
    assert 'warehouse' not in data


def test_type():
    data = SaleFilterSchema(context=dict(tenant_id='1')).load({})
    assert data['type'] == 2


def test_save_empty_transaction(app):
    app.post('/sales/add', json.dumps({'data': {}}), status=400)


def test_save_transaction(app, spynl_data_db):
    spynl_data_db.buffer.insert_one(
        {'_id': SALE['buffer_id'], 'tenant_id': [TENANT_ID]}
    )
    app.post(
        '/sales/add',
        json.dumps(
            {
                'data': {
                    **SALE,
                    'loyaltyPoints': 10,
                    'customer': {'id': str(CUSTOMER_ID)},
                }
            }
        ),
        status=200,
    )
    buffer = spynl_data_db.buffer.find_one({'_id': SALE['buffer_id']})
    customer = spynl_data_db.customers.find_one({'_id': CUSTOMER_ID})
    assert not buffer['active']
    assert customer['points'] == 10


def test_webshop_save_transaction(app, spynl_data_db):
    resp = app.post(
        '/webshop-sales/add',
        json.dumps({'data': {**SALE, 'payments': {}}}),
        headers={'X-Swapi-Authorization': str(TOKEN)},
        status=200,
    )
    sale = spynl_data_db.transactions.find_one({'_id': ObjectId(resp.json['data'][0])})
    for k, v in sale['payments'].items():
        if k == 'webshop':
            assert v == sale['totalAmount']
        else:
            assert v == 0


def test_cancel(app, spynl_data_db):
    nr = uuid.uuid4()
    sale_result = app.post(
        '/sales/add',
        json.dumps(
            {
                'data': {
                    **SALE,
                    'nr': str(nr),
                    'loyaltyPoints': 10,
                    'customer': {'id': str(CUSTOMER_ID)},
                }
            }
        ),
        status=200,
    )
    cancel_result = app.post(
        '/sales/cancel', json.dumps({'filter': {'nr': str(nr)}}), status=200
    )
    sale = spynl_data_db.transactions.find_one(
        {'_id': ObjectId(sale_result.json['data'][0])}
    )
    canceled = spynl_data_db.transactions.find_one(
        {'_id': ObjectId(cancel_result.json['data'][0])}
    )

    assert all(
        sale['payments'][k] + canceled['payments'][k] == 0 for k in sale['payments']
    )
    assert all(sale[k] + canceled[k] == 0 for k in ['totalAmount', 'totalPaid'])
    assert sum(i['qty'] for i in sale['receipt'] + canceled['receipt']) == 0
    assert canceled['nr'] != sale['nr']
    assert canceled['link'] == {
        'comment': str(sale['nr']),
        'id': str(sale['_id']),
        'resource': 'transactions',
        'type': 'return',
    }

    events = list(spynl_data_db.events.find({'method': 'cancelOrder'}))
    assert (
        sum(
            sale['vat'][k] + canceled['vat'][k]
            for k in sale['vat'].keys()
            if 'value' not in k
        )
        == 0
    )
    assert len(events) == 1


def test_cancel_not_found(app, spynl_data_db):
    app.post(
        '/sales/cancel', json.dumps({'filter': {'nr': str(uuid.uuid4())}}), status=400
    )


def test_upsert_transactions(spynl_data_db, app):
    events_before = spynl_data_db.events.count_documents()
    spynl_data_db.buffer.insert_one(
        {'_id': SALE['buffer_id'], 'tenant_id': [TENANT_ID]}
    )
    app.post('/sales/add', json.dumps({'data': SALE}), status=200)
    events_after = spynl_data_db.events.count_documents()
    assert (0, 1) == (events_before, events_after)
    buffer = spynl_data_db.buffer.find_one({'_id': SALE['buffer_id']})
    assert not buffer['active']


def test_modify_transaction(spynl_data_db, app):
    """
    Also works exactly the same for consignment, and withdrawel
    """
    app.get('/login?username=%s&password=%s' % (USERNAME2, PASSWORD))
    response = app.post(
        f'/tenants/{TENANT_ID}/sales/save', json.dumps({'data': SALE}), status=200
    )
    update = {'data': {**SALE, 'device_id': '12', '_id': response.json['data'][0]}}
    response = app.post(
        f'/tenants/{TENANT_ID}/sales/save', json.dumps(update), status=200
    )
    sale = spynl_data_db.transactions.find_one(
        {'_id': ObjectId(response.json['data'][0])}
    )
    assert sale['device_id'] == '12'


def test_save_bad_transaction(app):
    app.post('/sales/add', json.dumps({'data': BADSALE}), status=400)


def test_duplicate_transaction(app):
    app.post('/sales/add', json.dumps({'data': SALE}), status=200)
    app.post('/sales/add', json.dumps({'data': SALE}), status=400)


def test_save_withdrawel(app):
    app.post('/sales/add', json.dumps({'data': WITHDRAWEL}), status=200)


def test_save_transaction_event_collections(app, spynl_data_db):
    response = app.post('/sales/add', json.dumps({'data': SALE}))
    assert all(
        [
            response.status_code == 200,
            spynl_data_db.events.count_documents() == 1,
            spynl_data_db.transactions.count_documents() == 1,
        ]
    )


def test_nr(spynl_data_db, app):
    """test nr defaults to a uuid."""
    id_ = app.post('/sales/add', json.dumps({'data': SALE_WITHOUT_NR_RECEIPTNR})).json[
        'data'
    ][0]
    tr = spynl_data_db.transactions.find_one({'_id': ObjectId(id_)})
    try:
        uuid.UUID(tr['nr'])
    except Exception:
        pytest.fail('bad nr')


def test_receipt_nr(spynl_data_db, app):
    """test receiptNr increments by default."""
    app.post('/sales/add', json.dumps({'data': SALE}))
    id_ = app.post('/sales/add', json.dumps({'data': SALE_WITHOUT_NR_RECEIPTNR})).json[
        'data'
    ][0]
    tr = spynl_data_db.transactions.find_one({'_id': ObjectId(id_)})
    assert tr['receiptNr'] - SALE['receiptNr'] == 1


def test_get_withdrawals(app):
    """Test normal sales get ignored"""
    app.post('/withdrawals/add', json.dumps({'data': WITHDRAWEL}))
    withdrawal2 = deepcopy(WITHDRAWEL)
    withdrawal2 = {
        key: value for key, value in withdrawal2.items() if key not in ('_id', 'nr')
    }
    app.post('/withdrawals/add', json.dumps({'data': withdrawal2}))
    app.post('/sales/add', json.dumps({'data': SALE}))
    response = app.post('/withdrawals/get')
    assert len(response.json['data']) == 2


def test_get_withdrawals_regex(app, spynl_data_db):
    app.post('/withdrawals/add', json.dumps({'data': WITHDRAWEL}))
    withdrawal2 = deepcopy(WITHDRAWEL)
    withdrawal2 = {
        key: value for key, value in withdrawal2.items() if key not in ('_id', 'nr')
    }
    withdrawal2['withdrawelreason'] = 'Because'
    app.post('/withdrawals/add', json.dumps({'data': withdrawal2}))
    app.post('/sales/add', json.dumps({'data': SALE}))
    response = app.post(
        '/withdrawals/get', json.dumps({'filter': {'withdrawalReason': 'because'}})
    )
    assert len(response.json['data']) == 1


def test_add_consignment(app):
    app.post('/consignments/add', json.dumps({'data': CONSIGNMENT}), status=200)


def test_get_consignments(app, spynl_data_db):
    app.post('/consignments/add', json.dumps({'data': CONSIGNMENT}))
    app.post('/sales/add', json.dumps({'data': SALE}))

    response = app.post('/consignments/get', status=200)

    assert len(response.json['data']) == 1


def test_save_transaction_remark(app, spynl_data_db):

    res = app.post(
        '/sales/add',
        json.dumps(
            {
                'data': {
                    **SALE_REMARK_COMPLEX,
                    'customer': {'id': str(CUSTOMER_ID)},
                }
            }
        ),
        status=200,
    )
    sale_id = json.loads(res.body)['data'][0]
    print("response sale_id: " + str(sale_id))
    print(type(sale_id))
    res = app.get(
        '/sales/get',
        json.dumps(
            {
                'filter': {
                    "id": sale_id,
                }
            }
        ),
        status=200,
    )
    saleremark = json.loads(res.body)['data'][0]['remark']
    print("sale.remark : " + json.dumps(saleremark))
    assert saleremark == "my very smart remark"


def test_add_fiscal_receipt(app):
    add_sale_resp = app.post('/sales/add', json.dumps({'data': SALE}))
    get_sale_resp = app.get(
        '/sales/get', {"filter": {"_id": add_sale_resp.json['data'][0]}}
    )
    add_fiscal_receipt_response = app.post(
        '/sales/add-fiscal-receipt',
        json.dumps(
            {
                "_id": str(get_sale_resp.json['data'][0]['_id']),
                "fiscal_receipt_nr": "123",
                "fiscal_shift_nr": "1",
                "fiscal_date": "2022-09-28",
                "fiscal_printer_id": "1234567890A",
            }
        ),
    )
    assert add_fiscal_receipt_response.json['data']['fiscal_receipt_nr'] == "123"
    assert add_fiscal_receipt_response.json['data']['fiscal_shift_nr'] == "1"
    assert add_fiscal_receipt_response.json['data']['fiscal_date'] == "2022-09-28"
    assert (
        add_fiscal_receipt_response.json['data']['fiscal_printer_id'] == "1234567890A"
    )

    updated_sale_resp = app.get(
        '/sales/get', {"filter": {"_id": add_sale_resp.json['data'][0]}}
    )
    assert updated_sale_resp.json['data'][0]['fiscal_receipt_nr'] == "123"
    assert updated_sale_resp.json['data'][0]['fiscal_shift_nr'] == "1"
    assert updated_sale_resp.json['data'][0]['fiscal_date'] == "2022-09-28"
    assert updated_sale_resp.json['data'][0]['fiscal_printer_id'] == "1234567890A"
