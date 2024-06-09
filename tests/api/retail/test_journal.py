import datetime
import os

import pymongo
import pytest
from bson import json_util

from spynl.api.auth.testutils import login, mkuser
from spynl.api.retail.journal import (
    FIELDS,
    GROUPS_FILTER,
    PAYMENT_METHODS,
    FloatCompare,
    Journal,
    JournalFilter,
    JournalFilterQueryFilter,
)
from spynl.api.retail.sales_reports import TURNOVER_CALCULATION

TENANT_ID = '12345'
BIG_TENANT = '1'


@pytest.fixture()
def setup_db(db):
    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['dashboard']})
    db.tenants.insert_one(
        {'_id': BIG_TENANT, 'settings': {'limit_journal_filter_timeframe': True}}
    )
    mkuser(
        db,
        'username',
        'password',
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'dashboard-user'},
    )
    db.transactions.create_index(
        [('tenant_id', pymongo.ASCENDING), ('created.date', pymongo.DESCENDING)]
    )

    # This test data contains 104 transactions with the following warehouses,
    # customers, and cashiers for tenant 12345. The transactions contain
    # different coupons and discounts.
    # {
    #     "shop": [{"name": "Utrecht", "id": "51"}, {"name": "Amsterdam", "id": "50"}],
    #     "cashier": [
    #         {"name": "cashier1", "fullname": "peter cashier", "id": "1"},
    #         {"name": "cashier2", "fullname": "doru cashier", "id": "2"},
    #         {"name": "cashier3", "fullname": "rosanne cashier", "id": "3"},
    #     ],
    #     "customer": [
    #         {"lastname": "buscemi", "loyaltynr": "1", "email": "buscemi@email.com"},
    #         {
    #             "lastname": "washington",
    #             "loyaltynr": "2",
    #             "email": "washington@email.com",
    #         },
    #     ],
    # }
    with open(
        os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'data',
            'journal_transactions.bson',
        )
    ) as f:
        db.transactions.insert_many(json_util.loads(f.read()))


def test_float_compare():
    data = FloatCompare().load({'value': 7, 'operator': 'gt'})
    assert data == {'$gt': 7.00}


def test_journal_filter_schema():
    data = JournalFilter(context={'tenant_id': '1'}).load(
        {
            'startDate': '2018-12-12T12:00',
            'endDate': '2018-12-20T12:00',
            'turnover': {'value': 7, 'operator': 'gt'},
            'docNumber': ['a'],
            'shopId': ['aaa'],
        }
    )
    assert data == {
        'created.date': {
            '$gte': datetime.datetime(2018, 12, 12, 12, 00),
            '$lte': datetime.datetime(2018, 12, 20, 12, 00),
        },
        'turnover': {'$gt': 7.00},
        'type': 2,
        'nr': {'$in': ['a']},
        'shop.id': {'$in': ['aaa']},
        'active': True,
        'tenant_id': '1',
    }


@pytest.mark.parametrize(
    'input,expected',
    [
        (
            {'discountReason': ['bla']},
            {
                '$or': [
                    {'discountreason': {'$in': ['bla']}},
                    {'discountreason.desc': {'$in': ['bla']}},
                ]
            },
        ),
        ({'paymentMethod': ['pin']}, {'payments.pin': {'$ne': 0}}),
        (
            {'paymentMethod': ['pin', 'cash']},
            {'$or': [{'payments.pin': {'$ne': 0}}, {'payments.cash': {'$ne': 0}}]},
        ),
        (
            {'paymentMethod': ['pin', 'cash'], 'discountReason': ['bla']},
            {
                '$and': [
                    {
                        '$or': [
                            {'discountreason': {'$in': ['bla']}},
                            {'discountreason.desc': {'$in': ['bla']}},
                        ]
                    },
                    {
                        '$or': [
                            {'payments.pin': {'$ne': 0}},
                            {'payments.cash': {'$ne': 0}},
                        ]
                    },
                ]
            },
        ),
    ],
)
def test_journal_filter_schema_or(input, expected):
    data = JournalFilter(context={'tenant_id': '1'}).load(input)
    for field in ['created.date', 'tenant_id', 'active', 'type']:
        data.pop(field)
    assert data == expected


def test_tenant_id_ends_up_in_filter():
    """when no other filter values are given"""
    data = Journal(context={'tenant_id': '1'}).load({'groups': {'day'}})
    assert data['filter']['tenant_id'] == '1'


def test_journal():
    data = Journal(context={'tenant_id': '1'}).load(
        {
            'filter': {
                'startDate': '2018-12-12T12:00',
                'endDate': '2018-12-20T12:00',
                'turnover': {'value': 7, 'operator': 'gt'},
                'docNumber': ['a'],
                'shopId': ['aaa'],
            },
            'sort': [{'field': 'turnover', 'direction': 1}],
            'groups': ['day', 'shopName'],
        }
    )
    assert data == {
        'fields_': [
            'storeCreditPaid',
            'turnover',
            'cash',
            'numberOfSales',
            'creditcard',
            'creditreceipt',
            'pin',
            'storeCredit',
            'totalAmount',
            'vatHigh',
            'vatLow',
            'withdrawal',
            'deposit',
            'netQty',
            'qtySold',
            'qtyReturned',
            'numberOfItemSales',
            'netQtyPerReceipt',
            'turnoverPerReceipt',
            'turnoverPerItem',
            'totalDiscountCoupon',
            'totalCashBackCoupon',
            'totalGiftVoucherInactive',
            'totalGiftVoucherActive',
            'totalCreditReceipt',
            'totalCouponAsArticle',
        ],
        'filter': {
            'created.date': {
                '$gte': datetime.datetime(2018, 12, 12, 12, 00),
                '$lte': datetime.datetime(2018, 12, 20, 12, 00),
            },
            'turnover': {'$gt': 7.00},
            'type': 2,
            'nr': {'$in': ['a']},
            'shop.id': {'$in': ['aaa']},
            'active': True,
            'tenant_id': '1',
        },
        'sort': [{'field': 'turnover', 'direction': 1}],
        'skip': 0,
        'groups': ['day', 'shopName'],
        'columnMetadata': {},
        'added_dependencies': [],
    }


def test_query():
    data = Journal(context={'tenant_id': '1'}).load(
        {
            'filter': {
                'startDate': '2018-12-12T12:00',
                'endDate': '2018-12-20T12:00',
                'turnover': {'value': 7, 'operator': 'gt'},
                'docNumber': ['a'],
                'shopId': ['aaa'],
            },
            'sort': [{'field': 'turnover', 'direction': 1}],
            'groups': ['day', 'shopName'],
        }
    )
    query = Journal.build_query(data)
    expected = [
        {
            '$match': {
                'created.date': {
                    '$gte': datetime.datetime(2018, 12, 12, 12, 00),
                    '$lte': datetime.datetime(2018, 12, 20, 12, 00),
                },
                'type': 2,
                'nr': {'$in': ['a']},
                'shop.id': {'$in': ['aaa']},
                'tenant_id': '1',
                'active': True,
            }
        },
        {
            '$addFields': {
                'qty': {
                    '$reduce': {
                        'input': '$receipt',
                        'initialValue': {'sold': 0, 'returned': 0, 'netQty': 0},
                        'in': {
                            'returned': {
                                '$add': [
                                    '$$value.returned',
                                    {
                                        '$cond': [
                                            {
                                                '$and': [
                                                    {
                                                        '$eq': [
                                                            '$$this.category',
                                                            'barcode',
                                                        ]
                                                    },
                                                    {'$lt': ['$$this.qty', 0]},
                                                ]
                                            },
                                            '$$this.qty',
                                            0,
                                        ]
                                    },
                                ]
                            },
                            'sold': {
                                '$add': [
                                    '$$value.sold',
                                    {
                                        '$cond': [
                                            {
                                                '$and': [
                                                    {
                                                        '$eq': [
                                                            '$$this.category',
                                                            'barcode',
                                                        ]
                                                    },
                                                    {'$gt': ['$$this.qty', 0]},
                                                ]
                                            },
                                            '$$this.qty',
                                            0,
                                        ]
                                    },
                                ]
                            },
                            'netQty': {
                                '$add': [
                                    '$$value.netQty',
                                    {
                                        '$cond': [
                                            {
                                                '$and': [
                                                    {
                                                        '$eq': [
                                                            '$$this.category',
                                                            'barcode',
                                                        ]
                                                    },
                                                    {'$ne': ['$$this.qty', 0]},
                                                ]
                                            },
                                            '$$this.qty',
                                            0,
                                        ]
                                    },
                                ]
                            },
                        },
                    }
                },
                'totalAmount_': {
                    '$subtract': [
                        {'$subtract': ['$totalAmount', '$overallReceiptDiscount']},
                        '$totalDiscountCoupon',
                    ]
                },
                'withdrawal': {
                    '$cond': [
                        {'$gt': ['$payments.withdrawel', 0]},
                        '$payments.withdrawel',
                        0,
                    ]
                },
                'deposit': {
                    '$cond': [
                        {'$lt': ['$payments.withdrawel', 0]},
                        {'$abs': '$payments.withdrawel'},
                        0,
                    ]
                },
                'cash': {'$subtract': ['$payments.cash', '$change']},
                'turnover': TURNOVER_CALCULATION,
            }
        },
        {
            '$addFields': {
                'numberOfItemSales': {
                    '$cond': {
                        'else': 0,
                        'if': {'$or': ['$qty.returned', '$qty.sold']},
                        'then': 1,
                    }
                }
            }
        },
        {'$match': {'turnover': {'$gt': 7.00}}},
        {
            '$group': {
                '_id': {
                    'day': {
                        '$dateToString': {'date': '$created.date', 'format': '%Y-%m-%d'}
                    },
                    'shopName': '$shop.name',
                },
                'storeCreditPaid': {'$sum': '$totalStoreCreditPaid'},
                'turnover': {'$sum': {'$subtract': ['$turnover', '$couponTotals.A']}},
                'cash': {'$sum': '$cash'},
                'numberOfSales': {'$sum': 1},
                'creditcard': {'$sum': '$payments.creditcard'},
                'creditreceipt': {'$sum': '$payments.creditreceipt'},
                'netQty': {'$sum': '$qty.netQty'},
                'qtySold': {'$sum': '$qty.sold'},
                'qtyReturned': {'$sum': '$qty.returned'},
                'pin': {'$sum': '$payments.pin'},
                'storeCredit': {'$sum': '$payments.storecredit'},
                'totalAmount': {'$sum': '$totalAmount_'},
                'vatHigh': {'$sum': '$vat.highamount'},
                'vatLow': {'$sum': '$vat.lowamount'},
                'withdrawal': {'$sum': '$withdrawal'},
                'deposit': {'$sum': '$deposit'},
                'numberOfItemSales': {'$sum': '$numberOfItemSales'},
                'totalDiscountCoupon': {'$sum': '$couponTotals. '},
                'totalCashBackCoupon': {'$sum': '$couponTotals.C'},
                'totalGiftVoucherInactive': {
                    '$sum': {'$multiply': ['$couponTotals.I', -1]}
                },
                'totalGiftVoucherActive': {'$sum': '$couponTotals.U'},
                'totalCreditReceipt': {'$sum': '$couponTotals.T'},
                'totalCouponAsArticle': {'$sum': '$couponTotals.A'},
            }
        },
        {
            '$project': {
                '_id': 0,
                'cash': '$cash',
                'creditcard': '$creditcard',
                'creditreceipt': '$creditreceipt',
                'day': '$_id.day',
                'numberOfSales': '$numberOfSales',
                'pin': '$pin',
                'netQty': '$netQty',
                'qtySold': '$qtySold',
                'qtyReturned': '$qtyReturned',
                'shopName': '$_id.shopName',
                'storeCredit': '$storeCredit',
                'storeCreditPaid': '$storeCreditPaid',
                'totalAmount': '$totalAmount',
                'totalCashBackCoupon': '$totalCashBackCoupon',
                'totalCouponAsArticle': '$totalCouponAsArticle',
                'totalCreditReceipt': '$totalCreditReceipt',
                'totalDiscountCoupon': '$totalDiscountCoupon',
                'totalGiftVoucherActive': '$totalGiftVoucherActive',
                'totalGiftVoucherInactive': '$totalGiftVoucherInactive',
                'turnover': '$turnover',
                'vatHigh': '$vatHigh',
                'vatLow': '$vatLow',
                'withdrawal': '$withdrawal',
                'deposit': '$deposit',
                'numberOfItemSales': '$numberOfItemSales',
                'netQtyPerReceipt': {
                    '$cond': {
                        'if': {'$gt': ['$numberOfItemSales', 0]},
                        'then': {'$divide': ['$netQty', '$numberOfItemSales']},
                        'else': 0,
                    }
                },
                'turnoverPerReceipt': {
                    '$cond': {
                        'if': {'$gt': ['$numberOfItemSales', 0]},
                        'then': {'$divide': ['$turnover', '$numberOfItemSales']},
                        'else': 0,
                    }
                },
                'turnoverPerItem': {
                    '$cond': {
                        'if': {'$ne': ['$netQty', 0]},
                        'then': {'$divide': ['$turnover', {'$abs': '$netQty'}]},
                        'else': 0,
                    }
                },
            }
        },
        {'$sort': {'turnover': 1}},
        {
            '$group': {
                '_id': 0,
                'cash': {'$sum': '$cash'},
                'creditcard': {'$sum': '$creditcard'},
                'creditreceipt': {'$sum': '$creditreceipt'},
                'data': {
                    '$push': {
                        'cash': '$cash',
                        'creditcard': '$creditcard',
                        'creditreceipt': '$creditreceipt',
                        'day': '$day',
                        'deposit': '$deposit',
                        'numberOfItemSales': '$numberOfItemSales',
                        'netQty': '$netQty',
                        'netQtyPerReceipt': '$netQtyPerReceipt',
                        'numberOfSales': '$numberOfSales',
                        'pin': '$pin',
                        'qtyReturned': '$qtyReturned',
                        'qtySold': '$qtySold',
                        'shopName': '$shopName',
                        'storeCredit': '$storeCredit',
                        'storeCreditPaid': '$storeCreditPaid',
                        'totalAmount': '$totalAmount',
                        'totalCashBackCoupon': '$totalCashBackCoupon',
                        'totalCouponAsArticle': '$totalCouponAsArticle',
                        'totalCreditReceipt': '$totalCreditReceipt',
                        'totalDiscountCoupon': '$totalDiscountCoupon',
                        'totalGiftVoucherActive': '$totalGiftVoucherActive',
                        'totalGiftVoucherInactive': '$totalGiftVoucherInactive',
                        'turnover': '$turnover',
                        'turnoverPerItem': '$turnoverPerItem',
                        'turnoverPerReceipt': '$turnoverPerReceipt',
                        'vatHigh': '$vatHigh',
                        'vatLow': '$vatLow',
                        'withdrawal': '$withdrawal',
                    }
                },
                'deposit': {'$sum': '$deposit'},
                'numberOfSales': {'$sum': '$numberOfSales'},
                'pin': {'$sum': '$pin'},
                'netQty': {'$sum': '$netQty'},
                'qtyReturned': {'$sum': '$qtyReturned'},
                'qtySold': {'$sum': '$qtySold'},
                'storeCredit': {'$sum': '$storeCredit'},
                'storeCreditPaid': {'$sum': '$storeCreditPaid'},
                'totalAmount': {'$sum': '$totalAmount'},
                'totalCashBackCoupon': {'$sum': '$totalCashBackCoupon'},
                'totalCouponAsArticle': {'$sum': '$totalCouponAsArticle'},
                'totalCreditReceipt': {'$sum': '$totalCreditReceipt'},
                'totalDiscountCoupon': {'$sum': '$totalDiscountCoupon'},
                'totalGiftVoucherActive': {'$sum': '$totalGiftVoucherActive'},
                'totalGiftVoucherInactive': {'$sum': '$totalGiftVoucherInactive'},
                'turnover': {'$sum': '$turnover'},
                'vatHigh': {'$sum': '$vatHigh'},
                'vatLow': {'$sum': '$vatLow'},
                'withdrawal': {'$sum': '$withdrawal'},
                'numberOfItemSales': {'$sum': '$numberOfItemSales'},
            }
        },
        {
            '$project': {
                '_id': 0,
                'data': '$data',
                'totals': {
                    'cash': '$cash',
                    'creditcard': '$creditcard',
                    'creditreceipt': '$creditreceipt',
                    'day': '',
                    'deposit': '$deposit',
                    'numberOfSales': '$numberOfSales',
                    'pin': '$pin',
                    'netQty': '$netQty',
                    'qtyReturned': '$qtyReturned',
                    'qtySold': '$qtySold',
                    'shopName': '',
                    'storeCredit': '$storeCredit',
                    'storeCreditPaid': '$storeCreditPaid',
                    'totalAmount': '$totalAmount',
                    'totalCashBackCoupon': '$totalCashBackCoupon',
                    'totalCouponAsArticle': '$totalCouponAsArticle',
                    'totalCreditReceipt': '$totalCreditReceipt',
                    'totalDiscountCoupon': '$totalDiscountCoupon',
                    'totalGiftVoucherActive': '$totalGiftVoucherActive',
                    'totalGiftVoucherInactive': '$totalGiftVoucherInactive',
                    'turnover': '$turnover',
                    'vatHigh': '$vatHigh',
                    'vatLow': '$vatLow',
                    'withdrawal': '$withdrawal',
                    'numberOfItemSales': '$numberOfItemSales',
                    'netQtyPerReceipt': {
                        '$cond': {
                            'if': {'$gt': ['$numberOfItemSales', 0]},
                            'then': {'$divide': ['$netQty', '$numberOfItemSales']},
                            'else': 0,
                        }
                    },
                    'turnoverPerReceipt': {
                        '$cond': {
                            'if': {'$gt': ['$numberOfItemSales', 0]},
                            'then': {'$divide': ['$turnover', '$numberOfItemSales']},
                            'else': 0,
                        }
                    },
                    'turnoverPerItem': {
                        '$cond': {
                            'if': {'$ne': ['$netQty', 0]},
                            'then': {'$divide': ['$turnover', {'$abs': '$netQty'}]},
                            'else': 0,
                        }
                    },
                },
            }
        },
    ]
    for a, b in zip(query, expected):
        assert a == b


def test_journal_filter_query(spynl_data_db, setup_db):
    data = JournalFilterQueryFilter(
        context={'tenant_id': TENANT_ID, 'db': spynl_data_db}
    ).load({})
    assert data == {
        'active': True,
        'tenant_id': '12345',
        'type': 2,
        'created.date': data["created.date"],
    }
    data = JournalFilterQueryFilter(
        context={'tenant_id': BIG_TENANT, 'db': spynl_data_db}
    ).load({})
    assert '$gte' in data['created.date']


def test_get_journal_filter(app, setup_db):
    login(app, 'username', 'password')
    response = app.post_json(
        '/sales/journal-filter',
        {
            'filter': {'startDate': '2000-01-01T00:00'},
        },
        status=200,
    )
    assert response.json == {
        'data': {
            'fields': FIELDS,
            'filter': {
                'cardProvider': ['maestro', 'vpay'],
                'cashierName': ['doru cashier', 'peter cashier', 'rosanne cashier'],
                'customerEmail': ['buscemi@email.com', 'washington@email.com'],
                'discountReason': [''],
                'loyaltyNr': ['1', '2'],
                'shopName': ['Amsterdam', 'Utrecht'],
                'withdrawalReason': [
                    '',
                    '5. diversen',
                    'Geen reden',
                    'Geld wisselen',
                    'Kasopmaak',
                ],
                'paymentMethod': PAYMENT_METHODS,
            },
            'groups': list(GROUPS_FILTER),
        },
        'status': 'ok',
    }


def test_get_journal(app, setup_db):
    login(app, 'username', 'password')
    response = app.post_json(
        '/sales/journal',
        {
            'filter': {'startDate': '2021-01-01T00:00', 'endDate': '2022-01-01T00:00'},
            'groups': ['shopName', 'cashierName'],
            'sort': [{'field': 'cash'}],
        },
        status=200,
    )
    assert response.json == {
        'data': [
            {
                'cash': 36.0,
                'cashierName': 'peter cashier',
                'creditcard': 0.0,
                'creditreceipt': -9.99,
                'deposit': 0,
                'netQty': -4,
                'netQtyPerReceipt': -0.5,
                'numberOfItemSales': 8,
                'numberOfSales': 12,
                'pin': 30.0,
                'qtyReturned': -16,
                'qtySold': 12,
                'shopName': 'Utrecht',
                'storeCredit': -255.14999999999995,
                'storeCreditPaid': 0.0,
                'totalAmount': -239.13999999999993,
                'totalCashBackCoupon': 0.0,
                'totalCouponAsArticle': 0.0,
                'totalCreditReceipt': 0.0,
                'totalDiscountCoupon': 0.0,
                'totalGiftVoucherActive': 0.0,
                'totalGiftVoucherInactive': -40.0,
                'turnover': -239.13999999999993,
                'turnoverPerItem': -59.78499999999998,
                'turnoverPerReceipt': -29.89249999999999,
                'vatHigh': -40.8,
                'vatLow': 0.0,
                'withdrawal': 0,
            },
            {
                'cash': 80.0,
                'cashierName': 'doru cashier',
                'creditcard': 0.0,
                'creditreceipt': 0.0,
                'deposit': 0,
                'netQty': 22,
                'netQtyPerReceipt': 1.4666666666666666,
                'numberOfItemSales': 15,
                'numberOfSales': 19,
                'pin': 355.3,
                'qtyReturned': -6,
                'qtySold': 28,
                'shopName': 'Amsterdam',
                'storeCredit': 61.480000000000004,
                'storeCreditPaid': 0.0,
                'totalAmount': 506.78000000000003,
                'totalCashBackCoupon': 0.0,
                'totalCouponAsArticle': 0.0,
                'totalCreditReceipt': 0.0,
                'totalDiscountCoupon': 0.0,
                'totalGiftVoucherActive': 10.0,
                'totalGiftVoucherInactive': 0.0,
                'turnover': 506.78000000000003,
                'turnoverPerItem': 23.035454545454545,
                'turnoverPerReceipt': 33.785333333333334,
                'vatHigh': 87.95,
                'vatLow': 0.0,
                'withdrawal': 0,
            },
            {
                'cash': 240.5,
                'cashierName': 'peter cashier',
                'creditcard': 0.0,
                'creditreceipt': 0.0,
                'deposit': 0,
                'netQty': 22,
                'netQtyPerReceipt': 1.6923076923076923,
                'numberOfItemSales': 13,
                'numberOfSales': 15,
                'pin': 541.25,
                'qtyReturned': 0,
                'qtySold': 22,
                'shopName': 'Amsterdam',
                'storeCredit': 323.27,
                'storeCreditPaid': 0.0,
                'totalAmount': 1115.02,
                'totalCashBackCoupon': 0.0,
                'totalCouponAsArticle': 10.0,
                'totalCreditReceipt': 0.0,
                'totalDiscountCoupon': 0.0,
                'totalGiftVoucherActive': 0.0,
                'totalGiftVoucherInactive': 0.0,
                'turnover': 1105.02,
                'turnoverPerItem': 50.22818181818182,
                'turnoverPerReceipt': 85.00153846153846,
                'vatHigh': 191.78,
                'vatLow': 0.0,
                'withdrawal': 0,
            },
            {
                'cash': 282.0,
                'cashierName': 'rosanne cashier',
                'creditcard': 0.0,
                'creditreceipt': 0.0,
                'deposit': 0,
                'netQty': 18,
                'netQtyPerReceipt': 1.3846153846153846,
                'numberOfItemSales': 13,
                'numberOfSales': 14,
                'pin': 377.87,
                'qtyReturned': -3,
                'qtySold': 21,
                'shopName': 'Amsterdam',
                'storeCredit': 60.55999999999999,
                'storeCreditPaid': 0.0,
                'totalAmount': 735.43,
                'totalCashBackCoupon': 0.0,
                'totalCouponAsArticle': 5.0,
                'totalCreditReceipt': 10.0,
                'totalDiscountCoupon': 0.0,
                'totalGiftVoucherActive': 0.0,
                'totalGiftVoucherInactive': 0.0,
                'turnover': 730.43,
                'turnoverPerItem': 40.57944444444444,
                'turnoverPerReceipt': 56.18692307692307,
                'vatHigh': 126.75,
                'vatLow': 0.0,
                'withdrawal': 0,
            },
            {
                'cash': 501.0,
                'cashierName': 'rosanne cashier',
                'creditcard': 0.0,
                'creditreceipt': 0.0,
                'deposit': 0,
                'netQty': 23,
                'netQtyPerReceipt': 1.5333333333333334,
                'numberOfItemSales': 15,
                'numberOfSales': 15,
                'pin': 158.7,
                'qtyReturned': -4,
                'qtySold': 27,
                'shopName': 'Utrecht',
                'storeCredit': 243.85000000000002,
                'storeCreditPaid': 0.0,
                'totalAmount': 893.55,
                'totalCashBackCoupon': 10.0,
                'totalCouponAsArticle': 0.0,
                'totalCreditReceipt': 0.0,
                'totalDiscountCoupon': 0.0,
                'totalGiftVoucherActive': 0.0,
                'totalGiftVoucherInactive': -10.0,
                'turnover': 893.55,
                'turnoverPerItem': 38.85,
                'turnoverPerReceipt': 59.57,
                'vatHigh': 155.09,
                'vatLow': 0.0,
                'withdrawal': 0,
            },
            {
                'cash': 676.89,
                'cashierName': 'doru cashier',
                'creditcard': 0.0,
                'creditreceipt': 0.0,
                'deposit': 0,
                'netQty': 28,
                'netQtyPerReceipt': 2.1538461538461537,
                'numberOfItemSales': 13,
                'numberOfSales': 15,
                'pin': 219.89,
                'qtyReturned': -2,
                'qtySold': 30,
                'shopName': 'Utrecht',
                'storeCredit': 2.6299999999999955,
                'storeCreditPaid': 0.0,
                'totalAmount': 1034.12,
                'totalCashBackCoupon': 0.0,
                'totalCouponAsArticle': 0.0,
                'totalCreditReceipt': 0.0,
                'totalDiscountCoupon': 10.0,
                'totalGiftVoucherActive': 50.0,
                'totalGiftVoucherInactive': 0.0,
                'turnover': 1034.12,
                'turnoverPerItem': 36.93285714285714,
                'turnoverPerReceipt': 79.5476923076923,
                'vatHigh': 186.4,
                'vatLow': 0.0,
                'withdrawal': 8.75,
            },
        ],
        'status': 'ok',
        'totals': {
            'cash': 1816.3899999999999,
            'cashierName': '',
            'creditcard': 0.0,
            'creditreceipt': -9.99,
            'deposit': 0,
            'netQty': 109,
            'netQtyPerReceipt': 1.4155844155844155,
            'numberOfItemSales': 77,
            'numberOfSales': 90,
            'pin': 1683.01,
            'qtyReturned': -31,
            'qtySold': 140,
            'shopName': '',
            'storeCredit': 436.64000000000004,
            'storeCreditPaid': 0.0,
            'totalAmount': 4045.7599999999998,
            'totalCashBackCoupon': 10.0,
            'totalCouponAsArticle': 15.0,
            'totalCreditReceipt': 10.0,
            'totalDiscountCoupon': 10.0,
            'totalGiftVoucherActive': 60.0,
            'totalGiftVoucherInactive': -50.0,
            'turnover': 4030.7599999999998,
            'turnoverPerItem': 36.9794495412844,
            'turnoverPerReceipt': 52.34753246753247,
            'vatHigh': 707.1700000000001,
            'vatLow': 0.0,
            'withdrawal': 8.75,
        },
    }


def test_get_journal_no_groups(app, setup_db):
    login(app, 'username', 'password')
    response = app.post_json(
        '/sales/journal',
        {
            'filter': {'startDate': '2021-01-01T00:00', 'endDate': '2022-01-01T00:00'},
        },
        status=200,
    )
    totals = {
        'cash': 1816.39,
        'creditcard': 0.0,
        'creditreceipt': -9.99,
        'deposit': 0,
        'netQty': 109,
        'netQtyPerReceipt': 1.4155844155844155,
        'numberOfItemSales': 77,
        'numberOfSales': 90,
        'pin': 1683.01,
        'qtyReturned': -31,
        'qtySold': 140,
        'storeCredit': 436.64000000000004,
        'storeCreditPaid': 0.0,
        'totalAmount': 4045.76,
        'totalCashBackCoupon': 10.0,
        'totalCouponAsArticle': 15.0,
        'totalCreditReceipt': 10.0,
        'totalDiscountCoupon': 10.0,
        'totalGiftVoucherActive': 60.0,
        'totalGiftVoucherInactive': -50.0,
        'turnover': 4030.76,
        'turnoverPerItem': 36.9794495412844,
        'turnoverPerReceipt': 52.34753246753247,
        'vatHigh': 707.17,
        'vatLow': 0.0,
        'withdrawal': 8.75,
    }
    assert response.json == {'data': [totals], 'totals': totals, 'status': 'ok'}


def test_get_journal_field_dependencies(app, setup_db):
    login(app, 'username', 'password')
    response = app.post_json(
        '/sales/journal',
        {
            'filter': {'startDate': '2021-01-01T00:00', 'endDate': '2022-01-01T00:00'},
            'groups': ['shopName', 'cashierName'],
            'fields': ['netQtyPerReceipt'],
            'sort': [{'field': 'netQtyPerReceipt'}],
        },
        status=200,
    )
    assert response.json == {
        'data': [
            {
                'cashierName': 'peter cashier',
                'netQtyPerReceipt': -0.5,
                'shopName': 'Utrecht',
            },
            {
                'cashierName': 'rosanne cashier',
                'netQtyPerReceipt': 1.3846153846153846,
                'shopName': 'Amsterdam',
            },
            {
                'cashierName': 'doru cashier',
                'netQtyPerReceipt': 1.4666666666666666,
                'shopName': 'Amsterdam',
            },
            {
                'cashierName': 'rosanne cashier',
                'netQtyPerReceipt': 1.5333333333333334,
                'shopName': 'Utrecht',
            },
            {
                'cashierName': 'peter cashier',
                'netQtyPerReceipt': 1.6923076923076923,
                'shopName': 'Amsterdam',
            },
            {
                'cashierName': 'doru cashier',
                'netQtyPerReceipt': 2.1538461538461537,
                'shopName': 'Utrecht',
            },
        ],
        'totals': {
            'cashierName': '',
            'netQtyPerReceipt': 1.4155844155844155,
            'shopName': '',
        },
        'status': 'ok',
    }


def test_get_journal_field_dependencies_no_groups(app, setup_db):
    login(app, 'username', 'password')
    response = app.post_json(
        '/sales/journal',
        {
            'filter': {'startDate': '2021-01-01T00:00', 'endDate': '2022-01-01T00:00'},
            'fields': ['netQtyPerReceipt'],
        },
        status=200,
    )
    assert response.json == {
        'data': [{'netQtyPerReceipt': 1.4155844155844155}],
        'totals': {'netQtyPerReceipt': 1.4155844155844155},
        'status': 'ok',
    }


@pytest.mark.parametrize(
    'method_filter,value',
    [(['pin'], 1683.01), (['cash'], 1845.13), (['pin', 'cash'], 3528.14)],
)
def test_journal_payment_method_filter(app, setup_db, method_filter, value):
    login(app, 'username', 'password')
    response = app.post_json(
        '/sales/journal',
        {
            'filter': {
                'startDate': '2021-01-01T00:00',
                'endDate': '2022-01-01T00:00',
                'paymentMethod': method_filter,
            },
            'fields': ['turnover'],
        },
        status=200,
    )
    assert response.json == {
        'data': [{'turnover': value}],
        'status': 'ok',
        'totals': {'turnover': value},
    }


DOC_NUMBERS = [
    '00388cc77e7949a9b341797f0d79d798',
    '006eefb6d9fa4b43b291f0d4ba7869f6',
    '0074344829d1450c9ecb401618d6dc1e',
    '08d033460fde43f7b1c3d7db9e907246',
    '0fd255371c51496f95e8bf1098f6ff37',
    '1079968705e34a0b99e7002aaa6bdb78',
    '143c5751826f44a987d59585b1d5a460',
    '16daf406544342408925505b3bbd3d50',
    '18b5c97fadd242cfb4fab2dca8ad06f5',
    '1a0a8dfcf8bc496d8660e05b5d36bf32',
    '1bdc986932514a309d5ec219125e6b50',
    '1c0182eb69e84ad4812574889995968c',
    '22306241e5d54fe5bdb8334b3b876258',
    '23fbac3682cd458884734d473fbbb7fb',
    '24444671b1284389bc566a42c346e626',
    '24daed48b1214d2093d8ae5faff11d3d',
    '26b96c2933ea4315aa97cad87df40e23',
    '2b236a15e8204f4e9bf4fcd5de8c8bd3',
    '2ded0f0192814ec5ace891f1b5cd5bae',
    '2f7e26ea99594c2084a1371d8ad0a546',
    '2ff8587b69ef4b32a9366ebca2fc0866',
    '30f27365a55e4c61a3667ba098845a08',
    '3208291c38ee4cabb55eea8affacd7f3',
    '37e10bed5c844edeb8fdc0e1da601390',
    '3b93660dcded461db9f5f9c52c80a1fc',
    '3f1978897fed4e5996a3b69da6bd2d46',
    '40ea46685a504cea8e8a5b1661bd0299',
    '42add5e711884e648043017c085f75e0',
    '4717365e3d444bec9c5f50e5ed937f94',
    '48450fba75c8490b8aefda23d7a70ac1',
    '4f5459baf0ab4417a1849aa1865cc022',
    '511c0c5fb984442086a1141c2c3cf516',
    '57e9ff8c58fc4a00beeb9f10a463c500',
    '5b2dabf0d56348bca04884d292af2102',
    '67620dce094b4704a7faa8b6ea2db915',
    '6a3352ff29cf4a0ca54df684afc6dea5',
    '6eb52a9ab8e14b0bb9a96f8cf912daa1',
    '6f9d2d5401b24fb5baf556fd0639c099',
    '786eaada9b3142abb5524613e64bfb03',
    '7bc558c6065b4073a4e09c8e9a577ea9',
    '7ca5a551ebdd4e7e98d2df90dde12bb1',
    '7dbd945b2ce04811ab1ae5ebfabfea28',
    '7f71f392d3d14d41a9f5d4dafd2c8c28',
    '809bc23234e546c2a6278a019db2d962',
    '86f15201149d456487a88262eba17198',
    '877876acbef54fa1b184fc88d0376717',
    '9276b93561b94299a0fbf3176a80a912',
    '9547602846054f1485480c77cfb477fa',
    '97906c12ac2549959acd592908cb7124',
    '98153b0c97944affad390258bc1c4eca',
    '9a43522907ea49eba6a85b7552468fda',
    '9ec738781cf5401a9a18f692f8ba71e0',
    'a0274b733b524506a75ea983848860d0',
    'a08b336bd532497e9e23ef7b80a861a8',
    'a18d56e091a641cb9a68ed34ede26c9f',
    'a1c4c1a7f4a94bb79bbc1174edf8c261',
    'a343bca9cd1f45d6b4748804ad812e20',
    'a3b8cacd2f374b78b898a5ff027f62c1',
    'a3fe85d1df2e4b56bf4540b59c333917',
    'a46c6bb94ca741bdb41706f611923a20',
    'a852adcc68f049cdabe4c21fe654bf06',
    'af3bf993a80c4406a3030bce0c47b29d',
    'b21de421d7a441249fbc85cde71025bc',
    'b3825b76a1f94853a2c8bcfc344f5a1e',
    'b3aa2b71a5834ba2a457ca7c97c29af9',
    'b68776436ea947ef82fd29c6254c436f',
    'b82c80234a094cfc8082329e4e17c059',
    'baa2de160f5d4af49861be70b240592d',
    'bd962ef5621c4d45b7302001711f4e58',
    'be66b1209b464aa0b5615af6f7ca4293',
    'bec1306da69b47518383bb72c80f7ff2',
    'c523cc86063f416f8a2f696a9d262410',
    'c715c5206e574d17854ab392047a2ce4',
    'cd39c8d46017452285a7f316e61dd9b3',
    'cd50db2b31484fd2b1f099153bb9d4ff',
    'cde608d43dbc445c9ba2c33b40d3d043',
    'ce02593632484aad8e0d4466bd57ffa5',
    'd0e274c1e7c34d3e8ed94e785511bf1b',
    'd215a043ae4946d48d9406b91e282bf4',
    'd3379101f99448cf86fdb195899b4fb8',
    'd64c2dfaaf024763b40e229d6c3e5421',
    'd8c5e706d78e4e3db96fb54bdd398469',
    'd9726349a14a4f2194d5d3c62af53193',
    'dc3e3a4d19654ad581b7cf59d938b930',
    'df9a8a28ac1a4fbf90937cca6a5b9ab0',
    'e2ef455c7aae46208fd1a4b219fe5744',
    'f216c100805c4bb1963a1818a0ea100b',
    'f8e1efa4ed7e4f2a82efc2baa313b9ba',
    'fb095321ba2f423c8581bb2d2286a5cf',
    'ffdd408bd4c143f295837a5dd6c75dfc',
]
