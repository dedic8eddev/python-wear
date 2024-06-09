"""Tests for sale aggregation queries."""

import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timedelta

import pytest
from bson import ObjectId
from pytz import timezone

from spynl.main.dateutils import date_to_str, now
from spynl.main.exceptions import IllegalAction
from spynl.main.testutils import get, post

from spynl.api.auth.authentication import scramble_password
from spynl.api.retail.sales_reports import CustomerSalesSchema, get_warehouse_id
from spynl.api.retail.utils import round_results

customer_id = uuid.uuid4()
BARCODES_PER_CUSTOMER_DATE = now() - timedelta(weeks=104)


@pytest.fixture(autouse=True)
def set_db(db):
    """
    Fill in the database with one company, its owner and one employee.

    We are setting up an existing company with one existing user who is
    owner and one existing user who is employee.
    We also note what new user and company names we'll use.
    """
    db.tenants.insert_one(
        {
            '_id': 'existingtenantid',
            'name': 'Old Corp.',
            'active': True,
            'applications': ['dashboard', 'pos'],
            # owner does not exist, but none of the users now have
            # the owner role, for cleaner testing of role access
            'owners': [ObjectId()],
        }
    )
    db.tenants.insert_one({'_id': 'master', 'name': 'master tenant'})
    db.users.insert_one(
        {
            '_id': ObjectId(),
            'username': 'existing-hans',
            'email': 'existing-user@softwear.nl',
            'fullname': 'Hans Meyer',
            'password_hash': scramble_password('blah', 'blah', '2'),
            'password_salt': 'blah',
            'hash_type': '2',
            'active': True,
            'tz': 'Europe/Amsterdam',
            'tenant_id': ['existingtenantid'],
            'roles': {'existingtenantid': {'tenant': ['dashboard-report_user']}},
        }
    )

    db.users.insert_one(
        {
            '_id': ObjectId(),
            'username': 'existing-sjaak',
            'email': 'existing-user@softwear.nl',
            'fullname': 'Sjaak Man',
            'password_hash': scramble_password('blah', 'blah', '2'),
            'password_salt': 'blah',
            'hash_type': '2',
            'active': True,
            'tz': 'Europe/Amsterdam',
            'wh': '51',
            'tenant_id': ['existingtenantid'],
            'roles': {'existingtenantid': {'tenant': ['dashboard-report_user']}},
        }
    )

    db.users.insert_one(
        {
            '_id': ObjectId(),
            'username': 'existing-jan',
            'email': 'existing-employee@softwear.nl',
            'fullname': 'Jan Azubi',
            'password_hash': scramble_password('blah', 'blah', '2'),
            'password_salt': 'blah',
            'hash_type': '2',
            'active': True,
            'tenant_id': ['existingtenantid'],
            'type': 'standard',
            'roles': {'existingtenantid': {'tenant': []}},
        }
    )
    db.warehouses.insert_one(
        {'_id': '00001', 'tenant_id': ['existingtenantid'], 'wh': '51'}
    )
    db.warehouses.insert_one(
        {'_id': '00003', 'tenant_id': ['existingtenantid'], 'wh': '52'}
    )
    db.warehouses.insert_one(
        {'_id': '00002', 'tenant_id': ['anothertenantid'], 'wh': '52'}
    )

    template = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'data', 'sales-template.json'
    )
    with open(template, 'r') as fob:
        sales_template = json.loads(fob.read())

    sale1 = deepcopy(sales_template)
    sale1.update(
        {
            'created': {'date': now() - timedelta(hours=2)},
            'device': '1',
            'totalPaid': 10,
            'totalCoupon': 2,
            'totalAmount': 17,
            'totalDiscount': 2,
            'totalDiscountCoupon': 3,
            'couponTotals': {' ': 2, 'C': 1},
        }
    )
    db.transactions.insert_one(sale1)
    withdrawal1 = deepcopy(sales_template)
    withdrawal1.update(
        {
            'created': {'date': now() - timedelta(hours=2)},
            'payments': {'cash': -50, 'withdrawel': 50},
            'receipt': [],
        }
    )
    db.transactions.insert_one(withdrawal1)
    sale2 = deepcopy(sales_template)
    sale2.update(
        {
            'created': {'date': now() - timedelta(hours=24)},
            'totalPaid': 10,
            'totalStoreCCreditPaid': 20,  # misspelled, -> calculated as 0
            'totalAmount': 10,
            'shop': {'id': '52', 'name': 'Shop 2'},
        }
    )
    sale2_inactive = deepcopy(sale2)
    sale2_inactive.update({'active': False})
    db.transactions.insert_one(sale2)
    db.transactions.insert_one(sale2_inactive)
    sale3 = deepcopy(sales_template)
    sale3.update(
        {
            'created': {'date': now() - timedelta(days=8)},
            'totalPaid': 20,
            'totalAmount': 24,
            'totalCoupon': 4,
        }
    )
    sale3_inactive = deepcopy(sale3)
    sale3_inactive.update({'active': False})
    db.transactions.insert_one(sale3)
    db.transactions.insert_one(sale3_inactive)
    sale4 = deepcopy(sales_template)
    sale4.update(
        {
            'created': {'date': now() - timedelta(hours=60)},
            'totalPaid': 40,
            'totalCoupon': 18,
            'totalAmount': 49,
            'totalDiscount': 2,
            'totalDiscountCoupon': 3,
            'couponTotals': {'C': 3},
            'totalStoreCreditPaid': 5,
            'shop': {'id': '52', 'name': 'Shop 2'},
            'device': '2',
            'receipt': [
                {
                    'sku': 'sku_id1',
                    'qty': 1,
                    'price': 5,
                    'category': 'barcode',
                    'articleCode': 'yahoo-J-2',
                    'articleDescription': 'Yahoo 2 Jeans',
                    'sizeLabel': 'XL',
                    'color': 'blue',
                    'group': 'C',
                    'brand': 'A',
                },
                {
                    'sku': 'sku_id2',
                    'qty': -2,
                    'price': 9.99,
                    'category': 'barcode',
                    'articleCode': 'yahoo-J-2',
                    'articleDescription': 'Yahoo 2 Jeans',
                    'sizeLabel': 'L',
                    'color': 'blue',
                    'group': 'C',
                    'brand': 'A',
                },
                {'price': 5, 'qty': 1, 'category': 'storecredit'},
                {
                    'sku': 'sku_id3',
                    'qty': 5,
                    'price': 1.99,
                    'category': 'barcode',
                    'articleCode': 'yahoo-J-3',
                    'articleDescription': 'Yahoo 3 Jeans',
                    'sizeLabel': 'XL',
                    'color': 'blue',
                    'group': 'D',
                    'brand': 'B',
                },
                {
                    'barcode': '+KAV1KIQX9UIA7',
                    'category': 'coupon',
                    'couponNr': 'KAV1KIQX9UIA7',
                    'found': True,
                    'group': '',
                    'nettPrice': 14.00,
                    'price': 14.00,
                    'qty': 1,
                    'type': 'A',
                    'vat': 0,
                },
                {'sku': 'sku_id4', 'qty': 2, 'price': 7.99},
            ],
        }
    )
    db.transactions.insert_one(sale4)
    withdrawal2 = deepcopy(sales_template)
    withdrawal2.update(
        {
            'created': {'date': now() - timedelta(hours=60)},
            'shop': {'id': '52', 'name': 'Shop 2'},
            'payments': {'withdrawel': 25, 'cash': -25},
            'receipt': [],
        }
    )
    db.transactions.insert_one(withdrawal2)
    consignment1 = deepcopy(sales_template)
    consignment1.update(
        {
            'created': {'date': now() - timedelta(hours=2)},
            'payments': {'consignment': 25},
            'type': 9,
            'totalAmount': 25,
        }
    )
    db.transactions.insert_one(consignment1)

    # insert customer for sold_barcodes_per_customer
    db.customers.insert_one({'_id': customer_id, 'tenant_id': 'existingtenantid'})
    # insert transaction for testing the sold_barcodes_per_customer endpoint
    # date in past to not conflict with other tests.
    db.transactions.insert_one(
        {
            'created': {'date': BARCODES_PER_CUSTOMER_DATE},
            'totalStoreCreditPaid': 0,
            'vat': {
                'hightotal': 250.5,
                'zeroamount': 0,
                'zerototal': 0,
                'lowamount': 0,
                'highamount': 43.48,
                'lowtotal': 0,
            },
            'shop': {
                'houseadd': '',
                'zipcode': '1181 ZL',
                'city': 'Amstelveen',
                'name': 'Amstelveen',
                'id': '51',
                'street': 'Rembrandthof',
                'houseno': '12',
                'phone': '020-4539007',
            },
            'payments': {
                'consignment': 0,
                'withdrawel': 0,
                'cash': 250.5,
                'pin': 0,
                'creditcard': 0,
                'couponout': 0,
                'creditreceipt': 0,
                'storecredit': 0,
                'couponin': 0,
            },
            'withdrawelreason': '',
            'reqid': 0,
            'shift': '16c737a10-6eb4-43ec-8c5d-7e91e6151841',
            'nr': '51-5137-706',
            'loyaltyPoints': 52,
            'printed': '30-03-17 12:35',
            'totalPaid': 250.5,
            'receipt': [
                {
                    'changeDisc': False,
                    'articleCode': 'B.Drake Coat',
                    'category': 'barcode',
                    'sizeLabel': '-',
                    'reqid': 'a66b',
                    'articleDescription': 'Drake Coat',
                    'found': True,
                    'nettPrice': 250.5,
                    'color': 'antelopeaged washed',
                    'vat': 21,
                    'barcode': '10',
                    'price': 250.5,
                    'brand': 'My God',
                    'group': None,
                    'qty': 1,
                }
            ],
            'totalNumber': 1,
            'receiptNr': 706,
            'customer': {
                'email': '',
                'title': '',
                'loyaltynr': '0000001367',
                'points': 27,
                'lastname': 'Customer',
                'id': str(customer_id),
                'storecredit': 127.75,
                'middlename': '',
                'firstname': 'V,',
                'custnum': '$AAjI',
            },
            'change': 0,
            'difference': 0,
            'totalDiscount': 0,
            'discountreason': '',
            'selectedLine': 0,
            'device_id': 'HC8KG',
            'totalAmount': 250.5,
            'coupon': {'type': 'C', 'id': 'W96GLKAH6RGKM', 'value': 12.53},
            'device': '56388f5c500ce94d78b121fb',
            'tenant_id': ['existingtenantid'],
            'type': 2,
            'totalCoupon': 0,
            'amountEntry': '0',
            'buffer_id': 'buffer_8d3f4794-3d13-41c2-b7af-5f69c1a1f3f5',
            'pinInfo': '',
            'totalDiscountCoupon': 0,
            'couponTotals': {'C': 0, ' ': 0},
            'receipt_email': '',
            'cashier': {
                'fullname': 'Tony',
                'id': 'maddoxx.12@softwear.nu',
                'name': '12',
            },
            'remark': '',
            'pinError': '',
            'active': True,
        }
    )
    # insert return with qty 0 items
    sale_return = deepcopy(sales_template)
    sale_return.update(
        {
            'created': {'date': now() - timedelta(weeks=50)},
            'totalPaid': -5,
            'shop': {'id': '52', 'name': 'Shop 2'},
            'receipt': [
                {
                    'sku': 'sku_id1',
                    'qty': -1,
                    'price': 5,
                    'category': 'barcode',
                    'articleCode': 'yahoo-J-1',
                    'articleDescription': 'Yahoo 1 Jeans',
                    'group': 'C',
                    'brand': 'A',
                },
                {
                    'sku': 'sku_id2',
                    'qty': 0,
                    'price': 9.99,
                    'category': 'barcode',
                    'articleCode': 'yahoo-J-2',
                    'articleDescription': 'Yahoo 2 Jeans',
                    'group': 'C',
                    'brand': 'A',
                },
                {
                    'sku': 'sku_id3',
                    'qty': 0,
                    'price': 1.99,
                    'category': 'barcode',
                    'articleCode': 'yahoo-J-3',
                    'articleDescription': 'Yahoo 3 Jeans',
                    'group': 'D',
                    'brand': 'B',
                },
            ],
        }
    )
    db.transactions.insert_one(sale_return)


class Request:
    def __init__(self, wh=None, user_wh=None):
        self.args = {}
        self.cached_user = {}
        if wh:
            self.args.update(warehouseId=wh)
        if user_wh:
            self.cached_user.update(wh=user_wh)


@pytest.mark.parametrize(
    'wh,user_wh',
    [
        ('51', '51'),  # if user requests wh he has access too
        ('51', None),  # if user requests wh and he is not assigned one
        (None, '51'),  # if has warehouse assigned to him but does not ask for one
        # in particular
    ],
)
def test_get_warehouse_id_ok(wh, user_wh):
    """Test valid scenarios for requesting warehouses."""
    request = Request(wh, user_wh)
    assert (
        get_warehouse_id(request.cached_user.get('wh'), request.args.get('warehouseId'))
        == '51'
    )


def test_get_warehouse_id_bad():
    """Test requesting a warehouse when you are assigned a different one"""
    request = Request('51', '52')
    with pytest.raises(IllegalAction):
        get_warehouse_id(request.cached_user.get('wh'), request.args.get('warehouseId'))


# ---- Period ----


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_period_unauthorized(db, app, login):
    """Jan is not allowed to read sales."""
    response = get(app, '/sales/period', expect_errors=True)
    assert response['status'] == 'error'
    assert response['type'] == 'HTTPForbidden'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_period_no_params(db, app, login):
    """Simple period w/o parameters, so 48 hours back"""
    response = get(app, '/sales/period')
    assert response['status'] == 'ok'
    assert len(response['data']) == 2
    assert set([10, 14]) == set([row['turnover'] for row in response['data']])


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_period_no_params_excel(db, app, login):
    """Simple period w/o parameters, so 48 hours back"""
    app.get('/sales/period-excel', status=200)


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_period_no_params_csv(db, app, login):
    """Simple period w/o parameters, so 48 hours back"""
    app.get('/sales/period-csv', status=200)


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_period_too_early(db, app, login):
    """Ask for too long period (for minute grouping)"""
    response = post(
        app,
        '/sales/period',
        {'startDate': date_to_str(now() - timedelta(days=9)), 'group_by': 'minute'},
        expect_errors=True,
    )
    assert response['status'] == 'error'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_custom_period(db, app, login):
    """Ask for a custom recent period"""
    response = post(
        app, '/sales/period', {'startDate': date_to_str(now() - timedelta(hours=10))}
    )
    assert response['status'] == 'ok'
    sale1_time = now() - timedelta(hours=2)  # like sale1
    # ... but localised to hans' time zone !!
    sale1_time = sale1_time.astimezone(timezone('Europe/Amsterdam'))
    assert len(response['data']) == 1
    assert response['grouped_by'] == 'minute'
    assert response['data'][0]['turnover'] == 14  # turnover of sale1
    server_time = datetime(
        response['data'][0]['date']['year'],
        response['data'][0]['date']['month'],
        response['data'][0]['date']['day'],
        response['data'][0]['date']['hour'],
        response['data'][0]['date']['minute'],
        0,
    )  # doesn't return seconds so set it to 0
    # didnt set the timezone in the server_time creation, instead using the
    # localize
    server_time = timezone('Europe/Amsterdam').localize(server_time)
    seconds_difference = (sale1_time - server_time).seconds
    # The difference can be 1 minute max
    assert 0 <= (seconds_difference - sale1_time.second) <= 60


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_period_no_result(db, app, login):
    """Ask for a period without data"""
    response = post(
        app, '/sales/period', {'startDate': date_to_str(now() - timedelta(minutes=30))}
    )
    assert response['status'] == 'ok'
    assert len(response['data']) == 0


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_warehouse_period_wrong_grouping(db, app, login):
    """Group by parameter is wrong."""
    response = post(
        app,
        '/sales/period',
        {
            'startDate': date_to_str(now() - timedelta(days=3)),
            'endDate': date_to_str(now()),
            'warehouseId': '51',
            'group_by': 'mminute',
        },
        expect_errors=True,
    )
    assert response['status'] == 'error'
    assert response['type'] == 'IllegalParameter'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_warehouse_period_groupby_day(db, app, login):
    """Period for a warehouse by day, looking for two sales in warehouse 52."""
    response = post(
        app,
        '/sales/period',
        {
            'startDate': date_to_str(now() - timedelta(days=3)),
            'endDate': date_to_str(now()),
            'warehouseId': '52',
            'group_by': 'day',
        },
    )
    today = now()
    sale2_date = today - timedelta(hours=24)
    sale4_date = today - timedelta(hours=60)
    rows = sorted(
        response['data'],
        key=lambda r: (r['date']['year'], r['date']['month'], r['date']['day']),
    )

    assert (
        response['status'] == 'ok'
        and len(rows) == 2
        and rows[0]['date']['day'] == sale4_date.day
        and rows[0]['turnover'] == 41
        and rows[1]['date']['day'] == sale2_date.day
        and rows[1]['turnover'] == 10
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_warehouse_period_month(db, app, login):
    """period  for a warehouse by month, looking for warehouse 51"""
    response = post(
        app,
        '/sales/period',
        {
            'startDate': date_to_str(now() - timedelta(days=1)),
            'endDate': date_to_str(now()),
            'warehouseId': '51',
            'group_by': 'month',
        },
    )
    assert response['status'] == 'ok'
    today = now()
    assert response['data'][0]['date']['month'] == today.month
    assert response['data'][0]['date']['year'] == today.year
    # only sale1 (sales:12) is in the current month
    assert response['data'][0]['turnover'] == 14


# ---- summary ----


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_summary_unauthorized(db, app, login):
    """jan is not allowed to read sales."""
    response = get(app, '/sales/summary', expect_errors=True)
    assert response['status'] == 'error'
    assert response['type'] == 'HTTPForbidden'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_overall_receipt_discount(db, app, login):
    template = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'data', 'sales-template.json'
    )
    with open(template, 'r') as fob:
        sales_template = json.loads(fob.read())

    sales = [
        {
            **deepcopy(sales_template),
            'created': {'date': now()},
            'overallReceiptDiscount': 4,
            'device': 999,
        },
        {
            **deepcopy(sales_template),
            'created': {'date': now()},
            'overallReceiptDiscount': 3,
            'couponTotals': {'C': 1},
            'device': 999,
        },
        {
            **deepcopy(sales_template),
            'created': {'date': now()},
            'overallReceiptDiscount': 4,
            'couponTotals': {' ': 1, 'C': 2},
            'device': 999,
        },
        {
            **deepcopy(sales_template),
            'created': {'date': now()},
            'overallReceiptDiscount': 5,
            'couponTotals': {' ': 1, 'C': 4},
            'device': 999,
        },
        {
            **deepcopy(sales_template),
            'created': {'date': now()},
            # should not really happen but is theoretically possible
            'overallReceiptDiscount': -2,
            'couponTotals': {'C': 2},
            'device': 999,
        },
    ]
    db.transactions.insert_many(sales)

    response = post(
        app,
        '/sales/summary',
        {
            'device': 999,
            'startDate': date_to_str(now() - timedelta(days=1)),
            'endDate': date_to_str(now() + timedelta(days=1)),
        },
    )
    assert response['data']['overallReceiptDiscount'] == 14
    db.transactions.delete_one({'device': 999})


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_summary_all_warehouses(db, app, login):
    """Simple working summary across warehouses"""
    response = post(
        app,
        '/sales/summary',
        {
            'startDate': date_to_str(now() - timedelta(days=3)),
            'endDate': date_to_str(now()),
        },
    )
    assert response['status'] == 'ok'
    data = response['data']
    assert data['transactions'] == 5
    # 1 in sale 1, 1 in sale2, 1+0+5+2 in sale4
    # (1st 0 is for returned -2, 2nd for receipt missing "barcode" category)
    assert data['items'] == 8
    assert data['itemTransactions'] == 3
    assert round(data['itemsPer'], 2) == 2.67  # 8 items / 3 item transactions
    assert data['returns'] == 2  # see sale4
    assert data['turnover'] == 51
    assert data['withdrawal'] == 75  # 50+25 (withdrawal1 + withdrawal4)
    assert data['totalPer'] == 51 / 3  # total turnover / 3 item transactions
    assert data['nettItems'] == 6  # 8 - 2
    assert data['nettItemsPer'] == 2  # 8 items - 2 returns / 3
    assert data['consignment'] == 25.0
    assert data['consignmentItems'] == 1


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_summary_with_warehouse(db, app, login):
    """Simple working warehouse-summary"""
    response = post(
        app,
        '/sales/summary',
        {
            'startDate': date_to_str(now() - timedelta(days=3)),
            'endDate': date_to_str(now()),
            'warehouseId': '52',
        },
    )
    assert response['status'] == 'ok'
    data = response['data']
    assert data['transactions'] == 3
    # 1 in sale2, 1+0+5+0 in sale4 (1st 0 is for the returned -2,
    # 2nd for a receipt which is missing the "barcode" category)
    assert data['items'] == 7
    assert data['itemTransactions'] == 2
    # 7 items divided by 2 item transactions:
    assert data['itemsPer'] == 3.5
    assert data['returns'] == 2  # see sale4
    assert data['turnover'] == 37
    assert data['withdrawal'] == 25
    assert data['totalPer'] == 18.5  # total turnover 35 / 2 item transactions
    assert data['nettItems'] == 5  # 7 items - 2 returns
    assert data['nettItemsPer'] == 2.5  # 7 items - 2 returns / 2


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_summary_with_device(db, app, login):
    """Simple working warehouse-summary"""
    response = post(
        app,
        '/sales/summary',
        {
            'startDate': date_to_str(now() - timedelta(days=3)),
            'endDate': date_to_str(now()),
            'device': '1',
        },
    )
    assert response['status'] == 'ok'
    data = response['data']
    assert data['transactions'] == 1
    assert data['items'] == 1
    assert data['itemTransactions'] == 1
    assert data['itemsPer'] == 1
    assert data['returns'] == 0
    assert data['turnover'] == 14.0
    assert data['withdrawal'] == 0
    assert data['totalPer'] == 14.0
    assert data['nettItems'] == 1
    assert data['nettItemsPer'] == 1


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_summary_nonexistant_warehouse(db, app, login):
    """warehouse 00003 does not exist."""
    response = post(
        app,
        '/sales/summary',
        {
            'startDate': date_to_str(now() - timedelta(days=3)),
            'endDate': date_to_str(now()),
            'warehouseId': '53',
        },
        expect_errors=True,
    )
    assert response['status'] == 'error'
    assert response['type'] == 'IllegalAction'
    assert 'The warehouse' in response['message']
    assert 'does not exist' in response['message']


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_summary_nodata(db, app, login):
    """No data: zeroed"""
    response = post(
        app,
        '/sales/summary',
        {
            'startDate': date_to_str(now() - timedelta(days=52)),
            'endDate': date_to_str(now() - timedelta(days=51)),
        },
    )
    assert response['status'] == 'ok'
    assert all(
        response['data'][field] == 0
        for field in (
            'transactions',
            'items',
            'itemsPer',
            'itemTransactions',
            'totalPer',
            'nettItemsPer',
            'nettItems',
            'returns',
            'turnover',
            'withdrawal',
            'consignmentItems',
            'consignment',
            'cash',
            'KA',
            'KU',
            'KC',
            'K',
            'totalDiscount',
        )
    )


# ---- Per-warehouse ----


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perwarehouse_unauthorized(db, app, login):
    """jan is not allowed to read sales."""
    response = get(app, '/sales/per-warehouse', expect_errors=True)
    assert response['status'] == 'error'
    assert response['type'] == 'HTTPForbidden'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perwarehouse_dates_wrong_order(db, app, login):
    """Start date is after end date"""
    response = post(
        app,
        '/sales/per-warehouse',
        {
            'startDate': date_to_str(now() - timedelta(days=2)),
            'endDate': date_to_str(now() - timedelta(days=4)),
        },
        expect_errors=True,
    )
    assert response['status'] == 'error'
    assert response['type'] == 'IllegalPeriod'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perwarehouse(db, app, login):
    """Simple working per-warehouse, looking for latest two sales."""
    response = post(
        app,
        '/sales/per-warehouse',
        {
            'startDate': date_to_str(now() - timedelta(days=2)),
            'endDate': date_to_str(now()),
        },
    )

    rows = sorted(response['data'], key=lambda r: r['warehouse']['id'])

    assert (
        response['status'] == 'ok'
        and len(rows) == 2
        and rows[0]["warehouse"]['id'] == '51'
        and rows[0]["warehouse"]['name'] == 'Shop 1'
        and rows[0]['turnover'] == 14
        and rows[0]['qty'] == 1
        and rows[1]["warehouse"]['id'] == '52'
        and rows[1]["warehouse"]['name'] == 'Shop 2'
        and rows[1]['turnover'] == 10
        and rows[1]['qty'] == 1
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perwarehouse_excel(db, app, login):
    """Simple working per-warehouse, looking for latest two sales."""
    app.post_json(
        '/sales/per-warehouse-excel',
        {
            'startDate': date_to_str(now() - timedelta(days=2)),
            'endDate': date_to_str(now()),
        },
        status=200,
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perwarehouse_csv(db, app, login):
    """Simple working per-warehouse, looking for latest two sales."""
    app.post_json(
        '/sales/per-warehouse-csv',
        {
            'startDate': date_to_str(now() - timedelta(days=2)),
            'endDate': date_to_str(now()),
        },
        status=200,
    )


@pytest.mark.parametrize(
    'login',
    [('existing-sjaak', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perwarehouse_with_wh_assigned_to_user(db, app, login):
    """
    Simple working per-warehouse, checks that it only returns the data
    for the users assigned wh.
    """
    response = post(
        app,
        '/sales/per-warehouse',
        {
            'startDate': date_to_str(now() - timedelta(days=2)),
            'endDate': date_to_str(now()),
        },
    )
    row = response['data'][0]
    assert (
        response['status'] == 'ok'
        and len(response['data']) == 1
        and row['warehouse']['id'] == '51'
        and row['warehouse']['name'] == 'Shop 1'
        and row['turnover'] == 14
    )


# ---- Per-article ----


@pytest.mark.parametrize(
    'login',
    [('existing-jan', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_unauthorized(db, app, login):
    """jan is not allowed to read sales."""
    response = get(app, '/sales/per-article', expect_errors=True)
    assert response['status'] == 'error'
    assert response['type'] == 'HTTPForbidden'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_nodates(db, app, login):
    """test missing parameter check"""
    response = post(
        app,
        '/sales/per-article',
        {'endDate': date_to_str(now() + timedelta(days=-4))},
        expect_errors=True,
    )
    assert response['status'] == 'error'
    assert response['type'] == 'MissingParameter'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_nosales(db, app, login):
    """Testing per-article going all well but no sales"""
    response = post(
        app,
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-4)),
        },
    )
    assert response['status'] == 'ok'
    assert len(response['data']) == 0


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_withsales(db, app, login):
    """Testing per-article going all well, with 2 receipts (in sale4)"""
    response = post(
        app,
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
        },
    )
    assert response['status'] == 'ok'

    rows = sorted(response['data'], key=lambda r: r['article']['description'])
    assert (
        len(rows) == 2
        and rows[0]['article']['description'] == 'Yahoo 2 Jeans'
        and rows[0]['turnover'] == -14.98  # 1 * 5 + 2 * -9.99
        and rows[0]['qty'] == -1
        and rows[1]['article']['description'] == 'Yahoo 3 Jeans'
        and rows[1]['turnover'] == 9.95  # 5 * 1.99
        and rows[1]['qty'] == 5
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_withsales_excel(db, app, login):
    app.post_json(
        '/sales/per-article-excel',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
        },
        status=200,
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_withsales_csv(db, app, login):
    app.post_json(
        '/sales/per-article-csv',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
        },
        status=200,
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_brand(db, app, login):
    """Testing per-article going all well, with 2 receipts (in sale4)"""
    response = post(
        app,
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
            'category': 'brand',
        },
    )
    assert response['status'] == 'ok'
    rows = sorted(response['data'], key=lambda r: r['brand'])
    assert (
        len(rows) == 2
        and rows[0]['brand'] == 'A'
        and rows[0]['turnover'] == -14.98  # 1 * 5 + 2 * -9.99
        and rows[1]['brand'] == 'B'
        and rows[1]['turnover'] == 9.95  # 5 * 1.99
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_with_color_size(db, app, login):
    """Testing per-article going all well, with 2 receipts (in sale4)"""
    response = post(
        app,
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
            'category': 'articleColorSize',
        },
    )
    assert response['status'] == 'ok'

    assert sorted(response['data'], key=lambda r: r['turnover']) == [
        {
            'articleColorSize': {
                'code': 'yahoo-J-2',
                'color': 'blue',
                'description': 'Yahoo 2 Jeans',
                'sizeLabel': 'L',
            },
            'qty': -2,
            'turnover': -19.98,
        },
        {
            'articleColorSize': {
                'code': 'yahoo-J-2',
                'color': 'blue',
                'description': 'Yahoo 2 Jeans',
                'sizeLabel': 'XL',
            },
            'qty': 1,
            'turnover': 5,
        },
        {
            'articleColorSize': {
                'code': 'yahoo-J-3',
                'color': 'blue',
                'description': 'Yahoo 3 Jeans',
                'sizeLabel': 'XL',
            },
            'qty': 5,
            'turnover': 9.95,
        },
    ]


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_group(db, app, login):
    """Testing per-article going all well, with 2 receipts (in sale4)"""
    response = post(
        app,
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-6)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
            'category': 'articleGroup',
        },
    )
    assert response['status'] == 'ok'
    rows = sorted(response['data'], key=lambda r: r['articleGroup'])
    assert (
        len(rows) == 2
        and rows[0]['articleGroup'] == 'C'
        and rows[0]['turnover'] == -14.98  # 1 * 5 + 2 * -9.99
        and rows[1]['articleGroup'] == 'D'
        and rows[1]['turnover'] == 9.95  # 5 * 1.99
    )


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_with_warehouse(db, app, login):
    """Testing per-article going all well, with 2 sales"""
    response = post(
        app,
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-10)),
            'endDate': date_to_str(now() + timedelta(days=-2)),
            'warehouseId': '51',
        },
    )
    assert response['status'] == 'ok'
    assert len(response['data']) == 1
    assert response['data'][0]['article']['description'] == 'Yahoo Jeans'
    assert response['data'][0]['turnover'] == 0  # 1 * 0


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_with_device(db, app, login):
    """Testing per-article going all well, with 2 sales"""
    response = app.post_json(
        '/sales/per-article',
        {
            'startDate': date_to_str(now() + timedelta(days=-10)),
            'endDate': date_to_str(now()),
            'device': '2',
        },
        status=200,
    )
    data = {(r['article']['description'], r['turnover']) for r in response.json['data']}
    assert data == {('Yahoo 2 Jeans', -14.98), ('Yahoo 3 Jeans', 9.95)}


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_export_with_empty_data(db, app, login):
    try:
        query = {
            'startDate': date_to_str(now() + timedelta(days=50)),
            'endDate': date_to_str(now() + timedelta(days=100)),
            'warehouseId': '51',
        }
        response = app.post_json('/sales/per-article-csv', query)
    except IndexError:
        pytest.fail('should return empty export on empty result set')
    assert response.text.strip() == ''


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_perarticle_leave_out_qty_0_items(db, app, login):
    payload = {
        'startDate': date_to_str(now() - timedelta(weeks=51)),
        'endDate': date_to_str(now() - timedelta(weeks=49)),
    }
    response = app.post_json('/sales/per-article', payload, status=200)
    assert len(response.json['data']) == 1
    assert response.json['data'][0]['article']['code'] == 'yahoo-J-1'


@pytest.mark.parametrize(
    'login',
    [('existing-hans', 'blah', dict(tenant_id='existingtenantid'))],
    indirect=True,
)
def test_sold_barcodes_per_customer(app, login, db):
    """Test the sold_barcodes_per_customer endpoint"""
    payload = {
        'startDate': date_to_str(now() - timedelta(weeks=105)),
        'endDate': date_to_str(now() - timedelta(weeks=103)),
        'customerId': str(customer_id),
    }
    response = post(app, '/sales/barcodes-per-customer', payload)
    expected_data = [
        {
            'articleCode': 'B.Drake Coat',
            'articleDescription': 'Drake Coat',
            'barcode': '10',
            'brand': 'My God',
            'category': 'barcode',
            'color': 'antelopeaged washed',
            'nettPrice': 250.5,
            'price': 250.5,
            'qty': 1,
            'sizeLabel': '-',
            'vat': 21,
            'date': date_to_str(
                BARCODES_PER_CUSTOMER_DATE.astimezone(timezone('Europe/Amsterdam'))
            ),
        }
    ]
    assert response['data'] == expected_data


def test_default_daterange():
    data = CustomerSalesSchema(only=('startDate', 'endDate')).load({})
    delta = data['endDate'] - data['startDate']
    assert delta.days == 7


def test_round():
    data = [{'a': 1, 'b': 1.223}, {'a': 1.00, 'b': 1.229}, {'a': 1.999, 'b': 1.992}]

    round_results(data)
    assert data == [{'a': 1, 'b': 1.22}, {'a': 1.00, 'b': 1.23}, {'a': 2.00, 'b': 1.99}]
