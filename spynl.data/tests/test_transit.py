import pytest
from marshmallow import ValidationError

from spynl_schemas import TransitSchema


def test_sendorder_query():
    transit = {
        'overallReceiptDiscount': 0.0,
        'cashier': {'id': '123', 'name': 'kareem'},
        'device_id': '123',
        'nr': '123',
        'receiptNr': '456',
        'shop': {'id': '50'},
        'type': 3,
        'transit': {'transitWarehouse': '50', 'transitPeer': '55', 'dir': 'to'},
        'receipt': [
            {
                'category': 'barcode',
                'qty': 4,
                'barcode': '123211233',
                'articleCode': 'CODE',
                'sizeLabel': 'M',
                'color': 'black',
                'vat': 21,
                'price': 12.23,
            },
            {
                'category': 'barcode',
                'barcode': '123211231',
                'qty': 5,
                'articleCode': 'CODE2',
                'sizeLabel': 'L',
                'color': 'blue',
                'vat': 21,
                'price': 20.00,
            },
        ],
    }

    d = TransitSchema(context={'tenant_id': '1'}).load(transit)
    queries = TransitSchema.generate_fpqueries(d, ('token', 'TOKEN'))
    assert queries == [
        (
            'sendxtransit',
            'sendxtransit/token__TOKEN/from__50/to__55/'
            'refid__123/'
            'barcodes__123211233%3A4%2C123211231%3A5',
        )
    ]


def test_transit_warehouse_name_filled_in_from_db(database):
    database.warehouses.insert_one(dict(wh='55', tenant_id=['999'], name='a warehouse'))
    transit = {'shop': {'id': '50'}, 'transit': {'transitPeer': '55', 'dir': 'to'}}
    data = TransitSchema(
        only=('transit', 'shop.id', 'type'),
        context={'db': database, 'tenant_id': '999'},
    ).load(transit)
    assert data['transit']['transitWarehouse'] == 'a warehouse'


def test_peer_and_shop_should_be_different():
    transit = {'shop': {'id': '50'}, 'transit': {'transitPeer': '50', 'dir': 'to'}}
    with pytest.raises(ValidationError, match='Transit.transitPeer'):
        TransitSchema(only=('transit', 'shop.id')).load(transit)
