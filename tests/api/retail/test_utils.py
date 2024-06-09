import pytest

from spynl.api.retail.utils import TransactionFilterSchema


@pytest.mark.parametrize(
    'data, expected',
    [
        (
            {'paymentMethod': ['webshop']},
            {
                'payments.webshop': {'$ne': 0},
                'active': True,
                'type': {'$in': [2, 3, 9]},
            },
        ),
        (
            {'paymentMethod': ['webshop', 'pin', 'cash']},
            {
                '$or': [
                    {'payments.webshop': {'$ne': 0}},
                    {'payments.pin': {'$ne': 0}},
                    {'payments.cash': {'$ne': 0}},
                ],
                'active': True,
                'type': {'$in': [2, 3, 9]},
            },
        ),
    ],
)
def test_transaction_filter_schema_payment_method(data, expected):
    result = TransactionFilterSchema().load(data)
    assert result == expected


def test_handle_mapped_fields():
    mapping = {
        'shopName': 'shop.name',
        'customerId': 'customer.id',
        'customerLoyaltyNr': 'customer.loyaltynr',
        'customerEmail': 'customer.email',
    }
    for key, mapped_key in mapping.items():
        result = TransactionFilterSchema().load({key: 'foo'})
        assert key not in result
        assert result[mapped_key] == 'foo'
