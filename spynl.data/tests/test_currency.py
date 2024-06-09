import uuid

from spynl_schemas import Currency
from spynl_schemas.foxpro_serialize import escape


def test_currency_event():
    uuid_ = str(uuid.uuid4())
    currency = {
        'code': 'EUR',
        'description': 'euro stuff',
        'label': 'EURO normal',
        'uuid': uuid_,
    }
    data = Currency().load(currency)
    event = Currency.generate_fpqueries([data])
    assert event == [
        (
            'updatecurrencies',
            (
                'updatecurrencies/uuid__{}/'
                'label__EURO%20normal/description__euro%20stuff/isocode__EUR/'
                'salefactor__100/purchasefactor__100'
            ).format(escape(uuid_)),
        )
    ]
