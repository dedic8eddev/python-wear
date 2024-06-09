"""Tests for receiving schema."""

import copy
import json
import os

import pytest
from marshmallow import ValidationError

from spynl_schemas.receiving import ReceivingSchema
from spynl_schemas.utils import cast_percentage

EXAMPLE_DIR = os.path.abspath(os.path.dirname(__file__))


@pytest.mark.parametrize('status', ['unconfirmed', 'complete'])
def test_transform_data(status):
    schema = ReceivingSchema(partial=True)
    data = schema.load(
        {
            'status': status,
            'skus': [
                {'barcode': '1A', 'articleCode': 'A', 'qty': 5},
                {'barcode': '2A', 'articleCode': 'A', 'qty': 1},
                {'barcode': '3A', 'articleCode': 'A', 'qty': 1},
                {'barcode': '1B', 'articleCode': 'B', 'qty': 5},
                {'barcode': '2B', 'articleCode': 'B', 'qty': 2},
                {'barcode': '3B', 'articleCode': 'B', 'qty': 2},
                {'barcode': '2B', 'articleCode': 'B', 'qty': 2},
                {'barcode': '2C', 'articleCode': 'C', 'qty': 1},
                {'barcode': '2C', 'articleCode': 'C', 'qty': 2},
            ],
        }
    )
    assert 'skus' not in data and data['products'] == [
        {
            'articleCode': 'A',
            'skus': [
                {'barcode': '1A', 'qty': 5},
                {'barcode': '2A', 'qty': 1},
                {'barcode': '3A', 'qty': 1},
            ],
            'sizes': [],
        },
        {
            'articleCode': 'B',
            'skus': [
                {'barcode': '1B', 'qty': 5},
                {'barcode': '2B', 'qty': 4},
                {'barcode': '3B', 'qty': 2},
            ],
            'sizes': [],
        },
        {'articleCode': 'C', 'skus': [{'barcode': '2C', 'qty': 3}], 'sizes': []},
    ]


def test_no_merging():
    schema = ReceivingSchema(partial=True)
    receiving = {
        'status': 'draft',
        'skus': [
            {'barcode': '1A', 'articleCode': 'A', 'qty': 5},
            {'barcode': '2B', 'articleCode': 'B', 'qty': 2},
            {'barcode': '2C', 'articleCode': 'C', 'qty': 2},
        ],
    }
    data = schema.load(receiving)
    assert data['skus'] == receiving['skus'] and 'products' not in data


@pytest.mark.parametrize('price,sell_price', [(0, 5), (12, 7)])
def test_fpquery(price, sell_price):
    sku = {
        'sizeIndex': 3,
        'buyPrice': price,
        'price': sell_price,
        'size': 'M',
        'color': 'black',
        'suggestedRetailPrice': 1,
    }
    receiving = {
        'status': 'complete',
        'docNumber': '46f464d7-a063-4524-b052-386916475901',
        'warehouseId': '41',
        'orderNumber': 'RCV-1',
        'supplierOrderReference': ['a', 'b'],
        'skus': [{**sku, 'barcode': '91', 'articleCode': '1|2|3', 'qty': 5}],
        'remarks': 'foo bar',
    }
    data = ReceivingSchema(exclude=('tenant_id',)).load(receiving)
    queries = ReceivingSchema.generate_fpqueries(
        data, *[('token', 1), ('tenant_id', 2)]
    )

    assert queries == [
        (
            'Receivings',
            'Receivings/token__1/tenant_id__2/'
            'uuid__46f464d7%2Da063%2D4524%2Db052%2D386916475901/'
            'remark__foo%20bar/refid__RCV%2D1/reference__a/reference__b/barcode__91'
            '/qty__5/price__{}/sellprice__{}'.format(
                cast_percentage(price), cast_percentage(sell_price)
            ),
        )
    ]


@pytest.mark.parametrize('status', ['unconfirmed', 'complete'])
def test_size_index(status):
    schema = ReceivingSchema(partial=True)
    data = schema.load(
        {
            'status': status,
            'skus': [
                {
                    'size': 'S',
                    'sizeIndex': 0,
                    'barcode': '1A',
                    'articleCode': 'A',
                    'qty': 5,
                },
                {
                    'size': 'L',
                    'sizeIndex': 2,
                    'barcode': '2A',
                    'articleCode': 'A',
                    'qty': 1,
                },
                {
                    'size': 'L',
                    'sizeIndex': 2,
                    'barcode': '2AB',
                    'articleCode': 'A',
                    'colorCode': 'Blue',
                    'qty': 1,
                },
                {
                    'size': 'M',
                    'sizeIndex': 1,
                    'barcode': '3A',
                    'articleCode': 'A',
                    'qty': 1,
                },
                {
                    'size': 'M',
                    'sizeIndex': 1,
                    'barcode': '1B',
                    'articleCode': 'B',
                    'qty': 5,
                },
                {
                    'size': 'L',
                    'sizeIndex': 2,
                    'barcode': '2B',
                    'articleCode': 'B',
                    'qty': 2,
                },
                {
                    'size': 'Xl',
                    'sizeIndex': 3,
                    'barcode': '3B',
                    'articleCode': 'B',
                    'qty': 2,
                },
                {
                    'size': 'XXL',
                    'sizeIndex': 4,
                    'barcode': '2B',
                    'articleCode': 'B',
                    'qty': 2,
                },
                {
                    'size': 'S',
                    'sizeIndex': 0,
                    'barcode': '2C',
                    'articleCode': 'C',
                    'qty': 1,
                },
                {
                    'size': 'S',
                    'sizeIndex': 0,
                    'barcode': '2C',
                    'articleCode': 'C',
                    'qty': 2,
                },
            ],
        }
    )
    assert 'skus' not in data and data['products'] == [
        {
            'skus': [
                {'size': 'S', 'sizeIndex': 0, 'barcode': '1A', 'qty': 5},
                {'size': 'L', 'sizeIndex': 2, 'barcode': '2A', 'qty': 1},
                {
                    'barcode': '2AB',
                    'colorCode': 'Blue',
                    'qty': 1,
                    'size': 'L',
                    'sizeIndex': 2,
                },
                {'size': 'M', 'sizeIndex': 1, 'barcode': '3A', 'qty': 1},
            ],
            'articleCode': 'A',
            'sizes': ['S', 'M', 'L'],
        },
        {
            'skus': [
                {'size': 'M', 'sizeIndex': 1, 'barcode': '1B', 'qty': 5},
                {'size': 'L', 'sizeIndex': 2, 'barcode': '2B', 'qty': 4},
                {'size': 'Xl', 'sizeIndex': 3, 'barcode': '3B', 'qty': 2},
            ],
            'articleCode': 'B',
            'sizes': ['M', 'L', 'Xl'],
        },
        {
            'skus': [{'size': 'S', 'sizeIndex': 0, 'barcode': '2C', 'qty': 3}],
            'articleCode': 'C',
            'sizes': ['S'],
        },
    ]


@pytest.mark.parametrize('status', ['draft', 'unconfirmed', 'complete'])
def test_calculate_totals(status):
    schema = ReceivingSchema(context={'tenant_id': '1'}, partial=True)
    receiving = schema.load({**copy.deepcopy(RECEIVING), 'status': status})

    expected = {
        'totalPrice': 274671.7,
        'totalBuyPrice': 115075.5,
        'totalQty': 1970,
        'totalValuePrice': 115075.5,
    }

    for k, v in expected.items():
        assert receiving[k] == v


def test_move_from_draft_to_unconfirmed_to_complete():
    schema = ReceivingSchema(context={'tenant_id': '1'}, partial=True)
    receiving = schema.load({**copy.deepcopy(RECEIVING), 'status': 'draft'})
    assert 'skus' in receiving
    assert 'products' not in receiving
    receiving['status'] = 'unconfirmed'
    receiving = schema.load(receiving)
    assert 'skus' not in receiving
    assert 'products' in receiving
    receiving['status'] = 'complete'
    receiving = schema.load(receiving)
    assert 'skus' not in receiving
    assert 'products' in receiving


def test_cannot_move_from_unconfirmed_to_draft():
    schema = ReceivingSchema(context={'tenant_id': '1'}, partial=True)
    receiving = schema.load({**copy.deepcopy(RECEIVING), 'status': 'draft'})
    receiving['status'] = 'unconfirmed'
    receiving = schema.load(receiving)
    receiving['status'] = 'draft'
    with pytest.raises(ValidationError):
        receiving = schema.load(receiving)


def test_pdf_dump_look_up_warehouse(database):
    database.warehouses.insert_one(
        {'_id': '1', 'name': 'A warehouse', 'tenant_id': '2'}
    )
    receiving = {'warehouseId': '1'}
    ReceivingSchema.lookup_warehouse_data(receiving, db=database, tenant_id='2')

    assert receiving['warehouseName'] == 'A warehouse'


def test_prepare_for_pdf():
    with open(os.path.join(EXAMPLE_DIR, 'example_completed_receivings.json')) as f:
        receiving = json.loads(f.read())
    receiving['products'][0]['skus'].append(
        {
            'size': 'unknown',
            'sizeIndex': 2,
            'color': 'navy blauw',
            'qty': 400,
            'barcode': '000053035675',
            'colorCode': 'navy',
            'colorDescription': 'blauw',
            'colorSupplier': '0020',
        }
    )
    pdf = ReceivingSchema.prepare_for_pdf(receiving)
    sku_table = {
        'available_sizes': ['M', 'L', 'XL', 'XXL', 'unknown'],
        'skuRows': [
            {
                'colorCode': 'navy',
                'colorSupplier': '0020',
                'colorDescription': 'blauw',
                'remarks': '',
                'price': 172.41,
                'quantities': {
                    'L': 300,
                    'M': 400,
                    'XL': 250,
                    'XXL': 100,
                    'unknown': 400,
                },
                'totalPrice': 249994.5,
                'totalQuantity': 1450,
            }
        ],
        'sizeTotals': {'L': 300, 'M': 400, 'XL': 250, 'XXL': 100, 'unknown': 400},
        'totalPrice': 249994.5,
        'totalQuantity': 1450,
    }
    assert pdf['products'][0]['skuTable'] == sku_table


RECEIVING = {
    'status': 'complete',
    'skus': [
        {
            'articleCode': 'si-35155786-w1',
            'articleCodeSupplier': '35155786',
            'qty': 400,
            'barcode': '000053035675',
            'price': 172.41,
            'valuePrice': 72.15,
            'buyPrice': 72.15,
        },
        {
            'articleCode': 'si-35155786-w1',
            'articleCodeSupplier': '35155786',
            'qty': 300,
            'barcode': '000053035676',
            'price': 172.41,
            'valuePrice': 72.15,
            'buyPrice': 72.15,
        },
        {
            'articleCode': 'si-35155786-w1',
            'articleCodeSupplier': '35155786',
            'qty': 250,
            'barcode': '000053035677',
            'price': 172.41,
            'valuePrice': 72.15,
            'buyPrice': 72.15,
        },
        {
            'articleCode': 'si-35155786-w1',
            'articleCodeSupplier': '35155786',
            'qty': 100,
            'barcode': '000053035678',
            'price': 172.41,
            'valuePrice': 72.15,
            'buyPrice': 72.15,
        },
        {
            'articleCode': 'si-35151527-w1',
            'articleCodeSupplier': '35151527',
            'price': 104.35,
            'valuePrice': 44.02,
            'buyPrice': 44.02,
            'qty': 400,
            'barcode': '000053035577',
        },
        {
            'articleCode': 'si-35153032-w1',
            'articleCodeSupplier': '35153032',
            'price': 99.81,
            'valuePrice': 41.75,
            'buyPrice': 41.75,
            'qty': 125,
            'barcode': '000053035600',
        },
        {
            'articleCode': 'si-35153032-w1',
            'articleCodeSupplier': '35153032',
            'price': 99.81,
            'valuePrice': 41.75,
            'buyPrice': 41.75,
            'qty': 150,
            'barcode': '000053035601',
        },
        {
            'articleCode': 'si-35153032-w1',
            'articleCodeSupplier': '35153032',
            'price': 99.81,
            'valuePrice': 41.75,
            'buyPrice': 41.75,
            'qty': 245,
            'barcode': '000053035602',
        },
    ],
}
