import datetime
import os
import re
import sys

import pytest
from marshmallow import ValidationError, fields

from spynl.api.auth.testutils import mkuser

from spynl.services.reports.article_status import (
    ARTICLE,
    COLUMNS,
    LOWER_TO_CAMEL,
    ArticleStatusFilterQuery,
    ArticleStatusQuery,
    CollectionSchema,
    FilterSchema,
    SortSchema,
    revert_back_to_camelcase,
)


def test_revert_back_to_camelcase():
    result = [
        {
            'brand': 'Nike',
            'articlecode': '123123',
            'customgroupby': 123,
            'solditems': 100,
        }
    ]
    assert revert_back_to_camelcase(result, LOWER_TO_CAMEL) == [
        {
            'brand': 'Nike',
            'articleCode': '123123',
            'customGroupBy': 123,
            'soldItems': 100,
        }
    ]


def test_revert_back_to_camelcase_redundant():
    result = [
        {
            'brand': 'Nike',
            'articleCode': '123123',
            'customGroupBy': 123,
            'soldItems': 100,
        }
    ]
    assert revert_back_to_camelcase(result, LOWER_TO_CAMEL) == [
        {
            'brand': 'Nike',
            'articleCode': '123123',
            'customGroupBy': 123,
            'soldItems': 100,
        }
    ]


def test_collection_schema():
    result = CollectionSchema().load(["summer-18", "winter-00"], many=True)
    assert result == [
        {'season': 'summer', '_year': '18'},
        {'season': 'winter', '_year': '00'},
    ]


def test_collection_schema_invalid():
    with pytest.raises(ValidationError):
        CollectionSchema().load(["summer2018", "-2000"], many=True)


def test_start_end_date():
    schema = FilterSchema(context={'tenant_id': '1'}, only=('startDate', 'endDate'))
    result = schema.load(
        {'startDate': '2018-09-01T14:00+0200', 'endDate': '2018-09-02T12:00+0000'}
    )
    assert result == {
        'startDate': datetime.datetime.strptime(
            '2018-09-01T12:00+0000', '%Y-%m-%dT%H:%M%z'
        ),
        'endDate': datetime.datetime.strptime(
            '2018-09-02T12:00+0000', '%Y-%m-%dT%H:%M%z'
        ),
    }


def test_start_end_date_invalid():
    schema = FilterSchema(context={'tenant_id': '1'}, only=('startDate', 'endDate'))
    with pytest.raises(ValidationError, match='startDate must be before endDate'):
        schema.load(
            {'startDate': '2018-09-02T12:00+0000', 'endDate': '2018-09-01T14:00+0200'}
        )


def test_sort():
    schema = SortSchema(many=True)
    result = schema.load(
        [{'field': 'brand', 'direction': -1}, {'field': 'supplier', 'direction': 1}]
    )
    assert result == [('brand', 'DESC'), ('supplier', 'ASC')]


def test_sort_invalid():
    schema = SortSchema(many=True)
    # twice not a valid choice
    with pytest.raises(ValidationError, match="Must be one of"):
        schema.load([{'field': 'a', 'direction': 2}])


def test_implicit_sort():
    schema = ArticleStatusQuery(context={'tenant_id': '1'})
    payload = {
        'groups': ['warehouse', 'supplier', 'articleCode'],
        'fields': ['mutation'],
        'filter': {
            'startDate': '2018-08-01T00:00:00+0200',
            'endDate': '2018-09-30T00:00:00+0200',
        },
        'sort': [{'field': 'supplier', 'direction': -1}],
    }
    data = schema.load(payload)
    assert SortSchema.build_implicit_sort(data['sort'], data['groups']) == [
        ('supplier', 'DESC'),
        ('articleCode', 'ASC'),
        ('warehouse', 'ASC'),
    ]


def test_to_query(postgres_cursor):
    data = ArticleStatusQuery(context={'tenant_id': '1'}).load(
        {
            'salesOnly': True,
            'fields': ['endingStock', 'averageStock', 'soldItems'],
            'groups': ['supplier', 'company'],
            'filter': {
                'tenant_id': 1,
                'brand': ['nike'],
                'warehouse': ['Amsterdam', 'Haarlem'],
                'startDate': '1970-01-01T00:00:01+0000',
                'endDate': '1970-01-01T00:00:04+0000',
            },
            'sort': [
                {'field': 'company', 'direction': 1},
                {'field': 'soldItems', 'direction': -1},
            ],
        }
    )

    query = ArticleStatusQuery.to_query(data).as_string(postgres_cursor)

    pattern = re.compile(
        r'SELECT (?P<outer_select>.*) FROM \( '
        r'SELECT (?P<inner_select>.*)'
        r'FROM "transactions" '
        r'WHERE (?P<where>.*)'
        r'GROUP BY(?P<group_by>.*)\) as "inner" WHERE "n_sold" != 0  '
        r'ORDER BY(?P<order>.*)'
    )
    matches = pattern.search(query)
    assert matches
    assert set(matches['outer_select'].strip().split(', ')) == {
        '(1.0 * "n_stock" * 3 + "n_diffX") / 3 as "averageStock"',
        '"supplier" as "supplier"',
        '"n_stock" + "n_recieved" + "n_transit" + "n_change" - "n_sold" - "n_presold" '
        'as "endingStock"',
        '"n_sold" as "soldItems"',
        '"tenantname" as "company"',
    }

    assert set(matches['inner_select'].strip().split(', ')) == {
        '"supplier"',
        '"tenantname"',
        (
            'sum(case when "timestamp" >= 1 and "timestamp" <= 4 then "n_presold" '
            'else 0 end) as "n_presold"'
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
    }
    assert set(matches['group_by'].strip().split(', ')) == {
        '"supplier"',
        '"tenantname"',
    }
    assert set(matches['order'].strip().split(', ')) == {
        '"supplier" ASC',
        '"soldItems" DESC',
        '"company" ASC',
    }


def test_article_status_filter(postgres_cursor):
    s = ArticleStatusFilterQuery(context={'tenant_id': '1'})
    data = s.load({})
    query = s.to_query(data).as_string(postgres_cursor)

    pattern = re.compile(r'DISTINCT \'([^\']*)\'')
    queried_columns = pattern.findall(query)

    alias_type = {c.alias: c.report_type for c in COLUMNS}
    assert all(ARTICLE in alias_type[c] for c in queried_columns)

    expected = {
        'agent',
        'articleCode',
        'articleDescription',
        'articleGroup1',
        'articleGroup2',
        'articleGroup3',
        'articleGroup4',
        'articleGroup5',
        'articleGroup6',
        'articleGroup7',
        'articleGroup8',
        'articleGroup9',
        'brand',
        'collection',
        'color',
        'colorCode',
        'colorFamily',
        'company',
        'set',
        'size',
        'supplier',
        'warehouse',
    }

    assert expected == set(queried_columns)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))


@pytest.fixture()
def setup_db(db, app):
    db.tenants.insert_one(
        {
            '_id': '91537',
            'applications': ['dashboard'],
            'retail': True,
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


def test_article_status_filter_via_app(app, setup_db):
    response = app.post_json('/reports/article-status-filter', {}, status=200)
    assert response.json['data']['fields'] == [
        'receivings',
        'receivingsAmount',
        'soldItems',
        'amountSold',
        'amountSoldExVAT',
        'endingStock',
        'endingStockAmount',
        'costPrice',
        'mutation',
        'mutationAmount',
        'consignmentAmount',
        'consignmentItems',
        'stockAmount',
        'startingStock',
        'transitsAmount',
        'transits',
        'averageStockAmount',
        'averageStock',
        'turnOverVelocityCount',
        'turnOverVelocityAmount',
        'selloutPercentage',
        'margin',
        'startMargin',
        'profitability',
        'netProfit',
        'returnOnInvestment',
        'maxTurnover',
        'leakage',
        'discount',
        'bought',
        'boughtAmount',
        'revalue',
        'lastReceived',
    ]


def test_latest_date(app, setup_db):
    resp = app.post('/reports/latest-data').json
    try:
        fields.DateTime().deserialize(resp['data']['latestDate'])
    except ValidationError:
        pytest.fail('bad data')


def test_json_return_empty_list(app, setup_db):
    """the json endpoint should return an empty list if there is no data"""
    payload = {
        'filter': {
            'articleCode': ['does not exist'],
            'startDate': '2000-05-06T22:00:00.000Z',
            'endDate': '2030-04-30T21:59:59.999Z',
        },
        'fields': ['margin'],
        'groups': ['articleCode'],
    }
    result = app.post_json('/reports/article-status', payload, status=200)
    assert result.json == {'data': [], 'totals': [], 'status': 'ok'}


def test_json(app, setup_db):
    response = app.post_json('/reports/article-status', PAYLOAD, status=200)
    assert response.json == {
        'data': [
            {
                'amountSoldExVAT': 499.36,
                'articleCode': "bccard's",
                'averageStock': -7.27,
                'averageStockAmount': -214.48,
                'brand': 'Diesel',
                'costPrice': 236.0,
                'discount': 0.02,
                'endingStock': -8.0,
                'endingStockAmount': -236.0,
                'lastReceived': None,
                'leakage': 0.0,
                'margin': 52.74,
                'mutation': 0.0,
                'mutationAmount': 0.0,
                'netProfit': 263.36,
                'profitability': -122.79,
                'receivings': 0.0,
                'receivingsAmount': 0.0,
                'selloutPercentage': 0.0,
                'soldItems': 8.0,
                'startMargin': 52.74,
                'startingStock': 0.0,
                'stockAmount': 0.0,
                'supplier': 'Diesel',
                'transits': 0.0,
                'transitsAmount': 0.0,
                'turnOverVelocityAmount': -0.1,
                'turnOverVelocityCount': -0.1,
            }
        ],
        'status': 'ok',
        'totals': {
            'amountSoldExVAT': 499.36,
            'articleCode': '',
            'averageStock': -7.27049975729784,
            'averageStockAmount': -214.47974284028626,
            'brand': '',
            'costPrice': 236.0,
            'discount': 0.0161467889908256,
            'endingStock': -8.0,
            'endingStockAmount': -236.0,
            'lastReceived': None,
            'leakage': 0.0032333921222809934,
            'margin': 52.73950656840756,
            'mutation': 0.0,
            'mutationAmount': 0.0,
            'netProfit': 263.36,
            'profitability': -122.79015095430842,
            'receivings': 0.0,
            'receivingsAmount': 0.0,
            'selloutPercentage': 0.0,
            'soldItems': 8.0,
            'startMargin': 52.73950656840756,
            'startingStock': 0.0,
            'stockAmount': 0.0,
            'supplier': '',
            'transits': 0.0,
            'transitsAmount': 0.0,
            'turnOverVelocityAmount': -0.10010543659231284,
            'turnOverVelocityCount': -0.10010543659231284,
        },
    }


def test_json_filter_sales(app, setup_db):
    response = app.post_json(
        '/reports/article-status', {**PAYLOAD, 'salesOnly': True}, status=200
    )
    assert response.json == {
        'data': [
            {
                'amountSoldExVAT': 499.36,
                'articleCode': "bccard's",
                'averageStock': -7.27,
                'averageStockAmount': -214.48,
                'brand': 'Diesel',
                'costPrice': 236.0,
                'discount': 0.02,
                'endingStock': -8.0,
                'endingStockAmount': -236.0,
                'lastReceived': None,
                'leakage': 0.0,
                'margin': 52.74,
                'mutation': 0.0,
                'mutationAmount': 0.0,
                'netProfit': 263.36,
                'profitability': -122.79,
                'receivings': 0.0,
                'receivingsAmount': 0.0,
                'selloutPercentage': 0.0,
                'soldItems': 8.0,
                'startMargin': 52.74,
                'startingStock': 0.0,
                'stockAmount': 0.0,
                'supplier': 'Diesel',
                'transits': 0.0,
                'transitsAmount': 0.0,
                'turnOverVelocityAmount': -0.1,
                'turnOverVelocityCount': -0.1,
            }
        ],
        'status': 'ok',
        'totals': {
            'amountSoldExVAT': 499.36,
            'articleCode': '',
            'averageStock': '',
            'averageStockAmount': '',
            'brand': '',
            'costPrice': 236.0,
            'discount': '',
            'endingStock': '',
            'endingStockAmount': '',
            'lastReceived': '',
            'leakage': '',
            'margin': 52.73950656840756,
            'mutation': '',
            'mutationAmount': '',
            'netProfit': 263.36,
            'profitability': '',
            'receivings': '',
            'receivingsAmount': '',
            'selloutPercentage': '',
            'soldItems': 8.0,
            'startMargin': '',
            'startingStock': '',
            'stockAmount': '',
            'supplier': '',
            'transits': '',
            'transitsAmount': '',
            'turnOverVelocityAmount': '',
            'turnOverVelocityCount': '',
        },
    }


def test_pdf(app, setup_db):
    app.post_json('/reports/article-status-pdf', PAYLOAD, status=200)


def test_excel(app, setup_db):
    app.post_json('/reports/article-status-excel', PAYLOAD, status=200)


@pytest.mark.parametrize(
    'format, content_type',
    [
        ('pdf', 'application/pdf'),
        ('excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
        ('csv', 'text/csv'),
    ],
)
def test_email(app, setup_db, inbox, format, content_type):
    payload = {
        **PAYLOAD,
        'recipients': ['bla@bla.com'],
        'format': format,
        'message': 'custom message',
    }
    app.post_json('/reports/article-status-email', payload, status=200)
    attachment = inbox[0].attachments[0]
    assert attachment.content_type == content_type
    assert sys.getsizeof(attachment) > 0
    assert 'custom message' in inbox[0].html.data
    assert 'Artikelstatus' in inbox[0].html.data
    assert 'reports_user' in inbox[0].html.data
    assert 'Artikelstatus' in inbox[0].subject


PAYLOAD = {
    'groups': ['brand', 'supplier', 'articleCode'],
    'fields': [
        'receivings',
        'lastReceived',
        'receivingsAmount',
        'soldItems',
        'amountSoldExVAT',
        'endingStock',
        'endingStockAmount',
        'mutation',
        'mutationAmount',
        'stockAmount',
        'startingStock',
        'transitsAmount',
        'costPrice',
        'transits',
        'averageStockAmount',
        'averageStock',
        'turnOverVelocityCount',
        'turnOverVelocityAmount',
        'selloutPercentage',
        'margin',
        'startMargin',
        'netProfit',
        'profitability',
        'leakage',
        'discount',
    ],
    'filter': {
        'startDate': '2019-05-06T22:00:00.000Z',
        'endDate': '2030-04-30T21:59:59.999Z',
    },
    'sort': [{'field': 'brand', 'direction': 1}],
    'columnMetadata': {
        'supplier': {'label': 'leverancier', 'type': 'percentage'},
        'lastReceived': {'type': 'datetime'},
        'size': {'label': 'maat'},
        'receivings': {'type': 'number'},
        'receivingsAmount': {'type': 'number'},
        'brand': {'label': 'merk', 'type': 'text'},
        'soldItems': {'label': 'verkocht', 'type': 'quantity'},
        'stockAmount': {'label': 'voorraadwaarde', 'type': 'money'},
        'turnOverVelocityCount': {'label': 'bla', 'type': 'number', 'decimals': 2},
        'startingStock': {'type': 'number'},
        'transitsAmount': {'type': 'number'},
        'costPrice': {'type': 'number'},
        'transits': {'type': 'number'},
        'averageStockAmount': {'type': 'quantity'},
        'averageStock': {'type': 'number'},
        'turnOverVelocityAmount': {'type': 'number'},
        'selloutPercentage': {'type': 'percentage'},
        'margin': {'type': 'number'},
        'netProfit': {'type': 'number'},
        'profitability': {'type': 'number'},
    },
}
