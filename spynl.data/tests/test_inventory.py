"""Tests for receiving schema."""


from copy import deepcopy

from spynl_schemas import InventorySchema

FP_QUERY = (
    'sendinventory/token__123123123123/tenant_id__43588/username__foo/warehouse__51'
    '/uuid__46f464d7%2Da063%2D4524%2Db052%2D386916475901/barcodes__{barcodes}'
)
COMMON_EVENT_DATA = [
    ('token', '123123123123'),
    ('tenant_id', '43588'),
    ('username', 'foo'),
    ('warehouse', '51'),
]


def sample_data():
    """Return sample receiving transaction to test against."""
    return deepcopy(
        {
            "docNumber": "46f464d7-a063-4524-b052-386916475901",
            "warehouseId": "987654321",
            "products": [
                {"barcode": "91", "articleCode": "1|2|3", "qty": 5},
                {"barcode": "92", "articleCode": "4|5|6", "qty": 3},
            ],
            "remarks": "foo bar",
        }
    )


def test_receiving_fp_query_string_without_product_prices():
    schema = InventorySchema(exclude=('tenant_id',))
    data = schema.load(sample_data())
    result = schema.generate_fpqueries(data, *COMMON_EVENT_DATA)

    barcode_template = '{p[barcode]}%3B{p[qty]}'
    barcodes = [barcode_template.format(p=product) for product in data['products']]
    string = FP_QUERY.format(barcodes='%7C'.join(barcodes))
    assert result == [('sendinventory', string)]


def test_receiving_fp_query_string_with_product_prices():
    data = sample_data()
    for product in data['products']:
        product['buyPrice'] = 9.99
    schema = InventorySchema(exclude=('tenant_id',))
    data = schema.load(data)
    result = schema.generate_fpqueries(data, *COMMON_EVENT_DATA)

    barcode_template = '{p[barcode]}%3B{p[qty]}'
    barcodes = [barcode_template.format(p=product) for product in data['products']]
    string = FP_QUERY.format(barcodes='%7C'.join(barcodes))
    assert result == [('sendinventory', string)]
