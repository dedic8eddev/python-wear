import copy
import datetime
import itertools
import uuid

import pytest
from bson import ObjectId
from marshmallow import ValidationError

from spynl_schemas.foxpro_serialize import escape
from spynl_schemas.packing_list import (
    PACKING_LIST_STATUSES,
    PackingListBaseSkuSchema,
    PackingListSchema,
    PackingListSyncSchema,
)

CUST_ID = str(uuid.uuid4())


ALLOWED_STATUS_CHANGES = {
    ('pending', 'open'),
    ('open', 'pending'),
    ('open', 'picking'),
    ('picking', 'open'),
    ('picking', 'complete'),
    ('picking', 'pending'),
    ('incomplete', 'pending'),
    ('incomplete', 'complete-and-discard'),
    ('incomplete', 'complete-and-move'),
}
# sorted to be able to use xdist to run tests in parallel
INVALID_STATUS_CHANGES = sorted(
    set(itertools.permutations(PACKING_LIST_STATUSES, r=2)) - ALLOWED_STATUS_CHANGES
)


@pytest.mark.parametrize('status,new_status', INVALID_STATUS_CHANGES)
def test_packing_list_invalid_status_change(status, new_status, database):
    context = {
        'user_roles': ['picking-user', 'picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list(status))[0]
    database.sales_orders.insert_one(pl)
    with pytest.raises(ValidationError, match='Invalid status change'):
        pl['status'] = new_status
        schema.load(pl)


@pytest.mark.parametrize(
    'status', [status for status in PACKING_LIST_STATUSES if status != 'cancelled']
)
def test_packing_list_no_status_change(status, database):
    context = {
        'user_roles': [],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list(status))[0]
    database.sales_orders.insert_one(pl)
    # no validation error when status stays the same:
    schema.load(pl)


def test_no_status_change_cancelled(database):
    context = {
        'user_roles': ['picking-user', 'picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list('cancelled'))[0]
    database.sales_orders.insert_one(pl)
    with pytest.raises(ValidationError, match='Invalid status change'):
        pl['status'] = 'cancelled'
        schema.load(pl)


@pytest.mark.parametrize(
    'status',
    [
        'pending',
        'open',
        'picking',
        'incomplete',
        'complete',
        'ready-for-shipping',
        'shipping',
    ],
)
def test_packing_list_cancel(status, database):
    user_id = ObjectId()
    context = {'user_id': user_id, 'db': database, 'tenant_id': '2'}
    # create packinglist for database:
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list(status))[0]
    pl['products'][0]['skus'][0]['qty'] = 5
    pl['products'][0]['skus'][0]['picked'] = 5
    pl['products'][0]['skus'][1]['qty'] = 5
    pl['products'][0]['skus'][1]['picked'] = 5
    database.sales_orders.insert_one(pl)
    # cancel and check
    pl = PackingListSchema.cancel(pl, user_id)
    assert all(s['picked'] == 0 for p in pl['products'] for s in p['skus'])
    assert pl['status'] == 'cancelled'
    assert pl['status_history'][0]['status'] == 'cancelled'
    assert pl['status_history'][1]['status'] == status
    assert pl['status_history'][0]['user'] == pl['status_history'][1]['user'] == user_id


@pytest.mark.parametrize(
    'status,new_status',
    [
        ('pending', 'open'),
        ('open', 'pending'),
        ('picking', 'pending'),
        ('incomplete', 'pending'),
        ('incomplete', 'complete-and-discard'),
        ('incomplete', 'complete-and-move'),
    ],
)
def test_packing_list_status_change_role_check(status, new_status, database):
    context = {
        'user_roles': ['picking-user'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list(status))[0]
    database.sales_orders.insert_one(pl)
    with pytest.raises(ValidationError, match='Invalid status change'):
        pl['status'] = new_status
        schema.load(pl)


@pytest.mark.parametrize(
    'status,new_status', [('picking', 'open'), ('picking', 'complete')]
)
def test_packing_list_status_change_user_id_check(status, new_status, database):
    context = {
        'user_roles': [],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list(status))[0]
    database.sales_orders.insert_one(pl)
    with pytest.raises(ValidationError, match='Invalid status change'):
        schema.context['user_id'] = '2'
        pl['status'] = new_status
        schema.load(pl)


@pytest.mark.parametrize(
    'status,new_status', [('pending', 'open'), ('open', 'pending')]
)
def test_packing_list_status_pending_open(status, new_status, database):
    context = {
        'user_roles': ['picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list(status))[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = new_status
    # no validation error:
    schema.load(pl)


def test_packing_list_status_move_from_picking_open(database):
    context = {
        'user_roles': ['picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = packing_list('picking')
    pl['products'][1]['skus'][0]['qty'] = 5
    pl['products'][1]['skus'][0]['picked'] = 4
    pl = schema.load(pl)[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = 'complete'
    pl = schema.load(pl)[0]
    assert pl['status'] == 'incomplete'
    database.sales_orders.upsert_one({'_id': pl['_id']}, pl)
    pl['status'] = 'pending'
    pl = schema.load(pl)[0]
    assert pl['status'] == 'pending'
    assert all(s['picked'] == 0 for p in pl['products'] for s in p['skus'])


@pytest.mark.parametrize('new_status', ['open', 'pending'])
def test_packing_list_status_move_and_reset(new_status, database):
    context = {
        'user_roles': ['picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = packing_list('picking')
    pl['products'][1]['skus'][0]['qty'] = 5
    pl['products'][1]['skus'][0]['picked'] = 4
    pl = schema.load(pl)[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = new_status
    pl = schema.load(pl)[0]
    assert all(s['picked'] == 0 for p in pl['products'] for s in p['skus'])


def test_packing_list_status_move_complete(database):
    context = {
        'user_roles': [],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list('picking'))[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = 'complete'
    for p in pl['products']:
        for s in p['skus']:
            s['picked'] = s['qty']
    pl = schema.load(pl)[0]
    assert pl['status'] == 'ready-for-shipping'


def test_packing_list_status_complete_and_discard(database):
    context = {
        'user_roles': ['picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = packing_list('incomplete')
    pl['products'][1]['skus'][0]['qty'] = 5
    pl['products'][1]['skus'][0]['picked'] = 5
    pl['products'][1]['skus'][1]['qty'] = 5
    pl['products'][1]['skus'][1]['picked'] = 3
    pl['products'][1]['skus'][2]['qty'] = 5
    pl['products'][1]['skus'][2]['picked'] = 0

    pl = schema.load(pl)[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = 'complete-and-discard'
    pl = schema.load(pl)[0]
    assert pl['status'] == 'ready-for-shipping'
    assert (
        [pl['products'][0]['skus'][0]['qty'], pl['products'][0]['skus'][1]['qty']]
        == [
            pl['products'][0]['skus'][0]['picked'],
            pl['products'][0]['skus'][1]['picked'],
        ]
        == [5, 3]
    )
    assert len(pl['products'][0]['skus']) == 2
    assert len(pl['products']) == 1
    assert pl['products'][0]['articleCode'] == 'B'


def test_packing_list_status_complete_and_move(database):
    context = {
        'user_roles': ['picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    database.tenants.insert_one(
        {
            '_id': '2',
            'counters': {
                'packingList': 0,
            },
        }
    )
    schema = PackingListSchema(context=context)
    pl = packing_list('incomplete')
    pl['products'][1]['skus'][0]['qty'] = 5
    pl['products'][1]['skus'][0]['picked'] = 5
    pl['products'][1]['skus'][1]['qty'] = 5
    pl['products'][1]['skus'][1]['picked'] = 3
    pl['products'][1]['skus'][2]['qty'] = 5
    pl['products'][1]['skus'][2]['picked'] = 0

    pl = schema.load(pl)[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = 'complete-and-move'
    packing_lists = schema.load(pl)
    assert len(packing_lists) == 2
    assert len(packing_lists[0]['products']) == 1
    assert len(packing_lists[1]['products']) == 1
    assert len(packing_lists[0]['products'][0]['skus']) == 2
    assert len(packing_lists[1]['products'][0]['skus']) == 2


def test_split_packing_list():
    docNumber1 = uuid.uuid4()
    docNumber2 = uuid.uuid4()
    packing_list = {
        '_id': uuid.uuid4(),
        'docNumber': uuid.uuid4(),
        'numberOfParcels': 1,
        'products': [
            {
                'articleCode': 'A',
                'price': 5.0,
                'skus': [
                    {'barcode': '123', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                    {'barcode': '124', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                    {'barcode': '125', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                ],
            },
            {
                'articleCode': 'B',
                'price': 3.0,
                'skus': [
                    {'barcode': '128', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                    {'barcode': '123', 'qty': 5, 'picked': 3, 'link': [docNumber1]},
                    {'barcode': '124', 'qty': 5, 'picked': 1, 'link': [docNumber2]},
                    {'barcode': '125', 'qty': 5, 'picked': 0, 'link': [docNumber2]},
                ],
            },
        ],
    }
    original, new = PackingListSchema.split_packing_list(packing_list)
    assert new['_id'] != original['_id']
    assert new['docNumber'] != original['docNumber']
    assert 'numberOfParcels' not in new
    assert original['products'] == [
        {
            'articleCode': 'A',
            'price': 5.0,
            'skus': [
                {'barcode': '123', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                {'barcode': '124', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                {'barcode': '125', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
            ],
        },
        {
            'articleCode': 'B',
            'price': 3.0,
            'skus': [
                {'barcode': '128', 'qty': 5, 'picked': 5, 'link': [docNumber1]},
                {'barcode': '123', 'qty': 3, 'picked': 3, 'link': [docNumber1]},
                {'barcode': '124', 'qty': 1, 'picked': 1, 'link': [docNumber2]},
                {'barcode': '125', 'qty': 0, 'picked': 0, 'link': [docNumber2]},
            ],
        },
    ]
    assert new['products'] == [
        {
            'articleCode': 'B',
            'price': 3.0,
            'skus': [
                {
                    'barcode': '123',
                    'qty': 2,
                    'picked': 0,
                    'link': [docNumber1, original['docNumber']],
                },
                {
                    'barcode': '124',
                    'qty': 4,
                    'picked': 0,
                    'link': [docNumber2, original['docNumber']],
                },
                {
                    'barcode': '125',
                    'qty': 5,
                    'picked': 0,
                    'link': [docNumber2, original['docNumber']],
                },
            ],
        }
    ]


def test_packing_list_status(database):
    _id = uuid.uuid4()
    picker_id = ObjectId()
    admin_id = ObjectId()
    order = {
        **packing_list('open'),
        '_id': _id,
        'products': [],
        'status_history': [
            {'user': admin_id, 'status': 'open', 'date': datetime.datetime.utcnow()}
        ],
    }
    database.sales_orders.insert_one(order)
    order['status'] = 'picking'
    schema = PackingListSchema(
        context={
            'db': database,
            'user_id': picker_id,
            'user_fullname': 'name',
            'user_roles': [],
        },
        only=('status', '_id', 'products'),
    )

    p = schema.load(order)[0]

    for status in p['status_history']:
        status.pop('date')

    assert p == {
        '_id': _id,
        'orderPicker': picker_id,
        'orderPickerName': 'name',
        'products': [],
        'status': 'picking',
        'status_history': [
            {'status': 'picking', 'user': picker_id},
            {'status': 'open', 'user': admin_id},
        ],
    }


def test_packing_list_sync_lookup_warehouse(database):
    database.warehouses.insert_one({'_id': '12345', 'tenant_id': '1234', 'wh': '100'})
    data = packing_list('open')
    data.pop('warehouseId')
    pl = PackingListSyncSchema(context={'db': database, 'tenant_id': '1234'}).load(
        {**data, 'warehouse': '100'}
    )
    assert pl['warehouseId'] == '12345'


def test_packing_list_events(database):
    context = {
        'user_roles': [],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list('picking'))[0]
    database.sales_orders.insert_one(pl)
    pl['status'] = 'complete'
    schema.load(pl)

    events = PackingListSchema.generate_fpqueries(pl)

    expected = [
        (
            'sendOrder',
            (
                'sendOrder/refid__{}/uuid__{}/action__pakbon/'
                'barcode__123/qty__5/price__0.0/picked__5/'
                'barcode__124/qty__5/price__0.0/picked__5/'
                'barcode__125/qty__5/price__0.0/picked__5'
            ).format(escape(pl['docNumber']), escape(pl['customer']['_id'])),
        )
    ]
    assert events == expected

    events = PackingListSchema.generate_shipping_fp_event(pl)
    expected = [
        (
            'shipPackingList',
            'shipPackingList/refid__77ebf863%2D68c0%2D4029%2D9bfc%2Dfe5f9ba6f503/'
            'barcodes__orderNumber%3Bean%3Bqty%5Foriginal%3Bqty%5Floaded%3Bqty%5Fcolli'
            '%7C%3B123%3B5%3B5%3B2%7C%3B124%3B5%3B5%3B2%7C%3B125%3B5%3B5%3B2',
        )
    ]
    assert events == expected


def test_packing_list_tracking_number_events(database):
    context = {
        'user_roles': [],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list_with_parcels('picking'))[0]
    database.sales_orders.insert_one(pl)
    schema.load(pl)
    events = PackingListSchema.generate_fpqueries(pl)

    expected = [
        (
            'sendOrder',
            (
                'sendOrder/refid__{}/uuid__{}/action__pakbon/'
                'barcode__123/qty__5/price__0.0/picked__5/'
                'barcode__124/qty__5/price__0.0/picked__5/'
                'barcode__125/qty__5/price__0.0/picked__5'
            ).format(escape(pl['docNumber']), escape(pl['customer']['_id'])),
        )
    ]
    assert events == expected

    events = PackingListSchema.generate_shipping_fp_event(pl)
    expected = [
        (
            'shipPackingList',
            'shipPackingList/refid__77ebf863%2D68c0%2D4029%2D9bfc%2Dfe5f9ba6f503/'
            'tracking_number__%27TN%2D1%27%2C%27TN%2D2%27%2C%27TN%2D3%27/'
            'barcodes__orderNumber%3Bean%3Bqty%5Foriginal%3Bqty%5Floaded%3Bqty%5Fcolli'
            '%7C%3B123%3B5%3B5%3B2%7C%3B124%3B5%3B5%3B2%7C%3B125%3B5%3B5%3B2',
        )
    ]
    assert events == expected


def test_cancel_event():
    data = {
        'docNumber': '77ebf863-68c0-4029-9bfc-fe5f9ba6f503',
        'orderNumber': 'PL-1',
        'customer': {'_id': CUST_ID},
        'products': [
            {
                'articleCode': 'A',
                'skus': [
                    {'barcode': '123', 'qty': 4, 'remarks': 'some remark'},
                    {'barcode': '124', 'qty': 6},
                    {'barcode': '125', 'qty': 1},
                ],
            },
            {
                'articleCode': 'B',
                'sizes': ['S', 'M', 'L', 'XL'],
                'skus': [{'barcode': '123', 'qty': 5, 'picked': 1}],
            },
        ],
    }
    events = PackingListSchema.generate_cancel_fpqueries(data)

    expected = [
        (
            'sendOrder',
            (
                'sendOrder/refid__{}/ordernumber__PL%2D1/uuid__{}/action__pakbon/'
                'barcode__123%3Asome%20remark/qty__0/price__0/picked__0/'
                'barcode__124/qty__0/price__0/picked__0/'
                'barcode__125/qty__0/price__0/picked__0/'
                'barcode__123/qty__0/price__0/picked__0'
            ).format(escape(data['docNumber']), escape(data['customer']['_id'])),
        )
    ]
    assert events == expected


@pytest.mark.parametrize(
    'sku,color_code,color_description',
    [
        (
            {
                'mainColorCode': '601',
                'subColorCode': '201',
                'colorCode': '',
                'mainColorDescription': 'black',
                'subColorDescription': 'white',
                'colorDescription': '',
            },
            '601/201',
            'black white',
        ),
        (
            {
                'mainColorCode': '601',
                'subColorCode': '',
                'mainColorDescription': 'black',
                'subColorDescription': '',
            },
            '601',
            'black',
        ),
        (
            {
                'mainColorCode': '601',
                'subColorCode': '201',
                'colorCode': '555',
                'mainColorDescription': 'black',
                'subColorDescription': 'white',
                'colorDescription': 'purple',
            },
            '555',
            'purple',
        ),
    ],
)
def test_sku_fill_in_color_fields(sku, color_code, color_description):
    sku = PackingListBaseSkuSchema.fill_in_color_fields(sku)
    assert sku['colorCode'] == color_code
    assert sku['colorDescription'] == color_description


def test_order_fill_in_color_fields():
    order = {
        'products': [
            {
                'skus': [
                    {
                        'mainColorCode': '601',
                        'subColorCode': '201',
                        'colorCode': '',
                        'mainColorDescription': 'black',
                        'subColorDescription': 'white',
                        'colorDescription': '',
                    }
                ]
            }
        ]
    }
    order = PackingListSchema.fill_in_color_fields(order)
    assert order['products'][0]['skus'][0]['colorCode'] == '601/201'
    assert order['products'][0]['skus'][0]['colorDescription'] == 'black white'


def test_packing_list_status_change_duplication(database):
    context = {
        'user_roles': ['picking-admin'],
        'user_id': ObjectId(),
        'db': database,
        'tenant_id': '2',
    }
    schema = PackingListSchema(context=context)
    pl = schema.load(packing_list('open'))[0]
    pl['orderPicker'] = context['user_id']
    database.sales_orders.insert_one(pl)
    pl['status'] = 'open'
    pl = schema.load(pl)[0]
    database.sales_orders.upsert_one({'_id': pl['_id']}, pl)
    pl['status'] = 'picking'
    pl['orderPicker'] = context['user_id']
    pl = schema.load(pl)[0]
    database.sales_orders.upsert_one({'_id': pl['_id']}, pl)
    pl['status'] = 'open'
    pl = schema.load(pl)[0]
    database.sales_orders.upsert_one({'_id': pl['_id']}, pl)
    pl['status'] = 'open'
    pl = schema.load(pl)[0]
    database.sales_orders.upsert_one({'_id': pl['_id']}, pl)
    pl['status'] = 'picking'
    pl = schema.load(pl)[0]
    database.sales_orders.upsert_one({'_id': pl['_id']}, pl)
    assert len(pl['status_history']) == 4


def packing_list(status):
    return copy.deepcopy(
        {
            'agentId': str(ObjectId()),
            '_id': str(uuid.uuid4()),
            'status': status,
            'docNumber': '77ebf863-68c0-4029-9bfc-fe5f9ba6f503',
            'reservationDate': '',
            'fixDate': '',
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
                            'picked': 5,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                        {
                            'barcode': '124',
                            'size': 'L',
                            'qty': 5,
                            'picked': 5,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                        {
                            'barcode': '125',
                            'size': 'XL',
                            'qty': 5,
                            'picked': 5,
                            'color': 'black',
                            'colorCodeSupplier': '',
                            'mainColorCode': '',
                        },
                    ],
                },
            ],
            'numberOfParcels': 2,
            'warehouseId': '12345',
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


def packing_list_with_parcels(status):
    pl = packing_list(status)
    pl['parcels'] = [
        {'id': 1, 'tracking_number': 'TN-1'},
        {'id': 2, 'tracking_number': 'TN-2'},
        {'id': 3, 'tracking_number': 'TN-3'},
    ]

    return pl
