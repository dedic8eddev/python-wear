import json
import os
import random
from collections import defaultdict
from copy import deepcopy
from uuid import UUID

import pytest
from bson.objectid import ObjectId
from marshmallow import ValidationError

from spynl_schemas.sale import (
    BarcodeItem,
    BaseItemSchema,
    CashierSchema,
    ConsignmentSchema,
    CouponItem,
    CustomerSchema,
    SaleSchema,
    ShopSchema,
    TransitSchema,
    round_to_05,
)

from . import example_sales_for_pdf as pdf  # noqa: I252

THRESHOLD = 0.1e-6
EXAMPLE_SALES_DIR = os.path.abspath(os.path.dirname(__file__))


def test_totals():
    data = dict(
        receipt=[
            dict(category='barcode', qty=5, price=6.99),
            dict(category='barcode', qty=3, price=1.89),
            dict(category='barcode', qty=-2, price=10.00),
            dict(category='storecredit', qty=4, price=8.99),
            dict(category='storecredit', qty=1, price=2.99),
        ],
        payments=dict(
            cash=0.0,
            storecredit=0.0,
            pin=0.0,
            creditcard=0.0,
            couponin=0.0,
            creditreceipt=0.0,
            withdrawel=0.0,
            consignment=0.0,
        ),
    )
    expected_totals = dict(
        totalAmount=59.57,
        totalStoreCreditPaid=38.95,
        totalPaid=0.0,
        totalNumber=13,
        totalReturn=2,
        totalCoupon=0.0,
        totalDiscountCoupon=0.0,
    )
    result = {
        key: round(value, 2)
        for key, value in SaleSchema.calculate_totals(data).items()
        if key in expected_totals
    }

    assert result == expected_totals


def test_totals_with_deprecated_total_dicount():
    data = dict(
        receipt=[
            dict(category='coupon', type='C', value=5),
            dict(category='barcode', qty=5, price=6.99),
            dict(category='barcode', qty=3, price=1.89),
            dict(category='barcode', qty=-2, price=10.00),
            dict(category='storecredit', qty=4, price=8.99),
            dict(category='storecredit', qty=1, price=2.99),
        ],
        payments=dict(
            cash=0.0,
            storecredit=0.0,
            pin=0.0,
            creditcard=0.0,
            couponin=0.0,
            creditreceipt=0.0,
            withdrawel=0.0,
            consignment=0.0,
        ),
        totalDiscount=10,
    )
    expected_totals = dict(
        totalAmount=59.57,
        totalStoreCreditPaid=38.95,
        totalPaid=0.0,
        totalNumber=13,
        totalReturn=2,
        totalCoupon=0.0,
        totalDiscountCoupon=5,
        overallReceiptDiscount=5,
    )
    result = {
        key: round(value, 2)
        for key, value in SaleSchema.calculate_totals(data).items()
        if key in expected_totals
    }

    assert result == expected_totals


def test_total_coupons():
    data = dict(
        payments=defaultdict(int),
        receipt=[
            dict(category='coupon', type='A', price=6.99),
            dict(category='coupon', type='U', price=1.89),
            dict(category='coupon', type='I', price=8.99),
            dict(category='coupon', type='T', price=2.99),
            dict(category='coupon', type=' ', value=8.99),
            dict(category='coupon', type='C', value=2.99),
        ],
    )

    expected_totals = dict(totalCoupon=2.88, totalDiscountCoupon=11.98)
    result = {
        key: round(value, 2)
        for key, value in SaleSchema.calculate_totals(data).items()
        if key in expected_totals
    }

    assert result == expected_totals


def test_total_payments():
    data = dict(
        receipt=[],
        payments=dict(
            cash=-8.89, pin=12.87, creditcard=1.00, creditreceipt=2.10, storecredit=0
        ),
    )
    result = SaleSchema.calculate_totals(data)
    assert round(result['totalPaid'], 2) == 7.08


def test_vat():
    vat_settings = dict(low=6.0, high=21.0, zero=0.0)
    data = dict(
        totalAmount=60.62,
        totalDiscountCoupon=3.0,
        overallReceiptDiscount=4.0,
        receipt=[
            dict(category='coupon', type='A', qty=1, price=5),
            dict(vat=21, category='barcode', qty=5, price=6.99),
            dict(vat=6, category='barcode', qty=3, price=1.89),
            dict(vat=0, category='barcode', qty=2, price=10.00),
        ],
    )
    expected_vat = dict(
        highvalue=21.0,
        hightotal=26.49,
        highamount=4.6,
        lowvalue=6.0,
        lowtotal=5.02,
        lowamount=0.28,
        zerovalue=0.0,
        zerototal=17.69,
        zeroamount=0.0,
    )

    result = {
        key: round(value, 2)
        for key, value in SaleSchema.calculate_vat(data, vat_settings).items()
    }
    assert result == expected_vat


@pytest.mark.parametrize(
    'original,rounded',
    [
        (1.01, 1.00),
        (1.02, 1.00),
        (1.03, 1.05),
        (1.04, 1.05),
        (1.05, 1.05),
        (1.06, 1.05),
        (1.07, 1.05),
        (1.08, 1.10),
        (1.09, 1.10),
        (1.10, 1.10),
        (-1.01, -1.00),
        (-1.02, -1.00),
        (-1.03, -1.05),
        (-1.04, -1.05),
        (-1.05, -1.05),
        (-1.06, -1.05),
        (-1.07, -1.05),
        (-1.08, -1.10),
        (-1.09, -1.10),
        (-1.10, -1.10),
    ],
)
def test_round(original, rounded):
    assert round_to_05(original) - rounded < THRESHOLD


@pytest.mark.parametrize(
    'paid,amount,change,difference',
    [
        # tenant wins
        (1, 0.99, 0.0, 0.01),
        # tenant loses
        (1, 0.97, 0.05, -0.02),
        # NOTE the following are technically impossible, cannot pay less than
        # required. However the calculations should still hold up.
        # tenant wins
        (1, 1.09, -0.1, 0.01),
        # tenant loses
        (1, 1.07, -0.05, -0.02),
    ],
)
def test_change_difference(paid, amount, change, difference):
    data = defaultdict(
        float,
        {'totalPaid': paid, 'totalAmount': amount, 'payments': defaultdict(float)},
    )
    result = SaleSchema.calculate_change_and_difference(data, round=True)

    assert (
        round(result['change'], 2) == change
        and round(result['difference'], 2) == difference
    )


@pytest.mark.parametrize(
    'original,expected',
    [
        ({'id': 50}, None),
        ({'id': '32'}, None),
        ({'id': '255'}, None),
        ({'id': '33'}, {'id': '33'}),
        ({'id': '254'}, {'id': '254'}),
    ],
)
def test_shop_id(original, expected):
    if expected is None:
        with pytest.raises(ValidationError):
            ShopSchema(only=('id',)).load(original)
    else:
        assert ShopSchema(only=('id',)).load(original) == expected


@pytest.mark.parametrize(
    'original',
    [
        {'price': 50, 'type': 'C'},
        {'price': 50, 'type': ' '},
        {'value': 50, 'type': 'U'},
        {'value': 50, 'type': 'I'},
        {'value': 50, 'type': 'I'},
        {'value': 50, 'type': 'A '},
    ],
)
def test_price_value_bad(original):
    with pytest.raises(ValidationError):
        CouponItem(only=('type', 'price', 'value')).load(original)


@pytest.mark.parametrize(
    'original',
    [
        {'value': 50, 'type': 'C'},
        {'value': 50, 'type': ' '},
        {'price': 50, 'type': 'U'},
        {'price': 50, 'type': 'I'},
        {'price': 50, 'type': 'I'},
        {'price': 50, 'type': 'A'},
    ],
)
def test_price_value(original):
    try:
        CouponItem(only=('type', 'price', 'value')).load(original)
    except ValidationError as e:
        pytest.fail("Unexpected ValidationError: " + str(e))


def test_brand_none():
    data = BarcodeItem(only=('brand',)).load({'brand': None})
    assert data['brand'] == ''


def test_device():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale_without_device.json')) as f:
        data = json.loads(f.read())

    user_id = ObjectId()
    d = SaleSchema(context={'tenant_id': '1', 'user_info': {'_id': user_id}}).load(data)
    assert d['device'] == str(user_id)


def test_withdrawel_totals():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_withdrawel.json')) as f:
        data = json.loads(f.read())
    d = SaleSchema(context={'tenant_id': '1'}).load(data)
    assert all(
        [
            d[k] == v
            for k, v in dict(
                totalAmount=0.0,
                totalStoreCreditPaid=0.0,
                totalNumber=0.0,
                totalPaid=-1.5,
                totalCoupon=0.0,
                totalDiscountCoupon=0.0,
            ).items()
        ]
    )


def test_withdrawel_query():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_withdrawel.json')) as f:
        data = json.loads(f.read())
    d = SaleSchema(context={'tenant_id': '1'}).load(data)
    queries = SaleSchema.generate_fpqueries(d)
    assert len(queries) == 1 and queries[0][0] == 'sendorder'
    assert queries[0][1] == (
        'sendorder/warehouse__51/posid__00000/cashier__Nazli/'
        'refid__51%2D149%2D11117/withdrawel__150/'
        'withdrawelreason__5.%20Brand%20store%20benodigdheden/cash__%2D150'
    )


query_test_data = [
    (
        'example_sale_floating_point',
        'sendorder',
        (
            'sendorder/warehouse__50/refid__50%2D12%2D19677/cashier__Mylene/'
            'change__800/difference__%2D1/couponDiscount__0/'
            'storecreditused__true/scpaid__0/'
            'barcode__7613137906379/qty__%2D1/price__1200/'
            'barcode__7613137906379/qty__%2D1/price__1200/'
            'barcode__7610604011475/qty__%2D1/price__797/'
            'barcode__7610604011475/qty__%2D1/price__796/'
            'barcode__7613137906379/qty__1/price__1200/'
            'barcode__7613137906379/qty__1/price__1200/'
            'barcode__7610604011475/qty__1/price__797/'
            'barcode__7610604011475/qty__1/price__796'
        ),
    ),
    (
        'example_sale',
        'sendorder',
        (
            'sendorder/warehouse__50/refid__50%2D12%2D19677/'
            'cashier__Mylene/change__3000/difference__2/'
            'couponDiscount__10.0/'
            'cash__10000/storecreditused__true/scpaid__0/'
            'barcode__000698032678%3A1/qty__1/price__2624/'
            'barcode__000698032677%3A1/qty__1/price__4373'
        ),
    ),
    (
        'example_sale_pin',
        'sendorder',
        (
            'sendorder/warehouse__50/refid__50%2D12%2D19677/'
            'cashier__Mylene/change__3002/difference__0/'
            'couponDiscount__10.0/'
            'pin__10000/vpay__10000/storecreditused__true/scpaid__0/'
            'barcode__000698032678%3A1/qty__1/price__2624/'
            'barcode__000698032677/qty__1/price__4373'
        ),
    ),
    (
        'example_sale_pin_uncoupled',
        'sendorder',
        (
            'sendorder/warehouse__50/refid__50%2D12%2D19677/'
            'cashier__Mylene/change__3002/difference__0/'
            'couponDiscount__10.0/'
            'pin__10000/storecreditused__true/scpaid__0/'
            'barcode__000698032678%3A1/qty__1/price__2624/'
            'barcode__000698032677/qty__1/price__4373'
        ),
    ),
    (
        'example_sale_with_redeem',
        'redeemcoupon',
        (
            'redeemcoupon/warehouse__51/refid__51%2D4755%2D572/'
            'couponid__kadobon/value__99900'
        ),
    ),
    (
        'example_sale_with_storecredit',
        'paystorecredit',
        'paystorecredit/uuid__e00403c2%2Dcf05%2D4812%2D8f27%2D8478162ebb9a/'
        'value__600.0',
    ),
    (
        'example_sale_with_add',
        'addcoupon',
        ('addcoupon/coupontype__T/couponid__NZF5OR070ORSR/value__4001'),
    ),
    (
        'example_sale_with_creditreceipt',
        'sendorder',
        (
            'sendorder/warehouse__50/refid__50%2D12%2D19677/'
            'cashier__Mylene/change__1000/difference__0/'
            'couponDiscount__10.0/'
            'storecreditused__true/scpaid__0/creditreceipt__%2D10000/'
            'barcode__000698032678%3A1/qty__%2D1/price__5500/'
            'barcode__000698032677/qty__%2D1/price__5500'
        ),
    ),
    (
        'example_sale_with_creditreceipt_and_new_coupon',
        'sendorder',
        (
            'sendorder/warehouse__50/refid__50%2D12%2D19677/'
            'cashier__Mylene/change__11499/difference__0/'
            'couponDiscount__10.0/'
            'storecreditused__true/scpaid__0/creditreceipt__499/'
            'barcode__000698032678%3A1/qty__%2D1/price__5500/'
            'barcode__000698032677/qty__%2D1/price__5500'
        ),
    ),
]


@pytest.mark.parametrize('filename,method,expected', query_test_data)
def test_sendorder_query(filename, method, expected):
    with open(os.path.join(EXAMPLE_SALES_DIR, filename + '.json')) as f:
        data = json.loads(f.read())

    d = SaleSchema(context={'tenant_id': '1'}).load(data)

    query = None
    for m, q in SaleSchema.generate_fpqueries(d):
        if m == method:
            query = q
            break
    assert query and query == expected


def test_sendorder_query_order():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale_with_redeem.json')) as f:
        data = json.loads(f.read())

    d = SaleSchema(context={'tenant_id': '1'}).load(data)
    queries = SaleSchema.generate_fpqueries(d)
    assert 'sendorder' == queries[0][0]
    assert 'redeemcoupon' == queries[1][0]


def test_two_add_coupons_query():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale_with_add.json')) as f:
        data = json.loads(f.read())
    data['coupon'] = [data['coupon'], {'id': 'abcdef', 'value': 41.00, 'type': 'C'}]
    data = SaleSchema(context={'tenant_id': '1'}).load(data)
    queries = SaleSchema.generate_fpqueries(data)
    assert (
        queries[1][1] == 'addcoupon/coupontype__T/couponid__NZF5OR070ORSR/value__4001'
    )
    assert queries[2][1] == 'addcoupon/coupontype__C/couponid__abcdef/value__4100'


def test_close_consignment_query():
    with open(
        os.path.join(EXAMPLE_SALES_DIR, 'example_sale_close_consignment.json')
    ) as f:
        data = json.loads(f.read())
    data['link'] = {'type': 'consignment', 'id': 'abc', 'comment': '50-12-C19677'}
    data = SaleSchema(context={'tenant_id': '1'}).load(data)
    query = SaleSchema.generate_fpqueries(data)
    q = (
        'sendorder/warehouse__50/refid__50%2D12%2D19677/discountreason__somereason/'
        'cashier__Mylene/uuid__9db36a35%2Dc4e9%2D4a3d%2Da430%2D67c0a5339f3a/'
        'change__2000/'
        'difference__2/couponDiscount__0/cash__10000/storecreditused__true/scpaid__0/'
        'cancelcons__50%2D12%2DC19677/barcode__000698032678/qty__1/price__2999/'
        'barcode__000698032677/qty__1/price__4999'
    )
    assert query[0] == ('sendorder', q)


def test_get_next_receiptNr(database):
    """test getting the next receipt number for a specific tenant."""
    tenant_id_0 = '0'
    tenant_id_1 = '1'
    tenant_id_2 = '2'

    receiptnrs_t0 = list(range(2**32 - 10, 2**32 + 10))  # cross 32-64 bit range
    receiptnrs_t1 = random.sample(range(50, 100), 10)
    receiptnrs_t2 = random.sample(range(100, 150), 10)

    trs = [{'receiptNr': i, 'tenant_id': tenant_id_0, 'type': 2} for i in receiptnrs_t0]
    trs.extend(
        [{'receiptNr': i, 'tenant_id': tenant_id_1, 'type': 2} for i in receiptnrs_t1]
    )
    trs.extend(
        [{'receiptNr': i, 'tenant_id': tenant_id_2, 'type': 2} for i in receiptnrs_t2]
    )

    database.transactions.insert_many(trs)
    assert (
        SaleSchema.get_next_receiptnr(database, tenant_id_1) == max(receiptnrs_t1) + 1
    )


def test_get_first_receiptNr(database):
    """test getting the first receipt number for a specific tenant."""
    assert SaleSchema.get_next_receiptnr(database, '1') == 1


@pytest.mark.parametrize(
    't_type,schema', [(2, SaleSchema), (3, TransitSchema), (9, ConsignmentSchema)]
)
def test_get_next_receiptNr_from_diff_type(database, t_type, schema):
    """test getting the next receipt number for type 2."""
    tenant_id = '1'

    receiptnrs = {}
    receiptnrs[2] = random.sample(range(0, 50), 10)
    receiptnrs[3] = random.sample(range(50, 100), 10)
    receiptnrs[9] = random.sample(range(50, 100), 10)

    trs = []
    for tt in receiptnrs:
        trs.extend(
            [
                {'receiptNr': i, 'tenant_id': tenant_id, 'type': tt}
                for i in receiptnrs[tt]
            ]
        )

    database.transactions.insert_many(trs)
    assert (
        schema.get_next_receiptnr(database, tenant_id, transaction_type=t_type)
        == max(receiptnrs[t_type]) + 1
    )


def test_get_next_receiptNr_when_doesnt_exist_or_has_bad_type(database):
    database.transactions.insert_many(
        [dict(tenant_id=['123'], type=2), dict(tenant_id=['123'], type=2, receiptNr='')]
    )
    assert SaleSchema.get_next_receiptnr(database, '123') == 1


def test_shop_schema_injects_warehouse_info_from_database(database):
    shop = dict(
        city='foo',
        houseno='32',
        houseadd='bar',
        name='boo',
        street='far',
        zipcode='1234AE',
        phone='0303030303',
    )
    database.warehouses.insert_one(dict(wh='51', tenant_id=['999'], **shop))
    schema = ShopSchema(context={'db': database, 'tenant_id': '999'})
    data = schema.load({'id': '51'})
    assert data == dict(id='51', **shop)


def test_cashier_data_gets_fetched_from_database(database):
    cashier = {'name': '01', 'fullname': 'cashier'}
    database.cashiers.insert_one({'tenant_id': ['a'], '_id': '123', **cashier})
    schema = CashierSchema(context={'db': database, 'tenant_id': 'a'})
    data = schema.load({'id': '123'})
    assert data == {'id': '123', **cashier}


def test_customer_data_gets_fetched_from_database(database):
    customer = {
        '_id': '123',
        'cust_id': '456',
        'contacts': [
            {'email': 'not_primary', 'phone': 'not_primary'},
            {'email': 'mail@mail.com', 'mobile': '123456', 'primary': True},
        ],
        'first_name': 'first',
        'middle_name': 'middle',
        'last_name': 'last',
        'loyalty_no': '123',
        'points': 0,
        'title': 'ms',
    }
    database.customers.insert_one({'tenant_id': ['a'], **customer})
    schema = CustomerSchema(context={'db': database, 'tenant_id': 'a'})
    data = schema.load({'id': '123'})
    expected = {
        'id': '123',
        'custnum': '456',
        'email': 'mail@mail.com',
        'telephone': '123456',
        'firstname': 'first',
        'middlename': 'middle',
        'lastname': 'last',
        'loyaltynr': '123',
        'points': 0.0,
        'title': 'ms',
    }
    assert data == expected


def test_customer_does_not_exist(database):
    schema = CustomerSchema(context={'db': database, 'tenant_id': 'a'})
    with pytest.raises(ValidationError, match='This customer does not exist'):
        schema.load({'id': '123456'})


@pytest.mark.parametrize('email', ['', None])
def test_customer_can_have_empty_or_none_email(email):
    data = CustomerSchema(only=['email']).load({'email': email})
    assert data == {'email': email}


def test_consignment_should_have_customer():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_open_consignment.json')) as f:
        c_data = json.loads(f.read())
    c_data['customer'] = {}
    with pytest.raises(ValidationError) as e:
        ConsignmentSchema(context={'tenant_id': '123'}).load(c_data)
    assert 'Missing data' in e.value.messages['customer']['id'][0]


def test_close_consignment_with_sale(database):
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_open_consignment.json')) as f:
        c_data = json.loads(f.read())
    database.transactions.insert_one(c_data)
    database.customers.insert_one(
        {'_id': UUID('9db36a35-c4e9-4a3d-a430-67c0a5339f3a'), 'tenant_id': ['1']}
    )
    with open(
        os.path.join(EXAMPLE_SALES_DIR, 'example_sale_close_consignment.json')
    ) as f:
        s_data = json.loads(f.read())
    s_data['link'] = {'id': str(c_data['_id'])}
    data = SaleSchema(context={'tenant_id': '1', 'db': database}).load(s_data)
    assert data['link'] == {
        'id': str(c_data['_id']),
        'type': 'consignment',
        'comment': '50-12-C19677',
        'resource': 'transactions',
    }

    consignment = database.transactions.find_one({'_id': c_data['_id']})
    assert consignment['link'] == {
        'id': str(data['_id']),
        'type': 'sale',
        'comment': 'closed',
        'resource': 'transactions',
    }
    assert consignment['status'] == 'closed'


def test_close_consignment_with_consignment(database):
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_open_consignment.json')) as f:
        old_c = json.loads(f.read())
    new_c = deepcopy(old_c)
    database.transactions.insert_one(old_c)
    database.customers.insert_one(
        {'_id': UUID('9db36a35-c4e9-4a3d-a430-67c0a5339f3a'), 'tenant_id': ['1']}
    )
    new_c['link'] = {'id': str(old_c['_id'])}
    new_c['nr'] = '50-12-C19678'
    data = ConsignmentSchema(context={'tenant_id': '1', 'db': database}).load(new_c)
    assert data['link'] == {
        'id': str(old_c['_id']),
        'type': 'consignment',
        'comment': '50-12-C19677',
        'resource': 'transactions',
    }

    consignment = database.transactions.find_one({'_id': old_c['_id']})
    assert consignment['link'] == {
        'id': str(data['_id']),
        'type': 'consignment',
        'comment': 'closed',
        'resource': 'transactions',
    }
    assert consignment['status'] == 'closed'


def test_return_link(database):
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale.json')) as f:
        old_sale = json.loads(f.read())
    return_sale = deepcopy(old_sale)
    database.transactions.insert_one(old_sale)
    return_sale['link'] = {'id': str(old_sale['_id'])}
    return_sale['nr'] = '50-12-19678'

    data = SaleSchema(context={'tenant_id': '1', 'db': database}).load(return_sale)
    assert data['link'] == {
        'id': str(old_sale['_id']),
        'type': 'return',
        'comment': '50-12-19677',
        'resource': 'transactions',
    }


def test_missing_category(database):
    with open(
        os.path.join(
            EXAMPLE_SALES_DIR, 'example_sale_unspecified_receipt_category.json'
        )
    ) as f:
        sale = json.loads(f.read())

    try:
        data = SaleSchema(context={'tenant_id': '1', 'db': database}).load(sale)
    except ValidationError as e:
        pytest.fail(str(e))

    assert data['receipt'][0]['category'] == 'barcode'


def test_wrong_category(database):
    with open(
        os.path.join(EXAMPLE_SALES_DIR, 'example_sale_wrong_receipt_category.json')
    ) as f:
        sale = json.loads(f.read())

    with pytest.raises(ValidationError, match='category'):
        SaleSchema(context={'tenant_id': 1, 'db': database}).load(sale)


def test_default_nettPrice():
    schema = BaseItemSchema(only=('price', 'nettPrice'))
    data = schema.load({'price': 3.00})
    assert data['nettPrice'] == 3.00


def test_prepare_for_pdf_vat():
    data = SaleSchema.prepare_for_pdf(pdf.sale)
    assert data['vat']['high_gross_total'] == pytest.approx(108.49)
    assert data['vat']['low_gross_total'] == pytest.approx(100.00)


def test_prepare_for_pdf_total():
    data = SaleSchema.prepare_for_pdf(pdf.sale)
    assert data['totalPaid'] == pytest.approx(139.07)


def test_prepare_for_pdf_coupon_backwards_compatible():
    sale = deepcopy(pdf.sale)
    sale['coupon'] = {'id': 'YI7KVA01XRZLX', 'type': 'C', 'value': 5.65}
    data = SaleSchema.prepare_for_pdf(sale)
    assert isinstance(data['coupon'], list)


@pytest.mark.parametrize(
    'data,expected',
    [
        (pdf.data1, pdf.expected1),
        (pdf.data2, pdf.expected2),
        (pdf.data3, pdf.expected3),
        # storecredit does not count as discountable, and should not be used for
        # correcting rounding errors, plus only qty 1 should be used:
        (pdf.data4, pdf.expected4),
        (pdf.data5, pdf.expected5),  # only line discount
        (pdf.data6, pdf.expected6),  # line and total discount
    ],
)
def test_calculate_totals_and_discounts(data, expected):
    SaleSchema.calculate_totals_and_discounts(data)
    for i, item in enumerate(data['receipt']):
        assert round(data['receipt'][i]['total'], 2) == expected['receipt'][i]['total']
        if item['category'] == 'barcode':
            # round to 2, because that's how they are displayed
            assert (
                round(data['receipt'][i]['discount'], 2)
                == expected['receipt'][i]['discount']
            )
    assert data['display_discount'] == expected['display_discount']


def test_calculate_totals_and_discounts_coupons():
    data = {
        'receipt': [
            {'category': 'coupon', 'type': 'A', 'price': 1.00, 'qty': 1},
            {'category': 'coupon', 'type': 'T', 'price': 2.00, 'qty': 1},
            {'category': 'coupon', 'type': 'U', 'price': 3.00, 'qty': 1},
            {'category': 'coupon', 'type': 'I', 'price': 4.00, 'qty': 1},
            {'category': 'coupon', 'type': ' ', 'value': 5.00, 'qty': 1},
            {'category': 'coupon', 'type': 'C', 'value': 6.00, 'qty': 1},
        ],
        'totalAmount': 0.00,
        # 'totalDiscount': 11.00,
        'totalDiscountCoupon': 0.00,
        'overallReceiptDiscount': 11.00,
    }
    SaleSchema.calculate_totals_and_discounts(data)

    assert data == {
        'overallReceiptDiscount': 11.0,
        'receipt': [
            {
                'category': 'coupon',
                'type': 'A',
                'price': 1.00,
                'qty': 1,
                'total': -1.00,
            },
            {
                'category': 'coupon',
                'type': 'T',
                'price': 2.00,
                'qty': 1,
                'total': -2.00,
            },
            {
                'category': 'coupon',
                'type': 'U',
                'price': 3.00,
                'qty': 1,
                'total': -3.00,
            },
            {'category': 'coupon', 'type': 'I', 'price': 4.00, 'qty': 1, 'total': 4.00},
            {'category': 'coupon', 'type': ' ', 'value': 5.00, 'qty': 1},
            {'category': 'coupon', 'type': 'C', 'value': 6.00, 'qty': 1},
        ],
        'totalAmount': 0.00,
        'totalDiscountCoupon': 0.00,
        'display_discount': 11.00,
    }


def test_webshop_sale_with_totaldiscount():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale.json')) as f:
        data = json.loads(f.read())
        data.pop('payments')
        data['overallReceiptDiscount'] = 1

    d = SaleSchema(context={'tenant_id': '1', 'webshop': True}).load(data)
    assert d['payments'] == {
        'storecredit': 0,
        'pin': 0,
        'cash': 0,
        'creditcard': 0,
        'creditreceipt': 0,
        'couponin': 0.0,
        'withdrawel': 0.0,
        'consignment': 0.0,
        'webshop': d['totalAmount']
        - d['overallReceiptDiscount']
        - d['totalDiscountCoupon'],
    }
    assert d['change'] == 0
    assert d['difference'] == 0


def test_webshop_sale():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale.json')) as f:
        data = json.loads(f.read())
        data.pop('payments')

    d = SaleSchema(context={'tenant_id': '1', 'webshop': True}).load(data)
    assert d['payments'] == {
        'storecredit': 0,
        'pin': 0,
        'cash': 0,
        'creditcard': 0,
        'creditreceipt': 0,
        'couponin': 0.0,
        'withdrawel': 0.0,
        'consignment': 0.0,
        'webshop': d['totalAmount']
        - d['overallReceiptDiscount']
        - d['totalDiscountCoupon'],
    }
    assert d['change'] == 0
    assert d['difference'] == 0


def test_webshop_sale_with_payments():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale.json')) as f:
        data = json.loads(f.read())

    d = SaleSchema(context={'tenant_id': '1', 'webshop': True}).load(data)
    assert d['payments'] == {
        'storecredit': 0,
        'pin': 0,
        'cash': 100,
        'creditcard': 0,
        'creditreceipt': 0,
        'couponin': 0.0,
        'withdrawel': 0.0,
        'consignment': 0.0,
        'webshop': 0.0,
    }
    assert d['change'] == 30.0
    assert d['difference'] == 0.02


def test_webshop_sale_with_webshop_payment_method():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale.json')) as f:
        data = json.loads(f.read())
        data['payments'] = {'webshop': 100}

    d = SaleSchema(context={'tenant_id': '1', 'webshop': True}).load(data)
    assert d['payments'] == {
        'storecredit': 0,
        'pin': 0,
        'cash': 0,
        'creditcard': 0,
        'creditreceipt': 0,
        'couponin': 0.0,
        'withdrawel': 0.0,
        'consignment': 0.0,
        'webshop': 100,
    }
    assert d['change'] == 30.0
    assert d['difference'] == 0.02


def test_webshop_sale_defaults():
    with open(os.path.join(EXAMPLE_SALES_DIR, 'example_sale.json')) as f:
        data = json.loads(f.read())
        data.pop('device_id', None)
        data.pop('cashier', None)
    d = SaleSchema(context={'tenant_id': '1', 'webshop': True}).load(data)
    assert d['device_id'] == 'WEBSH'
    assert d['cashier']['id'] == 'WEBSHOP'
