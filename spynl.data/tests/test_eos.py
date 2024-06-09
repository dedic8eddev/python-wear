import datetime

import pytest

from spynl_schemas.eos import EOSSchema


@pytest.mark.parametrize(
    'payments, turnover, cash, electronic, other',
    [
        (
            {
                'cash': 0,
                'change': 0,
                'consignment': 0,
                'creditcard': 0,
                'creditreceipt': 0,
                'creditreceiptin': 0,
                'couponin': 0,
                'couponout': 0,
                'deposit': 0,
                'pin': 0,
                'storecredit': 0,
                'storecreditin': 0,
                'withdrawel': 0,
                'invalid': 0,
            },
            0,
            0,
            0,
            0,
        ),
        (
            {
                'cash': 0.01,
                'change': 0.02,
                'consignment': 0.04,
                'creditcard': 0.08,
                'creditreceipt': 0.16,
                'creditreceiptin': 0.32,
                'couponin': 0.64,
                'couponout': 1.28,
                'deposit': 2.56,
                'pin': 5.12,
                'storecredit': 10.24,
                'storecreditin': 20.48,
                'withdrawel': 40.96,
                'invalid': 81.92,
            },
            35.75,
            38.39,
            5.20,
            -7.84,
        ),
        (
            {
                'cash': -0.01,
                'change': -0.02,
                'consignment': -0.04,
                'creditcard': -0.08,
                'creditreceipt': -0.16,
                'creditreceiptin': -0.32,
                'couponin': -0.64,
                'couponout': -1.28,
                'deposit': -2.56,
                'pin': -5.12,
                'storecredit': -10.24,
                'storecreditin': -20.48,
                'withdrawel': -40.96,
                'invalid': -81.92,
            },
            -35.75,
            -38.39,
            -5.20,
            7.84,
        ),
        (
            {
                'cash': 0.011111,
                'change': 0,
                'consignment': 0,
                'creditcard': 0,
                'creditreceipt': 0,
                'creditreceiptin': 0,
                'couponin': 0,
                'couponout': 0,
                'deposit': 0,
                'pin': 0,
                'storecredit': 0,
                'storecreditin': 0,
                'withdrawel': 0,
                'invalid': 0,
            },
            0.01,
            0.01,
            0,
            0,
        ),
    ],
)
def test_turnover_calculation(payments, turnover, cash, electronic, other):

    # Invalid is ignored because it is invalid. Consignment is ignored because it has
    # turnover: None.

    # calculated_turnover = EOSSchema().calculate_turnover(data, type)

    assert EOSSchema().calculate_turnover({'final': payments}) == turnover
    assert EOSSchema().calculate_turnover({'final': payments}, 'cash') == cash
    assert (
        EOSSchema().calculate_turnover({'final': payments}, 'electronic') == electronic
    )
    assert EOSSchema().calculate_turnover({'final': payments}, 'other') == other


@pytest.mark.parametrize(
    'data, difference',
    [
        (
            {
                'final': {
                    'cash': 0.01,
                    'change': 0.02,
                    'consignment': 0.04,
                    'creditcard': 0.08,
                    'creditreceipt': 0.16,
                    'creditreceiptin': 0.32,
                    'couponin': 0.64,
                    'couponout': 1.28,
                    'deposit': 2.56,
                    'pin': 5.12,
                    'storecredit': 10.24,
                    'storecreditin': 20.48,
                    'withdrawel': 40.96,
                    'invalid': 81.92,
                },
                'original': {
                    'cash': 0.01,
                    'change': 0.01,
                    'consignment': 0.01,
                    'creditcard': 0.01,
                    'creditreceipt': 0.01,
                    'creditreceiptin': 0.01,
                    'couponin': 0.01,
                    'couponout': 0.01,
                    'deposit': 0.01,
                    'pin': 0.01,
                    'storecredit': 0.01,
                    'storecreditin': 0.01,
                    'withdrawel': 0.01,
                    'invalid': 0.01,
                },
            },
            35.69,
        ),
        (
            {
                'final': {
                    'cash': 0.01,
                    'change': 0.02,
                    'consignment': 0.04,
                    'creditcard': 0.08,
                    'creditreceipt': 0.16,
                    'creditreceiptin': 0.32,
                    'couponin': 0.64,
                    'couponout': 1.28,
                    'deposit': 2.56,
                    'pin': 5.12,
                    'storecredit': 10.24,
                    'storecreditin': 20.48,
                    'withdrawel': 40.96,
                    'invalid': 81.92,
                },
                'original': {
                    'cash': 0,
                    'change': 0,
                    'consignment': 0,
                    'creditcard': 0,
                    'creditreceipt': 0,
                    'creditreceiptin': 0,
                    'couponin': 0,
                    'couponout': 0,
                    'deposit': 0,
                    'pin': 0,
                    'storecredit': 0,
                    'storecreditin': 0,
                    'withdrawel': 0,
                    'invalid': 0,
                },
            },
            35.75,
        ),
        (
            {
                'original': {
                    'cash': 0.01,
                    'change': 0.02,
                    'consignment': 0.04,
                    'creditcard': 0.08,
                    'creditreceipt': 0.16,
                    'creditreceiptin': 0.32,
                    'couponin': 0.64,
                    'couponout': 1.28,
                    'deposit': 2.56,
                    'pin': 5.12,
                    'storecredit': 10.24,
                    'storecreditin': 20.48,
                    'withdrawel': 40.96,
                    'invalid': 81.92,
                },
                'final': {
                    'cash': 0,
                    'change': 0,
                    'consignment': 0,
                    'creditcard': 0,
                    'creditreceipt': 0,
                    'creditreceiptin': 0,
                    'couponin': 0,
                    'couponout': 0,
                    'deposit': 0,
                    'pin': 0,
                    'storecredit': 0,
                    'storecreditin': 0,
                    'withdrawel': 0,
                    'invalid': 0,
                },
            },
            -35.75,
        ),
        (
            {
                'original': {
                    'cash': 0.01111111,
                    'change': 0,
                    'consignment': 0,
                    'creditcard': 0,
                    'creditreceipt': 0,
                    'creditreceiptin': 0,
                    'couponin': 0,
                    'couponout': 0,
                    'deposit': 0,
                    'pin': 0,
                    'storecredit': 0,
                    'storecreditin': 0,
                    'withdrawel': 0,
                    'invalid': 0,
                },
                'final': {
                    'cash': 0,
                    'change': 0,
                    'consignment': 0,
                    'creditcard': 0,
                    'creditreceipt': 0,
                    'creditreceiptin': 0,
                    'couponin': 0,
                    'couponout': 0,
                    'deposit': 0,
                    'pin': 0,
                    'storecredit': 0,
                    'storecreditin': 0,
                    'withdrawel': 0,
                    'invalid': 0,
                },
            },
            -0.01,
        ),
    ],
)
def test_difference_calculation_with_all_payment_methods(data, difference):
    calc_difference = EOSSchema().calculate_difference(data)
    # Invalid is ignored because it is invalid. Consignment is ignored because it has
    # turnover: None.
    assert calc_difference == difference


def test_default_period_start():
    eos = {
        'shop': {'id': '44', 'name': 'Amsterdam'},
        'cashier': {'id': '44'},
        'device': {'id': '1'},
        'deposit': 200,
        'expectedCashInDrawer': 0,
        'totalCashInDrawer': 4,
    }
    data = EOSSchema(context={'user_id': 1, 'tenant_id': '1'}).load(eos)
    assert isinstance(data['periodStart'], datetime.datetime)


def test_fpquery(database):
    eos = {
        'shop': {'id': '44', 'name': 'Amsterdam'},
        'cashier': {'id': '44'},
        'device': {'id': '1'},
        'periodStart': '2019-05-04T00:00+0000',
        'periodEnd': '2019-05-04T23:59+0000',
        'deposit': 200,
        'expectedCashInDrawer': 0,
        'totalCashInDrawer': 4,
        'final': {
            'abc': 50,
            'xyz': 0,
            'change': 0,
            'couponin': 25,
            'couponout': 0,
            'storecreditin': 0,
            'creditreceiptin': 2,
            'withdrawel': 5,
            'deposit': 1,
        },
        'original': {
            'abc': 0,
            'xyz': 0,
            'change': 0,
            'couponin': 0,
            'couponout': 0,
            'storecreditin': 0,
            'creditreceiptin': 0,
        },
        'status': 'completed',
        'edited': False,
        'cycleID': '1',
        'shift': '1',
    }

    schema = EOSSchema(context={'db': database, 'user_id': 1, 'tenant_id': '1'})
    data = schema.load(eos)
    assert schema.generate_fpqueries(data) == [
        (
            'seteod',
            'seteod/warehouse__44/posid__1/periodstart__2019%2D05%2D04%2002%3A00%3A00'
            '/periodend__2019%2D05%2D05%2001%3A59%3A00/cash__0/change__0'
            '/consignment__0/couponin__2500/couponout__0/creditcard__0'
            '/creditreceipt__200/deposit__20000/miscelaneous__2700/pin__0'
            '/storecredit__0/storedebit__0/withdrawel__400/difference__400'
            '/openningbalance__0/closingbalance__0/turnover__3100',
        )
    ]


def test_reset_fpqueries(database):
    eos = {
        'shop': {'id': '44', 'name': 'Amsterdam'},
        'periodStart': datetime.datetime(2019, 5, 4, 0, 0),
    }
    assert EOSSchema().generate_reset_fpqueries(eos) == [
        ('reseteod', 'reseteod/shopid__44/date__20190504')
    ]


@pytest.mark.parametrize('status', ['completed', 'rectification', 'generated'])
def test_vat(status, database):
    database.transactions.insert_many(
        [
            {
                'shift': '-1',
                'tenant_id': ['1'],
                'type': 2,
                'vat': {'highamount': 0, 'zeroamount': 0, 'lowamount': 10},
            },
            {
                'shift': '-1',
                'tenant_id': ['1'],
                'type': 2,
                'vat': {'highamount': 2, 'zeroamount': 1, 'lowamount': 20},
            },
            {
                'shift': '-1',
                'tenant_id': ['1'],
                'type': 2,
                'vat': {'highamount': 1, 'zeroamount': 0, 'lowamount': 0},
            },
            {
                'shift': '-1',
                'tenant_id': ['1'],
                'type': 2,
                'vat': {'highamount': 0, 'zeroamount': 5, 'lowamount': 0},
            },
            {
                'shift': '-1',
                'tenant_id': ['1'],
                'type': 2,
                'vat': {'highamount': 0, 'zeroamount': 0, 'lowamount': 0},
            },
            {
                'shift': '-2',
                'tenant_id': ['1'],
                'type': 2,
                'vat': {'highamount': 100, 'zeroamount': 100, 'lowamount': 100},
            },
        ]
    )
    eos = {
        'shop': {'id': '44', 'name': 'Amsterdam'},
        'cashier': {'id': '44'},
        'device': {'id': '1'},
        'cycleID': '-1',
        'shift': '1',
        'periodStart': '2019-01-01T00:00+0000',
        'status': status,
    }
    schema = EOSSchema(context={'db': database, 'user_id': 1, 'tenant_id': '1'})
    data = schema.load(eos)
    if status == 'completed':
        assert data['vat'] == {'highAmount': 3, 'lowAmount': 30, 'zeroAmount': 6}
        assert data['periodStart'] < data['periodEnd']
    elif status == 'rectification':
        assert data['periodStart'] == data['periodEnd']
    else:
        assert data['vat'] == {}


def test_prepare_for_pdf():
    eos = {
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
        'final': {'cash': 200, 'change': 12},
    }
    assert EOSSchema.prepare_for_pdf(eos) == {
        'cashInDrawer': {
            0.01: 0,
            0.02: 0,
            0.05: 0,
            0.1: 1,
            0.2: 0,
            0.5: 0,
            1: 4,
            2: 0,
            5: 0,
            10: 1,
            20: 0,
            50: 0,
            100: 4,
            200: 0,
            500: 10,
        },
        'final': {'cash': 200, 'change': 12, 'net_cash': 188},
        'print_modified_headers': True,
    }
