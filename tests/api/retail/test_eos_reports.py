"""Tests for eos reports."""
import random
import uuid
from collections import defaultdict, namedtuple
from datetime import datetime, timedelta, timezone
from itertools import groupby

import pytest
from bson import ObjectId
from marshmallow import ValidationError
from pyramid.testing import DummyRequest

from spynl.main.dateutils import date_format_str

from spynl.api.auth.testutils import mkuser
from spynl.api.retail.eos_reports import (
    AGGREGATED,
    GROUPS,
    EOSReportsAggSchema,
    EOSReportsFilterSchema,
    aggregate_eos_json,
    get_eos_filters,
)
from spynl.api.retail.resources import EOS

Tenant = namedtuple('Tenant', 'id, cashiers, shops')
Shop = namedtuple('Shop', 'name, device_names')

TENANT_ID = '12345'
USER_ID = ObjectId()

TENANTS = [
    Tenant(
        TENANT_ID,
        ['John', 'Jan'],
        [Shop('Amsterdam', ['D1', 'D2']), Shop('Utrecht', ['D3', 'D4'])],
    ),
    Tenant('foo', [ObjectId()], [Shop('Breda', ['D1', 'D2', 'D3', 'D4'])]),
]


# reference for the keys that included in the result of the key 'totals' in endpoint's
# response
TOTAL_FIELDS = {
    'cash',
    'change',
    'couponin',
    'couponout',
    'creditreceiptin',
    'creditcard',
    'deposit',
    'pin',
    'consignment',
    'storecredit',
    'storecreditin',
    'withdrawel',
    'creditreceipt',
    'difference',
    'bankDeposit',
    'endBalance',
    'openingBalance',
    'turnover',
}


def make_relative_dates(*nums):
    """Return datetimes relative to today(start of day)."""
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return [today + timedelta(days=num) for num in nums]


def spynl_strftime(val):
    """Return datetime's strftime according to spynl's format."""
    return val.strftime(date_format_str())


def spynl_strptime(val):
    """Return datetime according to spynl's format."""
    return datetime.strptime(val, date_format_str())


def eos_doc_factory(
    num, cashier, tenant_id, shop, device_name, status='generated', randomize=False
):
    """Return a new eos document with sample eos data."""
    # assign to all number fields the same value for easier testing
    period_start = make_relative_dates(-num)[0]
    period_end = period_start + timedelta(hours=5)
    if randomize:
        amount = random.choice(range(1, 100))
    else:
        amount = num

    return {
        'created': {'date': period_end, 'user': {'_id': USER_ID}},
        # periodStart is earlier than when the document is created/saved
        'periodStart': period_start,
        'periodEnd': period_end,
        'tenant_id': [tenant_id],
        'device': {'name': device_name, 'id': device_name},
        'shop': {'name': shop.name, 'id': '51'},
        'cashier': {'fullname': cashier, 'id': '1'},
        'cycleID': uuid.uuid4().hex,
        'status': status,
        'difference': amount,
        'deposit': amount,
        'endBalance': amount,
        'openingBalance': amount,
        'turnover': amount,
        'final': {
            'cash': amount,
            'change': amount,
            'deposit': amount,
            'couponin': amount,
            'couponout': amount,
            'creditreceiptin': amount,
            'creditcard': amount,
            'consignment': amount,
            'storecredit': amount,
            'storecreditin': amount,
            'withdrawel': amount,
            'creditreceipt': amount,
            'pin': amount,
        },
        'active': True,
    }


@pytest.fixture
def setup_data(spynl_data_db):
    spynl_data_db.pymongo_db.eos.insert_many(
        [
            eos_doc_factory(days_before, cashier, tenant.id, shop, device_name)
            for tenant in TENANTS
            for shop in tenant.shops
            for device_name in shop.device_names
            # pretend that each user works on each tenant's shop
            for cashier in tenant.cashiers
            for days_before in range(1, 5)
        ]
    )


@pytest.fixture
def request_(spynl_data_db):
    """Prepare and return a dummy request for spynl needs."""

    class SpynlDummyRequest(DummyRequest):
        def __init__(self, *args, **kwargs):
            kwargs['requested_tenant_id'] = TENANTS[0].id
            kwargs.setdefault('json_body', {})
            kwargs.setdefault('args', kwargs['json_body'])
            super().__init__(*args, **kwargs)

        @property
        def json_payload(self):
            return self.json_body

    SpynlDummyRequest.db = spynl_data_db
    SpynlDummyRequest.session_or_token_id = '123456'
    return SpynlDummyRequest


@pytest.fixture
def setup_accounts(db):
    db.tenants.insert_one({'_id': TENANT_ID, 'active': True, 'applications': ['pos']})
    mkuser(db, 'a_user', 'pwd', [TENANT_ID], tenant_roles={TENANT_ID: ['pos-device']})


def test_excel_eos_report(app, setup_data, setup_accounts):
    app.get('/login', {'username': 'a_user', 'password': 'pwd'}, status=200)
    payload = {
        'groups': ['device', 'periodStart'],
        'columnMetadata': {
            'change': {'type': 'number', 'decimals': 2, 'label': 'wisselgeld'}
        },
    }
    app.post_json('/eos/report-excel', payload, status=200)


def test_excel_eos_report_no_data(app, setup_data, setup_accounts):
    app.get('/login', {'username': 'a_user', 'password': 'pwd'}, status=200)
    payload = {'filter': {'device': ['does_not_exist']}}
    app.post_json('/eos/report-excel', payload, status=400)


def test_excel_with_filter(app, setup_data, setup_accounts):
    """test added for bug"""
    app.get('/login', {'username': 'a_user', 'password': 'pwd'}, status=200)
    payload = {
        'groups': ['device', 'periodStart'],
        'columnMetadata': {
            'change': {'type': 'number', 'decimals': 2, 'label': 'wisselgeld'}
        },
        'filter': {'location': ['Amsterdam']},
    }
    app.post_json('/eos/report-excel', payload, status=200)


def test_tenant_id_ends_up_in_filter():
    """when no other filter values are given"""
    data = EOSReportsAggSchema(context={'tenant_id': '1'}).load({})
    data = EOSReportsAggSchema.build_query(data)
    assert data[0]['$match']['tenant_id'] == {'$in': ['1']}


def test_filter_schema_maps_keys_to_correct_database_fields():
    filter_before = {'cashier': ['a cashier'], 'location': ['foo'], 'device': ['bar']}
    filter_after = {
        'cashier.fullname': {'$in': filter_before['cashier']},
        'shop.name': {'$in': filter_before['location']},
        'device.name': {'$in': filter_before['device']},
    }
    assert EOSReportsFilterSchema().load(filter_before) == filter_after


def test_eos_schema_start_and_end_dates_use_spynl_format():
    start, end = '2018-01-25T00:00:00+0000', '2018-01-25T23:59:59+0000'
    expected = {'$gte': spynl_strptime(start), '$lte': spynl_strptime(end)}
    filter_ = dict(startDate=start, endDate=end)
    data = EOSReportsAggSchema().load(dict(filter=filter_))
    pipeline = EOSReportsAggSchema.build_query(data)
    period_end = pipeline[0]['$match']['periodEnd']
    assert period_end == expected


@pytest.mark.parametrize(
    'group_by',
    ['cashier', 'location', 'device', 'dow', 'day', 'week', 'month', 'year', 'shift'],
)
def test_eos_schema_accepts_specified_groups(group_by):
    assert EOSReportsAggSchema().load(dict(groups=[group_by]))


def test_eos_schema_rejects_unknown_group():
    with pytest.raises(ValidationError):
        EOSReportsAggSchema(only=('groups',)).load(dict(groups=['foo']))


def test_eos_aggregation_without_groups_that_totals_are_correct(
    setup_data, request_, spynl_data_db
):
    """Totals should be sum of tenant's eos docs."""
    # 2 shops, 2 devices per shop, 2 users per shop, (1+2+3+4) from 4 days
    totals = {k: 80 for k in TOTAL_FIELDS}
    response = aggregate_eos_json(EOS(), request_(json_body=dict(fields=TOTAL_FIELDS)))
    assert response['totals'] == totals


def test_eos_aggregation_with_period_group(setup_data, request_, spynl_data_db):
    """Totals should be sum of tenant's eos docs."""
    # 2 shops, 2 devices per shop, 2 users per shop, (1+2+3+4) from 4 days
    response = aggregate_eos_json(
        EOS(),
        request_(
            json_body={'fields': TOTAL_FIELDS, 'groups': ['periodStart', 'periodEnd']}
        ),
    )
    assert response['totals'] == {
        **{k: 80 for k in TOTAL_FIELDS},
        'periodStart': '',
        'periodEnd': '',
    }
    for i in response['data']:
        i.pop('periodStart')
        i.pop('periodEnd')
    assert sorted(response['data'], key=lambda d: d['cash']) == sorted(
        GROUPED_BY_SHIFT_EXPECTED, key=lambda d: d['cash']
    )


def test_eos_aggregation_with_shift_group(setup_data, request_, spynl_data_db):
    """Totals should be sum of tenant's eos docs."""
    # 2 shops, 2 devices per shop, 2 users per shop, (1+2+3+4) from 4 days
    response = aggregate_eos_json(
        EOS(), request_(json_body={'fields': TOTAL_FIELDS, 'groups': ['shift']})
    )
    assert response['totals'] == {**{k: 80 for k in TOTAL_FIELDS}, 'shift': ''}
    for i in response['data']:
        assert 'shift' in i
    assert len(response['data']) == spynl_data_db.eos.count_documents(
        {'tenant_id': TENANTS[0].id}
    )


@pytest.mark.parametrize(
    'groups',
    [('cashier',), ('cashier', 'device')],  # single group by  # multiple groups
)
def test_eos_aggregation_with_groups_that_totals_are_correct(
    setup_data, request_, spynl_data_db, groups
):
    """Totals should be sum of tenant's eos docs, no matter the groups applied."""
    # 2 shops, 2 devices per shop, 2 users per shop, (1+2+3+4) from 4 days
    totals = {k: 80 for k in TOTAL_FIELDS}
    totals.update({g: "" for g in groups})
    response = aggregate_eos_json(
        EOS(), request_(json_body=dict(groups=groups, fields=TOTAL_FIELDS))
    )
    assert response['totals'] == totals


@pytest.mark.parametrize(
    'group_by, expected',
    [
        ('cashier', 2),  # 2 cashiers for the used tenant
        ('location', 2),  # 2 shops for the used tenant
        ('device', 4),  # 4 devices in total owned by the used tenant
    ],
)
def test_eos_aggregation_grouping_by_user_or_shop_or_device(
    setup_data, request_, group_by, expected
):
    # include all results for convenience
    four_days_ago = make_relative_dates(-4)[0]
    payload = dict(groups=[group_by], startDate=spynl_strftime(four_days_ago))
    response = aggregate_eos_json(EOS(), request_(json_body=payload))
    # using set to ensure the uniqueness in grouped results
    ids = set(doc[group_by] for doc in response['data'])
    assert len(ids) == expected


def test_eos_aggregation_with_multiple_groups_that_their_ids_is_correct(
    setup_data, request_
):
    response = aggregate_eos_json(
        EOS(), request_(json_body=dict(groups=['cashier', 'location']))
    )
    sorted_response = sorted(
        response['data'], key=lambda d: (d['cashier'], d['location'])
    )

    def sort(list_of_dicts):
        return sorted(list_of_dicts, key=lambda d: (d['cashier'], d['location']))

    expected = sorted(
        [
            {'cashier': cashier, 'location': shop.name}
            for cashier in TENANTS[0].cashiers
            for shop in TENANTS[0].shops
        ],
        key=lambda d: (d['cashier'], d['location']),
    )

    for a, b in zip(expected, sorted_response):
        assert set(a.values()) <= set(b.values())


def test_eos_aggregation_with_multiple_groups_that_their_values_are_correct(
    setup_data, request_
):
    response = aggregate_eos_json(
        EOS(),
        request_(json_body={'groups': ['cashier', 'location'], 'fields': TOTAL_FIELDS}),
    )
    # each user for the last 4 days made 1 eos in each shop(according to test data)
    # reminder: eos yesterday has values set to 1, day before yesterday values are set
    # to 2 and so on..So expected values of fields for each group should be:
    # 4(days) * (1, 2, 3, 4) = 20 per group
    expected = {k: 20 for k in TOTAL_FIELDS}
    assert all(
        {k: v for k, v in result.items() if k not in ['cashier', 'location']}
        == expected
        for result in response['data']
    )


def test_eos_aggregation_grouping_by_day_of_week_totals_are_correct(
    spynl_data_db, setup_data, request_
):
    # all results from all 4 days for convenience
    four_days_ago = make_relative_dates(-4)[0]
    payload = dict(groups=['dow'], startDate=spynl_strftime(four_days_ago))
    resp_before = aggregate_eos_json(EOS(), request_(json_body=payload))

    # add one eos that happened 2 days ago
    cashier = TENANTS[0].cashiers[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]
    new_eos = eos_doc_factory(2, cashier, tenant_id, shop, device_name)
    spynl_data_db.pymongo_db.eos.insert_one(new_eos)

    resp_after = aggregate_eos_json(EOS(), request_(json_body=payload))
    totals_before_plus_two = {
        k: v if isinstance(v, str) else v + 2 for k, v in resp_before['totals'].items()
    }
    assert resp_after['totals'] == totals_before_plus_two


def test_eos_aggregation_grouping_by_day_of_week_data_are_correct(
    spynl_data_db, setup_data, request_
):
    cashier = TENANTS[0].cashiers[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]
    new_eos = eos_doc_factory(2, cashier, tenant_id, shop, device_name)

    # all results from all 4 days for convenience
    four_days_ago = make_relative_dates(-4)[0]
    payload = dict(groups=['dow'], startDate=spynl_strftime(four_days_ago))
    resp_before = aggregate_eos_json(EOS(), request_(json_body=payload))

    def get_aggregated_result(response):
        """Return the aggregated result that has new_eos's periodStart date."""
        for doc in response['data']:
            week = (new_eos['periodStart'].isoweekday() + 1) % 7
            if doc['dow'] == str(week or 7):  # week might be 0 cause 7%7
                return doc

    aggregated_before = get_aggregated_result(resp_before)

    # add now the new eos that happened 2 days ago
    spynl_data_db.pymongo_db.eos.insert_one(new_eos)
    resp_after = aggregate_eos_json(EOS(), request_(json_body=payload))
    aggregated_after = get_aggregated_result(resp_after)

    aggregated_before_plus_two = {
        k: v if isinstance(v, str) else v + 2 for k, v in aggregated_before.items()
    }
    assert aggregated_after == aggregated_before_plus_two


def test_eos_aggregation_grouping_by_day_totals_are_correct(
    spynl_data_db, setup_data, request_
):
    # all results from all 4 days for convenience
    four_days_ago = make_relative_dates(-4)[0]
    payload = dict(groups=['day'], startDate=spynl_strftime(four_days_ago))
    resp_before = aggregate_eos_json(EOS(), request_(json_body=payload))

    # add one eos that happened 2 days ago
    cashier = TENANTS[0].cashiers[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]
    new_eos = eos_doc_factory(2, cashier, tenant_id, shop, device_name)
    spynl_data_db.pymongo_db.eos.insert_one(new_eos)

    resp_after = aggregate_eos_json(EOS(), request_(json_body=payload))

    totals_before_plus_two = {
        k: v if isinstance(v, str) else v + 2 for k, v in resp_before['totals'].items()
    }
    assert resp_after['totals'] == totals_before_plus_two


def test_eos_aggregation_grouping_by_day_data_are_correct(
    spynl_data_db, setup_data, request_
):
    cashier = TENANTS[0].cashiers[0]
    tenant_id = TENANTS[0].id
    shop = TENANTS[0].shops[0]
    device_name = shop.device_names[0]
    new_eos = eos_doc_factory(2, cashier, tenant_id, shop, device_name)

    # all results from all 4 days for convenience
    four_days_ago = make_relative_dates(-4)[0]
    payload = dict(groups=['day'], startDate=spynl_strftime(four_days_ago))
    resp_before = aggregate_eos_json(EOS(), request_(json_body=payload))

    def get_aggregated_result(response):
        """Return the aggregated result that has new_eos's periodStart date."""
        for doc in response['data']:
            if doc['day'] == str(new_eos['periodStart'].date()):
                return doc

    aggregated_before = get_aggregated_result(resp_before)

    # add now the new eos that happened 2 days ago
    spynl_data_db.pymongo_db.eos.insert_one(new_eos)
    resp_after = aggregate_eos_json(EOS(), request_(json_body=payload))
    aggregated_after = get_aggregated_result(resp_after)

    aggregated_before_plus_two = {
        k: v if isinstance(v, str) else v + 2 for k, v in aggregated_before.items()
    }
    assert aggregated_after == aggregated_before_plus_two


@pytest.mark.parametrize('group_by', ['month', 'year'])
def test_eos_aggregation_grouping_by_month_or_year_that_sum_of_data_is_same_as_totals(
    spynl_data_db, setup_data, request_, group_by
):
    """Their sum should be the same as the totals from the response."""
    # all results from all 4 days for convenience
    four_days_ago = make_relative_dates(-4)[0]
    payload = dict(groups=[group_by], startDate=spynl_strftime(four_days_ago))
    response = aggregate_eos_json(EOS(), request_(json_body=payload))
    totals_from_data = defaultdict(int)
    for result in response['data']:
        for key, val in result.items():
            if isinstance(val, str):
                continue
            totals_from_data[key] += val
    assert totals_from_data == {
        k: v for k, v in response['totals'].items() if not isinstance(v, str)
    }


def test_eos_aggregation_by_providing_date_period(setup_data, request_, spynl_data_db):
    """Should return results for the given period."""
    yesterday, day_before_yesterday = make_relative_dates(-1, -2)
    payload = {
        'filter': {
            'startDate': spynl_strftime(day_before_yesterday + timedelta(hours=5)),
            'endDate': spynl_strftime(yesterday + timedelta(hours=5)),
        },
        'fields': TOTAL_FIELDS,
    }
    response = aggregate_eos_json(EOS(), request_(json_body=payload))
    # reminder: yesterday means one eos with all values set to 1 and day before
    #           yesterday means one eos with keys set to 2(see how the data were setup
    #           for the tests)
    # reminder: 2 shops, 2 devices per shop, 2 users per shop, (1+2) from last 2 days
    totals = {key: 24 for key in TOTAL_FIELDS}
    assert response['totals'] == totals


def test_eos_aggregation_filtering_by_pos(setup_data, request_):
    """Should return results for yesterday and the day before yesterday."""
    yesterday, day_before_yesterday = make_relative_dates(-1, -2)
    payload = {
        'filter': {
            'startDate': spynl_strftime(day_before_yesterday + timedelta(hours=5)),
            'endDate': spynl_strftime(yesterday + timedelta(hours=5)),
        },
        'fields': TOTAL_FIELDS,
    }
    response = aggregate_eos_json(EOS(), request_(json_body=payload))
    # reminder: yesterday means one eos with all values set to 1 and day before
    #           yesterday means one eos with values set to 2
    # reminder: 2 shops, 2 devices per shop, 2 users per shop, (1+2) from last 2 days
    expected_response = {
        'totals': {key: 24 for key in TOTAL_FIELDS},
        'data': [{key: 24 for key in TOTAL_FIELDS}],
    }
    assert response == expected_response


def test_getting_eos_filters(setup_data, request_, spynl_data_db):
    """Ensure returns the expected result."""
    eos_docs = list(spynl_data_db.eos.find({'tenant_id': {'$in': [TENANTS[0].id]}}))
    expected = {
        'groups': GROUPS,
        'filter': {
            'user': [dict(value=doc['created']['user']['_id']) for doc in eos_docs],
            'location': [dict(value=doc['shop']['name']) for doc in eos_docs],
            'device': [dict(value=doc['device']['name']) for doc in eos_docs],
        },
        'fields': AGGREGATED,
    }
    response = get_eos_filters(EOS(), request_())
    assert response['data'].keys() == expected.keys()


def test_sort(spynl_data_db):
    spynl_data_db.pymongo_db.eos.insert_many(
        [
            eos_doc_factory(
                days_before, cashier, tenant.id, shop, device_name, randomize=True
            )
            for tenant in TENANTS
            for shop in tenant.shops
            for device_name in shop.device_names
            # pretend that each user works on each tenant's shop
            for cashier in tenant.cashiers
            for days_before in range(1, 5)
            for _ in range(5)
        ]
    )
    payload = {
        'groups': ['cashier', 'location'],
        'fields': ['creditcard'],
        'sort': [
            {'field': 'location', 'direction': -1},
            {'field': 'creditcard', 'direction': 1},
        ],
    }
    data = EOSReportsAggSchema().load(payload)
    pipeline = EOSReportsAggSchema.build_query(data)
    result = list(spynl_data_db.eos.aggregate(pipeline))

    sorted_field = []
    sorted_group = []
    for k, g in groupby(result[0]['data'], key=lambda r: r['location']):
        sorted_field.append([row['creditcard'] for row in g])
        sorted_group.append(k)

    # assert that sorting does not change (because it's already sorted correctly)
    assert sorted(sorted_group, reverse=True) == sorted_group
    assert all(sorted(row) == row for row in sorted_field)


GROUPED_BY_SHIFT_EXPECTED = [
    {
        'bankDeposit': 16,
        'cash': 16,
        'change': 16,
        'consignment': 16,
        'couponin': 16,
        'couponout': 16,
        'creditcard': 16,
        'creditreceipt': 16,
        'creditreceiptin': 16,
        'deposit': 16,
        'difference': 16,
        'endBalance': 16,
        'openingBalance': 16,
        'pin': 16,
        'storecredit': 16,
        'storecreditin': 16,
        'turnover': 16,
        'withdrawel': 16,
    },
    {
        'bankDeposit': 32,
        'cash': 32,
        'change': 32,
        'consignment': 32,
        'couponin': 32,
        'couponout': 32,
        'creditcard': 32,
        'creditreceipt': 32,
        'creditreceiptin': 32,
        'deposit': 32,
        'difference': 32,
        'endBalance': 32,
        'openingBalance': 32,
        'pin': 32,
        'storecredit': 32,
        'storecreditin': 32,
        'turnover': 32,
        'withdrawel': 32,
    },
    {
        'bankDeposit': 24,
        'cash': 24,
        'change': 24,
        'consignment': 24,
        'couponin': 24,
        'couponout': 24,
        'creditcard': 24,
        'creditreceipt': 24,
        'creditreceiptin': 24,
        'deposit': 24,
        'difference': 24,
        'endBalance': 24,
        'openingBalance': 24,
        'pin': 24,
        'storecredit': 24,
        'storecreditin': 24,
        'turnover': 24,
        'withdrawel': 24,
    },
    {
        'bankDeposit': 8,
        'cash': 8,
        'change': 8,
        'consignment': 8,
        'couponin': 8,
        'couponout': 8,
        'creditcard': 8,
        'creditreceipt': 8,
        'creditreceiptin': 8,
        'deposit': 8,
        'difference': 8,
        'endBalance': 8,
        'openingBalance': 8,
        'pin': 8,
        'storecredit': 8,
        'storecreditin': 8,
        'turnover': 8,
        'withdrawel': 8,
    },
]


def test_sort_2(spynl_data_db):
    spynl_data_db.pymongo_db.eos.insert_many(
        [
            eos_doc_factory(
                days_before, cashier, tenant.id, shop, device_name, randomize=True
            )
            for tenant in TENANTS
            for shop in tenant.shops
            for device_name in shop.device_names
            # pretend that each user works on each tenant's shop
            for cashier in tenant.cashiers
            for days_before in range(1, 5)
            for _ in range(5)
        ]
    )
    payload = {
        'groups': ['cashier', 'location'],
        'fields': ['creditcard'],
        'sort': [
            {'field': 'location', 'direction': -1},
            {'field': 'creditcard', 'direction': 1},
        ],
    }
    data = EOSReportsAggSchema().load(payload)
    pipeline = EOSReportsAggSchema.build_query(data)
    result = list(spynl_data_db.eos.aggregate(pipeline))

    sorted_field = []
    sorted_group = []
    for k, g in groupby(result[0]['data'], key=lambda r: r['location']):
        sorted_field.append([row['creditcard'] for row in g])
        sorted_group.append(k)

    # assert that sorting does not change (because it's already sorted correctly)
    assert sorted(sorted_group, reverse=True) == sorted_group
    assert all(sorted(row) == row for row in sorted_field)
