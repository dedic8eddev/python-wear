import json
import os

import pytest

from spynl.api.auth.testutils import login, mkuser

from spynl.services.pdf.pdf import generate_article_status_html_css
from spynl.services.reports.article_status import ArticleStatusQuery

PATH = os.path.dirname(os.path.abspath(__file__))

TENANT = {
    '_id': '12345',
    'applications': ['dashboard'],
    'settings': {
        'logoUrl': {'medium': 'file://{}/examples/square_logo.png'.format(PATH)}
    },
    'name': 'Testing Tenant',
    'addresses': [
        {
            'address': 'street street 1',
            'zipcode': '1000 AB',
            'city': 'The City',
            'country': 'NL',
            'primary': True,
        }
    ],
}


@pytest.fixture
def set_db(db):
    """
    add user and tenant and example receiving order
    """
    db.tenants.insert_one(TENANT)

    mkuser(
        db,
        'reports_user',
        'bla',
        ['12345'],
        language='nl-nl',
        tenant_roles={'12345': ['dashboard-report_user']},
    )


PAYLOAD = {
    'groups': ['brand', 'supplier', 'articleCode'],
    'fields': [
        'receivings',
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
        'netProfit',
        'profitability',
    ],
    'filter': {
        'startDate': '2018-05-06T22:00:00.000Z',
        'endDate': '2019-04-30T21:59:59.999Z',
        'supplier': ['Aaiko', 'American Vintage', 'Barong Barong'],
        'size': ['M/L', 'M'],
    },
    'sort': [],
    'columnMetadata': {
        'supplier': {'label': 'leverancier', 'type': 'percentage'},
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
        'grossProfit': {'type': 'number'},
        'profitability': {'type': 'number'},
    },
}


def article_status_test_data(ctx, request, format, schema):
    with open('{}/examples/data_article_status.json'.format(PATH)) as f:
        response = json.loads(f.read())
        # can be increased when debugging/adapting:
        response['data'] = response['data'][:10]
    return response


@pytest.fixture()
def mock_article_status(monkeypatch):

    monkeypatch.setattr(
        'spynl.services.reports.article_status.serve_report', article_status_test_data
    )


# this actually does not test anything, except for the registration of the endpoint
def test_article_status_pdf(app, set_db, mock_article_status):
    login(app, 'reports_user', 'bla')
    app.post_json('/reports/article-status-pdf', PAYLOAD, status=200)


# note: because this is using the mocked version of the jinja renderer, this does not
# test if all the filters are properly configured
def test_article_status_html(patch_jinja):
    class Request:
        cached_user = {'language': 'nl'}

    data = ArticleStatusQuery(context={'tenant_id': TENANT['_id']}).load(PAYLOAD)
    html, css = generate_article_status_html_css(
        Request(), data, TENANT, article_status_test_data(None, None, None, None)
    )
    assert 'Aaiko' in html
