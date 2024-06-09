import os
import re

import pytest

from spynl.api.auth.testutils import mkuser

from spynl.services.reports.article_status import COLUMNS, CUSTOMER
from spynl.services.reports.retail_customer_sales import (
    RetailCustomerFilterQuery,
    RetailCustomerSalesQuery,
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def test_retail_customer_filter(postgres_cursor):
    s = RetailCustomerFilterQuery(context={'tenant_id': '1'})
    data = s.load({})
    query = s.to_query(data).as_string(postgres_cursor)

    pattern = re.compile(r'DISTINCT \'([^\']*)\'')
    queried_columns = pattern.findall(query)

    alias_type = {c.alias: c.report_type for c in COLUMNS}
    assert all(CUSTOMER in alias_type[c] for c in queried_columns)

    expected = {
        'articleDescription',
        'customerCountry',
        'size',
        'color',
        'Reference',
        'warehouse',
        'brand',
        'customerEmail',
        'colorCode',
        'collection',
        'colorFamily',
        'customerGroup3',
        'customerGroup1',
        'customerGroup2',
        'articleGroup1',
        'articleGroup2',
        'articleGroup3',
        'articleGroup4',
        'articleGroup5',
        'articleGroup6',
        'articleGroup7',
        'articleGroup8',
        'articleGroup9',
    }
    assert expected == set(queried_columns)


def test_to_query_customer_sales(postgres_cursor):
    data = RetailCustomerSalesQuery(context={'tenant_id': '1'}).load(
        {
            'fields': ['endingStock', 'averageStock', 'soldItems'],
            'groups': ['supplier', 'customerName'],
            'filter': {
                'tenant_id': 1,
                'brand': ['nike'],
                'warehouse': ['Amsterdam', 'Haarlem'],
                'startDate': '1970-01-01T00:00:01+0000',
                'endDate': '1970-01-01T00:00:04+0000',
            },
            'sort': [{'field': 'soldItems', 'direction': -1}],
        }
    )

    query = RetailCustomerSalesQuery.to_query(data).as_string(postgres_cursor)

    pattern = re.compile(
        r'SELECT (?P<outer_select>.*) FROM \( '
        r'SELECT (?P<inner_select>.*)'
        r'FROM "transactions" '
        r'WHERE (?P<where>.*)'
        r'GROUP BY(?P<group_by>.*)\) as "inner" '
        r'ORDER BY(?P<order>.*)'
    )
    matches = pattern.search(query)
    assert matches
    assert set(matches['outer_select'].strip().split(', ')) == {
        '(1.0 * "n_stock" * 3 + "n_diffX") / 3 as "averageStock"',
        '"supplier" as "supplier"',
        '"cname" as "customerName"',
        '"n_stock" + "n_recieved" + "n_transit" + "n_change" - "n_sold" '
        '- "n_presold" as "endingStock"',
        '"n_sold" as "soldItems"',
    }

    assert set(matches['inner_select'].strip().split(', ')) == {
        '"supplier"',
        '"cname"',
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_presold" else 0 end) as "n_presold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_recieved" else 0 end) as "n_recieved"'
        ),
        (
            'sum(case when "timestamp" >= 946684800 and "timestamp" <= 1 then '
            '"n_stock" else 0 end) as "n_stock"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_sold" else 0 end) as "n_sold"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_transit" else 0 end) as "n_transit"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '("n_recieved" + "n_transit" + "n_change" - "n_sold") * '
            '(4 - "timestamp") else 0 end) as "n_diffX"'
        ),
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then '
            '"n_change" else 0 end) as "n_change"'
        ),
    }
    assert set(matches['where'].strip().split(' AND ')) == {
        '"brand" IN (\'nike\')',
        '"warehouse" IN (\'Amsterdam\', \'Haarlem\')',
        '"tenant" IN (1)',
        '"trtype" IN (2, 95)',
        '"timestamp" >= 1',
        '"timestamp" <= 4',
    }
    assert set(matches['group_by'].strip().split(', ')) == {'"supplier"', '"cname"'}
    assert set(matches['order'].strip().split(', ')) == {
        '"supplier" ASC',
        '"customerName" ASC',
        '"soldItems" DESC',
    }


@pytest.fixture()
def setup_db(db, app):
    db.tenants.insert_one(
        {
            '_id': '91537',
            'applications': ['dashboard'],
            'settings': {
                'logoUrl': {
                    'medium': 'file://{}/examples/square_logo.png'.format(BASE_DIR)
                }
            },
            'name': 'Testing Tenant',
            'addresses': [
                {
                    'address': 'street street 1',
                    'zipcode': '1000 AB',
                    'city': 'The City',
                    'country': 'Nederland',
                    'primary': True,
                }
            ],
        }
    )

    mkuser(
        db,
        'reports_user',
        'bla',
        ['91537'],
        language='nl-nl',
        tenant_roles={'91537': ['dashboard-report_user']},
    )
    app.post_json('/login', {'username': 'reports_user', 'password': 'bla'})
    yield
    app.get('/logout')


def test_retail_customer_sales_filter(app, setup_db):
    app.post_json('/reports/retail-customer-sales-filter', {}, status=200)


def test_retail_customer_sales(app, setup_db):
    payload = {
        'fields': ['amountVAT', 'amountSold', 'amountSoldExVAT'],
        'filter': {'startDate': '2019-01-01T00:00Z', 'endDate': '2021-01-01T00:00Z'},
    }
    response = app.post_json('/reports/retail-customer-sales', payload, status=200)
    assert response.json_body == {
        'data': [{'amountSold': 408.24, 'amountSoldExVAT': 374.52, 'amountVAT': 33.72}],
        'status': 'ok',
        'totals': {'amountSold': 408.24, 'amountSoldExVAT': 374.52, 'amountVAT': 33.72},
    }
