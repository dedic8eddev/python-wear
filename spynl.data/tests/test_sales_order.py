import copy
import datetime
import uuid
from itertools import chain

import pytest
from bson import ObjectId
from marshmallow import ValidationError

from spynl_schemas import SalesOrderSchema
from spynl_schemas.foxpro_serialize import escape

CUST_ID = str(uuid.uuid4())


@pytest.fixture
def setup_db(database):
    database.wholesale_customers.insert_one({'_id': uuid.UUID(CUST_ID)})


def sales_order():
    return copy.deepcopy(
        {
            'agentId': str(ObjectId()),
            '_id': str(uuid.uuid4()),
            'status': 'draft',
            'docNumber': '77ebf863-68c0-4029-9bfc-fe5f9ba6f503',
            'reservationDate': '2017-05-06T16:00+0100',
            'fixDate': '2017-05-06T00:00+0200',
            'products': [
                {
                    'articleCode': 'A',
                    'price': 0.0,
                    'localizedPrice': 0.0,
                    'suggestedRetailPrice': 0.0,
                    'localizedSuggestedRetailPrice': 0.0,
                    'directDelivery': 'on',
                    'sizes': ['S', 'M', 'L', 'XL'],
                    'skus': [
                        {
                            'barcode': '123',
                            'size': 'M',
                            'qty': 0,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                            'remarks': 'some remark',
                        },
                        {
                            'barcode': '124',
                            'size': 'L',
                            'qty': 0,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                        {
                            'barcode': '125',
                            'size': 'XL',
                            'qty': 0,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                    ],
                },
                {
                    'articleCode': 'B',
                    'price': 0.0,
                    'localizedPrice': 0.0,
                    'suggestedRetailPrice': 0.0,
                    'localizedSuggestedRetailPrice': 0.0,
                    'sizes': ['S', 'M', 'L', 'XL'],
                    'skus': [
                        {
                            'barcode': '123',
                            'size': 'M',
                            'qty': 5,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                        {
                            'barcode': '124',
                            'size': 'L',
                            'qty': 5,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                        {
                            'barcode': '125',
                            'size': 'XL',
                            'qty': 0,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                    ],
                },
            ],
            'visitedArticles': ['C', 'B'],
            'favoriteArticles': ['E'],
            'customer': {
                'email': 'a@a.com',
                'legalName': 'COMP',
                'id': '123',
                '_id': CUST_ID,
                'vatNumber': '123',
                'cocNumber': '123',
                'bankNumber': '123',
                'clientNumber': '123',
                'currency': 'JPN',
                'address': {
                    'address': 'somestreet 40',
                    'zipcode': '1222BE',
                    'city': 'Zaandam',
                    'country': 'NL',
                    'telephone': '123123123',
                },
                'deliveryAddress': {
                    'address': 'somestreet 40',
                    'zipcode': '1222BE',
                    'city': 'Zaandam',
                    'country': 'NL',
                    'telephone': '123123123',
                },
            },
        }
    )


def complete_sales_order():
    order = sales_order()
    order['status'] = 'complete'
    order['signedBy'] = 'kareem'
    order['signature'] = 'data:image/png;base64,c2lnbmF0dXJl'
    order['termsAndConditionsAccepted'] = True
    return order


def complete_sales_order_with_direct():
    order = complete_sales_order()
    order['products'][0]['skus'][0]['qty'] = 3
    return order


def complete_sales_order_only_direct():
    order = complete_sales_order()
    for product in order['products']:
        product['directDelivery'] = 'on'
    return order


def test_valid_b64_signature(database):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    try:
        schema.load(complete_sales_order(), partial=True)
    except ValidationError:
        pytest.fail('validation incorrectly rejects signature')


def test_reservation_date(database):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    data = schema.load(sales_order())
    assert data[0]['reservationDate'] == str(
        datetime.datetime(2017, 5, 6, 0, 0).isoformat()
    )
    assert data[0]['fixDate'] == str(datetime.datetime(2017, 5, 6, 0, 0).isoformat())


def test_splitting_orders_direct_delivery(database, setup_db):
    schema = SalesOrderSchema(
        context={
            'tenant_id': '123',
            'orderNumber': 1,
            'db': database,
            'user_id': '1',
            'packing_list_on_direct_delivery': False,
        }
    )
    data = schema.load(complete_sales_order_with_direct())
    assert isinstance(data, list) and len(data) == 2
    s, sp = data
    assert s['_id'] != sp['_id']
    assert s['docNumber'] != sp['docNumber']
    assert s['type'] == 'sales-order'
    assert sp['type'] == 'sales-order'
    assert sp['directDelivery'] is True


def test_splitting_orders_packing_lists(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_with_direct())
    assert isinstance(data, list) and len(data) == 3
    s, sp, p = data
    assert s['_id'] != sp['_id'] != p['_id']
    assert s['docNumber'] != sp['docNumber'] != p['docNumber']
    assert s['type'] == 'sales-order'
    assert p['type'] == 'packing-list'
    assert 'directDelivery' not in s
    assert sp['directDelivery'] is True


def test_splitting_orders_only_direct_delivery(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_only_direct())
    assert isinstance(data, list) and len(data) == 2
    sp, p = data
    assert sp['_id'] != p['_id']
    assert sp['docNumber'] != p['docNumber']
    assert sp['type'] == 'sales-order'
    assert sp['directDelivery'] is True
    assert p['type'] == 'packing-list'


def test_splitting_orders_only_direct_delivery_no_packing_list(database, setup_db):
    schema = SalesOrderSchema(
        context={
            'tenant_id': '123',
            'orderNumber': 1,
            'db': database,
            'user_id': '1',
            'packing_list_on_direct_delivery': False,
        }
    )
    data = schema.load(complete_sales_order_only_direct())
    assert isinstance(data, list) and len(data) == 1
    sp = data[0]
    assert sp['type'] == 'sales-order'
    assert sp['directDelivery'] is True


def test_splitting_products_orders_packing_lists(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_with_direct())
    s, sp, p = data
    assert all(product['directDelivery'] == 'on' for product in sp['products'])
    assert all(product['directDelivery'] == 'unavailable' for product in s['products'])


def test_splitting_orders_packing_lists_status_history(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_with_direct())
    s, sp, p = data
    assert len(p['status_history']) == 1
    assert p['status_history'][0]['status'] == 'open'


def test_splitting_orders_packing_lists_status(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_with_direct())
    s, sp, p = data
    assert p['status'] == 'open'
    database.wholesale_customers.update_one(
        {'_id': uuid.UUID(CUST_ID)}, {'$set': {'blocked': True}}
    )
    data = schema.load(complete_sales_order_with_direct())
    s, sp, p = data
    assert p['status'] == 'pending'


def test_splitting_products_orders_packing_lists_link_document(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_with_direct())
    s, sp, p = data
    assert all(
        sku['link'] == [sp['docNumber']]
        for sku in chain.from_iterable([product['skus'] for product in p['products']])
    )


def test_settings_reference_on_direct_delivery_skus(database, setup_db):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database, 'user_id': '1'}
    )
    data = schema.load(complete_sales_order_with_direct())
    s, sp, p = data
    assert all(
        sku['salesOrder'] == s['_id']
        for product in p['products']
        for sku in product['skus']
    )


def test_invalid_b64_signature():
    schema = SalesOrderSchema(context={'tenant_id': '123', 'orderNumber': 1})
    data_uri, _ = SIGNATURE.split(',')
    signature = data_uri + ',123'
    with pytest.raises(ValidationError, match='Invalid base64 signature'):
        schema.load(
            {**complete_sales_order(), 'status': 'complete', 'signature': signature}
        )


def test_empty_string_signature():
    schema = SalesOrderSchema(context={'tenant_id': '123', 'orderNumber': 1})
    with pytest.raises(ValidationError, match='May not be an empty base64 string'):
        schema.load({**sales_order(), 'status': 'complete', 'signature': ''})


def test_acceptance_order_terms():
    schema = SalesOrderSchema(context={'tenant_id': '123', 'orderNumber': 1})
    with pytest.raises(ValidationError, match="termsAndConditionsAccepted"):
        schema.load({**complete_sales_order(), 'termsAndConditionsAccepted': 'False'})


def test_signature_required_on_complete():
    schema = SalesOrderSchema(context={'tenant_id': '123', 'orderNumber': 1})
    with pytest.raises(ValidationError, match=".*signature.*signedBy"):
        schema.load({**sales_order(), 'status': 'complete'})


def test_remove_zero_qty_items(database):
    schema = SalesOrderSchema(exclude=['tenant_id'])
    schema.context.update(orderNumber=1, db=database)
    data = schema.load(sales_order())[0]
    skus = data['products'][0]['skus']
    assert len(skus) == 2 and ''.join(s['size'] for s in skus) == 'ML'


def test_remove_zero_qty_products(database):
    schema = SalesOrderSchema(exclude=['tenant_id'])
    schema.context.update(orderNumber=1, db=database)
    data = schema.load(sales_order())[0]
    assert len(data['products']) == 1


def test_raise_on_complete_and_no_products(database):
    schema = SalesOrderSchema(exclude=['tenant_id'])
    schema.context.update(orderNumber=1, db=database)
    with pytest.raises(
        ValidationError, match="Missing data for required field on completed order"
    ):
        schema.load(
            {**complete_sales_order(), 'products': [sales_order()['products'][0]]}
        )


def test_completed_date_not_on_draft(database):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    orders = schema.load(sales_order())
    assert 'completedDate' not in orders[0]


def test_completed_date_on_complete(database):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    orders = schema.load(complete_sales_order())
    assert orders[0]['completedDate']


def test_pop_visited_favorited(database):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    data = schema.load(
        {
            **complete_sales_order(),
            'visitedArticled': ['1', '2'],
            'favoriteArticles': ['3', '4'],
        }
    )[0]
    assert not {'visitedArticles', 'favoriteArticles'} & data.keys()


@pytest.mark.parametrize('direct_delivery,action', [(False, 'ordero'), (True, 'order')])
def test_sale_events(database, direct_delivery, action):
    schema = SalesOrderSchema(context={'tenant_id': '123', 'db': database})

    sale = schema.load(complete_sales_order())[0]
    sale['orderNumber'] = 'SO-200'
    sale['directDelivery'] = direct_delivery
    sale['customReference'] = 'custom string'
    sale['products'][0]['localizedPrice'] = 10
    events = SalesOrderSchema.generate_fpqueries(sale)

    expected = [
        (
            'sendOrder',
            'sendOrder/refid__{}/ordernumber__SO%2D200/uuid__{}/'
            'reservationdate__06-05-2017/fixdate__06-05-2017/'
            'customreference__custom%20string/action__{}/'
            'barcode__123/qty__5/price__1000/barcode__124/qty__5/price__1000'.format(
                escape(sale['docNumber']), escape(CUST_ID), action
            ),
        )
    ]
    assert events == expected


RAW_SIGNATURE = '''data:image/png;base64,
iVBORw0KGgoAAAANSUhEUgAAAjUAAAI1CAYAAAFZEjsOAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv
OFSXDUVS+MGKYHMEYHLGK/L//9/8BOW9E7B0AENCAAAAASUVORK5CYII=
'''

SIGNATURE = RAW_SIGNATURE.replace('\n', '')


def extended_sales_order():
    order = complete_sales_order()
    additional_skus = [
        {
            'barcode': '126',
            'size': 'M',
            'qty': 2,
            'color': 'blue',
            'colorFamily': 'blue',
            'colorCode': 'blue',
            'colorDescription': 'Blue',
            'colorCodeSupplier': '',
            'mainColorCode': '',
            'remarks': 'a remark',
        },
        {
            'barcode': '127',
            'size': 'L',
            'qty': 4,
            'color': 'blue',
            'colorFamily': 'blue',
            'colorCode': 'blue',
            'colorDescription': 'Blue',
            'colorCodeSupplier': '',
            'mainColorCode': '',
        },
        {
            'barcode': '128',
            'size': 'S',
            'qty': 3,
            'color': 'blue',
            'colorFamily': 'blue',
            'colorCode': 'blue',
            'colorDescription': 'Blue',
            'colorCodeSupplier': '',
            'mainColorCode': '',
        },
        {
            'barcode': '129',
            'size': 'M',
            'qty': 2,
            'color': 'red',
            'colorFamily': 'red',
            'colorCode': 'red',
            'colorDescription': 'Red',
            'colorCodeSupplier': '',
            'mainColorCode': '',
        },
        {
            'barcode': '130',
            'size': 'L',
            'qty': 4,
            'color': 'red',
            'colorFamily': 'red',
            'colorCode': 'red',
            'colorDescription': 'Red',
            'colorCodeSupplier': '',
            'mainColorCode': '',
        },
        {
            'barcode': '131',
            'size': 'XL',
            'qty': 6,
            'color': 'red',
            'colorFamily': 'red',
            'colorCode': 'red',
            'colorDescription': 'Red',
            'colorCodeSupplier': '',
            'mainColorCode': '',
        },
    ]
    order['products'][0]['skus'].extend(additional_skus)
    order['products'][0]['directDelivery'] = 'unavailable'
    order['products'][0]['localizedPrice'] = 20.00
    order['products'][1]['localizedPrice'] = 10.00
    return copy.deepcopy(order)


def test_pdf_sku_table(database):
    schema = SalesOrderSchema(context={'tenant_id': '123', 'db': database})
    order = schema.load(extended_sales_order())[0]
    pdf_order = SalesOrderSchema.prepare_for_pdf(order)
    sku_table = {
        'available_sizes': ['S', 'M', 'L', 'XL'],
        'skuRows': [
            {
                'colorCode': 'blue',
                'colorFamily': 'blue',
                'colorDescription': 'Blue',
                'price': 20.0,
                'quantities': {'L': 4, 'M': 2, 'S': 3, 'XL': 0},
                'totalPrice': 180.0,
                'totalQuantity': 9,
                'remarks': 'a remark',
            },
            {
                'colorCode': 'red',
                'colorFamily': 'red',
                'colorDescription': 'Red',
                'price': 20.0,
                'quantities': {'L': 4, 'M': 2, 'S': 0, 'XL': 6},
                'totalPrice': 240.0,
                'totalQuantity': 12,
                'remarks': '',
            },
        ],
        'sizeTotals': {'L': 8, 'M': 4, 'S': 3, 'XL': 6},
        'totalPrice': 420.0,
        'totalQuantity': 21,
    }

    assert pdf_order['products'][0]['skuTable'] == sku_table


def test_pdf_totals_of_all_products(database):
    schema = SalesOrderSchema(context={'tenant_id': '123', 'db': database})
    order = schema.load(extended_sales_order())[0]
    pdf_order = SalesOrderSchema.prepare_for_pdf(order)
    assert pdf_order['totalLocalizedPrice'] == 520.0
    assert pdf_order['totalQuantity'] == 31


def test_pdf_small_header_font(database):
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    order = schema.load(sales_order())[0]
    order['products'][0]['sizes'].append('123/136')
    order = SalesOrderSchema.prepare_for_pdf(order, database, '123')
    assert order['products'][0]['skuTable']['use_small_header_font'] is True


def test_order_terms_are_added_on_dump_for_draft(database):
    order_terms = {
        '_id': uuid.uuid4(),
        'orderPreviewText1': 'en-NL',
        'language': 'en',
        'country': 'NL',
        'tenant_id': ['123'],
    }
    database.order_terms.insert_one(order_terms)
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    order = schema.load(sales_order())[0]
    order['customer'].update({'language': 'en'})
    order = SalesOrderSchema.prepare_for_pdf(order, database, '123')
    assert order['orderTerms']['orderPreviewText1'] == 'en-NL'


def test_order_terms_are_added_on_dump_for_draft_default(database):
    order_terms = {
        '_id': uuid.uuid4(),
        'orderPreviewText1': 'default',
        'language': 'default',
        'country': 'default',
        'tenant_id': ['123'],
    }
    database.order_terms.insert_one(order_terms)
    schema = SalesOrderSchema(
        context={'tenant_id': '123', 'orderNumber': 1, 'db': database}
    )
    order = schema.load(sales_order())[0]
    order['customer'].update({'language': 'nl', 'country': 'NL'})
    order = SalesOrderSchema.prepare_for_pdf(order, database, '123')
    assert order['orderTerms']['orderPreviewText1'] == 'default'


def test_order_terms_are_not_touched_on_dump_for_complete(database):
    order_terms = {
        '_id': uuid.uuid4(),
        'orderPreviewText1': 'en-NL',
        'language': 'en',
        'country': 'NL',
        'tenant_id': ['123'],
    }
    database.order_terms.insert_one(order_terms)
    schema = SalesOrderSchema(context={'tenant_id': '123', 'db': database})
    order = schema.load(complete_sales_order())[0]
    order['customer'].update({'language': 'en', 'country': 'NL'})
    order = SalesOrderSchema.prepare_for_pdf(order, database, '123')
    assert 'orderTerms' not in order


def test_agent_name(database):
    order = sales_order()
    order.pop('agentId')
    result = database.users.insert_one({'fullname': 'joe', '_id': ObjectId()})
    data = SalesOrderSchema(
        context={
            'tenant_id': '1',
            'db': database,
            'agentId': ObjectId(result.inserted_id),
        }
    ).load(order)
    assert data[0]['agentName'] == 'joe'


def test_save_audit_trail_comes_from_database(database):
    _id = uuid.uuid4()
    # without datetimes, because they get tz info in database:
    original_audit_trail = {
        'original_version_id': ObjectId('612df4178d7c05c23d0b863f'),
        'remark': 'This was edited for some reason',
        'opened': {
            'user_id': ObjectId('612df4178d7c05c23d0b863e'),
            'username': 'bla',
        },
        'edited': {
            'user_id': ObjectId('612df4178d7c05c23d0b863e'),
            'username': 'agent',
        },
    }
    database.sales_orders.insert_one(
        {'_id': _id, 'audit_trail': [original_audit_trail]}
    )
    order = sales_order()
    order['_id'] = _id
    order['audit_trail'] = [
        {
            'original_version_id': ObjectId(),
            'remark': 'Not allowed to set this',
            'user_id': ObjectId(),
            'username': 'wrong user',
        }
    ]
    data = SalesOrderSchema(context={'tenant_id': '1', 'db': database}).load(order)[0]
    assert data['audit_trail'] == [original_audit_trail]


def test_open_for_edit():
    user_id = ObjectId()
    audit_id = ObjectId()
    order = {'foo': 'bar', 'status': 'complete'}
    SalesOrderSchema.open_for_edit(order, {'username': 'bla', '_id': user_id}, audit_id)
    order['audit_trail'][0]['opened'].pop('edit_date')
    assert order == {
        'audit_trail': [
            {
                'original_version_id': audit_id,
                'opened': {'username': 'bla', 'user_id': user_id},
            }
        ],
        'foo': 'bar',
        'status': 'complete-open-for-edit',
    }


def test_open_for_edit_preserves_audit_trail():
    order = {
        'audit_trail': [EXAMPLE_AUDIT_TRAIL_ENTRY],
        'foo': 'bar',
        'status': 'complete',
    }
    user_id = ObjectId()
    audit_id = ObjectId()
    SalesOrderSchema.open_for_edit(
        order, {'username': 'user', '_id': user_id}, audit_id
    )
    order['audit_trail'][0]['opened'].pop('edit_date')
    assert order == {
        'audit_trail': [
            {
                'original_version_id': audit_id,
                'opened': {'user_id': user_id, 'username': 'user'},
            },
            EXAMPLE_AUDIT_TRAIL_ENTRY,
        ],
        'foo': 'bar',
        'status': 'complete-open-for-edit',
    }


EXAMPLE_AUDIT_TRAIL_ENTRY = {
    'original_version_id': ObjectId('612df4178d7c05c23d0b863f'),
    'remark': 'This was edited for some reason',
    'opened': {
        'user_id': ObjectId('612df4178d7c05c23d0b863e'),
        'username': 'bla',
        'edit_date': datetime.datetime(2021, 8, 31, 9, 19, 19, 336709),
    },
    'edited': {
        'user_id': ObjectId('612df4178d7c05c23d0b863e'),
        'username': 'agent',
        'edit_date': datetime.datetime(2021, 8, 31, 9, 19, 19, 336709),
    },
}


def test_complete_open_for_edit_without_context():
    with pytest.raises(ValidationError, match='Status not allowed'):
        SalesOrderSchema().load({'status': 'complete-open-for-edit'})


def test_complete_open_for_edit_without_existing_audit_trail(database):
    user_id = ObjectId()
    sales_order = complete_sales_order()
    sales_order['status'] = 'complete-open-for-edit'
    sales_order['_id'] = uuid.UUID(sales_order['_id'])
    database.sales_orders.insert_one(sales_order)
    with pytest.raises(ValidationError):
        SalesOrderSchema(
            context={
                'tenant_id': '1234',
                'agentId': user_id,
                'db': database,
                'user_id': user_id,
                'username': 'username',
                'audit_remark': 'try to edit',
                'editing_open_order': True,
            }
        ).load(sales_order)


def test_complete_open_for_edit(database):
    user_id = ObjectId()
    sales_order = complete_sales_order()
    sales_order['status'] = 'complete-open-for-edit'
    sales_order['_id'] = uuid.UUID(sales_order['_id'])
    open_audit = {
        'original_version_id': ObjectId('612df4178d7c05c23d0b863f'),
        'opened': {
            'user_id': ObjectId('612df4178d7c05c23d0b863e'),
            'username': 'bla',
            'edit_date': datetime.datetime(2021, 8, 31, 9, 19, 19, 336709),
        },
    }
    sales_order['audit_trail'] = [open_audit]
    database.sales_orders.insert_one(sales_order)
    # get tz info:
    open_audit = database.sales_orders.find_one(sales_order['_id'])['audit_trail'][0]
    edited_order = SalesOrderSchema(
        context={
            'tenant_id': '1234',
            'agentId': user_id,
            'db': database,
            'user_id': user_id,
            'username': 'username',
            'audit_remark': 'try to edit',
            'editing_open_order': True,
        }
    ).load(sales_order)[0]
    assert edited_order['status'] == 'complete'
    for key in ('opened', 'original_version_id'):
        assert edited_order['audit_trail'][0][key] == open_audit[key]
    assert edited_order['audit_trail'][0]['remark'] == 'try to edit'
    assert edited_order['audit_trail'][0]['edited']['username'] == 'username'
    assert edited_order['audit_trail'][0]['edited']['user_id'] == user_id
