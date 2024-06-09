import os

import pytest

from spynl.api.auth.testutils import mkuser

from spynl.services.reports.stock import StockFilter, StockQuery

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


@pytest.fixture
def set_db(db, app):
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


def test_schema():
    loaded = StockQuery(context={'tenant_id': '1'}).load(
        {
            'sort': [{'field': 'articleGroup1', 'direction': -1}],
            'groups': ['articleGroup1'],
            'filter': {'collection': ['winter-19'], 'endDate': '2020-01-01T00:00Z'},
        }
    )
    assert loaded == {
        'history': False,
        'keep_zero_lines': False,
        'sort': [
            ('aatr1', 'DESC'),
            ('article', 'ASC'),
            ('sizeidx', 'ASC'),
            ('label', 'ASC'),
        ],
        'groups': [
            'aatr1',
            'article',
            'artnr_lev',
            'descript',
            'sizename',
            'label',
            'sizeidx',
            'n_stock',
        ],
        'filter': {
            'collection': [{'season': 'winter', '_year': '19'}],
            'tenant': [1],
            'startDate': 946684800,
            'endDate': 1577836800,
        },
        'calculate_totals': False,
    }


def test_query_no_filter():
    loaded = StockFilter(context={'tenant_id': '1'}).load({})
    assert loaded == {'filter': {'tenant': [1]}}


def test_stock_report(app, set_db):
    query = {
        'sort': [{'field': 'articleGroup1', 'direction': -1}],
        'groups': ['articleGroup1'],
        'filter': {'endDate': '2021-01-01T00:00Z'},
    }
    response = app.post_json('/reports/stock-report', query, status=200)
    assert response.json_body['data'] == [
        {'header': 'jeans'},
        {
            'articleCode': "bccard's",
            'articleCodeSupplier': 'cheyenne 789',
            'articleDescription': 'Diesel cheyenne stonewashed',
            'articleGroup1': 'jeans',
            'skuStockMatrix': [
                ['Kleur', 'Kleur leverancier', 'Locatie', '32', '33', '34', '35'],
                ['stonewashed 32', ' 789-10d4', 'Amstelveenn', -1.0, -1.0, None, None],
                ['stonewashed 34', ' 789-10d5', 'Amstelveenn', None, None, None, -3.0],
                ['stonewashed 36', ' 789-10d6', 'Amstelveenn', None, None, -1.0, None],
            ],
        },
    ]


def test_stock_report_history(app, set_db):
    query = {
        'sort': [{'field': 'articleGroup1', 'direction': -1}],
        'groups': ['articleGroup1'],
        'filter': {'startDate': '2019-01-01T00:00Z', 'endDate': '2021-01-01T00:00Z'},
        'history': True,
    }
    response = app.post_json('/reports/stock-report', query, status=200)
    assert response.json_body['data'] == [
        {'header': 'jeans'},
        {
            'articleCode': "bccard's",
            'articleCodeSupplier': 'cheyenne 789',
            'articleDescription': 'Diesel cheyenne stonewashed',
            'articleGroup1': 'jeans',
            'skuStockMatrix': [
                [
                    'Kleur',
                    'Tijd',
                    'Locatie',
                    'Gebruiker',
                    'Type',
                    'Referentie',
                    '32',
                    '33',
                    '34',
                    '35',
                ],
                [
                    'stonewashed 32 / 789-10d4 / ',
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ],
                [
                    '',
                    '20-02-05 05:31',
                    'Amstelveenn',
                    '11-Nancy',
                    'Verk',
                    ' ',
                    None,
                    -1.0,
                    None,
                    None,
                ],
                [
                    '',
                    '20-02-18 05:39',
                    'Amstelveenn',
                    '11-Nancy',
                    'Verk',
                    ' ',
                    -1.0,
                    None,
                    None,
                    None,
                ],
                ['', 'Eindvoorraad', '', '', '', '', -1.0, -1.0, 0, 0],
                [
                    'stonewashed 34 / 789-10d5 / ',
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ],
                [
                    '',
                    '19-09-19 12:11',
                    'Amstelveenn',
                    '01-Bobby',
                    'Verk',
                    ' ',
                    None,
                    None,
                    None,
                    -1.0,
                ],
                [
                    '',
                    '19-10-14 09:56',
                    'Amstelveenn',
                    '01-Bobby',
                    'Verk',
                    ' ',
                    None,
                    None,
                    None,
                    -1.0,
                ],
                [
                    '',
                    '20-03-17 03:32',
                    'Amstelveenn',
                    '11-Nancy',
                    'Verk',
                    ' ',
                    None,
                    None,
                    None,
                    -1.0,
                ],
                ['', 'Eindvoorraad', '', '', '', '', 0, 0, 0, -3.0],
                [
                    'stonewashed 36 / 789-10d6 / ',
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ],
                [
                    '',
                    '20-02-07 09:59',
                    'Amstelveenn',
                    '11-Nancy',
                    'Verk',
                    ' ',
                    None,
                    None,
                    -1.0,
                    None,
                ],
                ['', 'Eindvoorraad', '', '', '', '', 0, 0, -1.0, 0],
            ],
        },
    ]


def imageroot(tenant):
    return 'file://{}/images/'.format(BASE_DIR)


def test_stock_report_pdf(app, set_db, monkeypatch):
    monkeypatch.setattr('spynl.services.pdf.pdf.get_image_location', imageroot)
    query = {
        'sort': [{'field': 'articleGroup1', 'direction': -1}],
        'groups': ['articleGroup1', 'brand'],
        'filter': {'endDate': '2021-01-01T00:00Z'},
        'productPhotos': True,
    }
    app.post_json('/reports/stock-report-pdf', query, status=200)


def test_stock_history_report_pdf(app, set_db, monkeypatch):
    monkeypatch.setattr('spynl.services.pdf.pdf.get_image_location', imageroot)
    query = {
        'sort': [{'field': 'articleGroup1', 'direction': -1}],
        'groups': ['articleGroup1', 'brand'],
        'filter': {'endDate': '2021-01-01T00:00Z'},
        'productPhotos': True,
        'history': True,
        'pageSize': 'A4 landscape',
    }
    app.post_json('/reports/stock-report-pdf', query, status=200)


def test_stock_filter(app, set_db):
    result = app.post_json('/reports/stock-report-filter', {}, status=200)
    assert result.json_body['data']['filter'] == {
        'articleCode': ["bccard's"],
        'articleCodeSupplier': ['cheyenne 789'],
        'articleDescription': ['Diesel cheyenne stonewashed'],
        'articleGroup1': ['jeans'],
        'articleGroup2': [],
        'articleGroup3': [],
        'articleGroup4': [],
        'articleGroup5': [],
        'articleGroup6': [],
        'articleGroup7': [],
        'articleGroup8': ['A'],
        'articleGroup9': [],
        'barcode': None,
        'brand': ['Diesel'],
        'collection': ['basis-00'],
        'customGroupBy': ['30', '32', '34', '36'],
        'supplier': ['Diesel'],
        'warehouse': ['Amstelveenn'],
    }
