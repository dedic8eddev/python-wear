"""EOS(end of shift) endpoints."""

from datetime import datetime, timedelta

from marshmallow import EXCLUDE, Schema, fields, post_load, pre_load, validate
from pymongo import ASCENDING, DESCENDING

from spynl_schemas import EOSSchema
from spynl_schemas.fields import Nested, ObjectIdField

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction, SpynlException
from spynl.main.utils import required_args

from spynl.api.auth.utils import get_user_info
from spynl.api.hr.exceptions import UserDoesNotExist
from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.exceptions import WarehouseNotFound


class EOSFilterSchema(FilterSchema):
    _id = fields.String()
    cycleID = fields.String(metadata={'description': 'The unique shift identifier.'})
    status = fields.List(
        fields.String(),
        validate=[
            validate.ContainsOnly(
                ['generated', 'completed', 'rectification'],
                error='Only the following values are allowed: {choices}',
            ),
            validate.Length(min=1),
        ],
    )
    periodStart = fields.DateTime()
    periodEnd = fields.DateTime()

    warehouseId = fields.String()
    deviceId = fields.String()

    @pre_load
    def preprocess(self, data, **kwargs):
        if 'device.id' in data:
            data['deviceId'] = data.pop('device.id')

        # NOTE SPAPI-697 the following logic to deal with the periods is all for
        # backwards compatibility with sw6
        if 'periodStart' in data and '$exists' in data.get('periodStart', {}):
            data.pop('periodStart')
        if 'periodEnd' in data and '$exists' in data.get('periodEnd', {}):
            data.pop('periodEnd')

        if 'periodStart' in data and '$gte' in data.get('periodStart', {}):
            data['periodStart'] = data['periodStart'].pop('$gte')
        if 'periodEnd' in data and '$lte' in data.get('periodEnd', {}):
            data['periodEnd'] = data['periodEnd'].pop('$lte')
        return data

    @post_load
    def postprocess(self, data, **kwargs):
        if 'warehouseId' in data:
            data['shop.id'] = data.pop('warehouseId')

        if 'deviceId' in data:
            data['device.id'] = data.pop('deviceId')

        for field, operator in [('periodStart', '$gte'), ('periodEnd', '$lte')]:
            if field in data:
                data[field] = {operator: data[field]}

        if 'status' in data:
            data['$or'] = [{'status': s} for s in data.pop('status')]

        if 'periodStart' not in data:
            data['periodStart'] = {'$exists': True}

        if 'periodEnd' not in data:
            data['periodEnd'] = {'$exists': True}
        return data


class EOSGetSchema(MongoQueryParamsSchema):
    filter = Nested(EOSFilterSchema, load_default=dict)


@required_args('data')
def save(ctx, request):
    """
    Add a new or edit an eos transaction.

    ---
    post:
      description: >
        Create a new or edit an eos transaction. This also informs foxpro by
        creating an event if the eos is completed.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'eos_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    tenant_id = request.requested_tenant_id
    user_info = get_user_info(request, purpose='stamp')['user']
    schema = EOSSchema(
        context={'db': request.db, 'tenant_id': tenant_id, 'user_id': user_info['_id']}
    )

    data = request.json_payload['data']
    if isinstance(data, list):
        data = data[0]

    data = schema.load(data)

    request.db[ctx].upsert_one({'_id': data['_id']}, data, user=user_info)

    if data['status'] == 'completed':
        insert_foxpro_events(request, data, schema.generate_fpqueries)

    return dict(status='ok', data=[str(data['_id'])])


def get(ctx, request):
    """
    Get eos transactions

    ---
    post:
      description: >
        Get endpoint for eos documents
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'eos_get_parameters.json#/definitions/EOSGetSchema'
      responses:
        "200":
          schema:
            $ref: 'eos_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    context = {'tenant_id': request.requested_tenant_id}
    data = request.json_payload
    data = EOSGetSchema(context=context).load(request.json_payload)

    cursor = request.db[ctx].find(**data)
    return dict(status='ok', data=list(cursor))


def init(ctx, request):
    """
    This endpoint will create a new EOS document if an open document does
    not already exist

    ---
    post:
      description: >
        This endpoint will create a new EOS document if an open document does
        not already exist
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    tenant_id = request.requested_tenant_id
    user_info = get_user_info(request, purpose='stamp')['user']
    # note: this way the endpoint should not be used by sw-users
    device_user = request.cached_user

    if not device_user.get('wh'):
        raise WarehouseNotFound()

    location = request.db.warehouses.find_one(
        {'tenant_id': request.requested_tenant_id, 'wh': device_user['wh']}
    )

    if not location:
        raise WarehouseNotFound()

    eos = _get_last_open(
        request.db[ctx],
        {
            'filter': {
                'device.id': device_user['deviceId'],
                'shop.id': location['wh'],
                'tenant_id': tenant_id,
            }
        },
    )

    # If there is no eos matching the filter, create a new one and return it
    if eos:
        eos = eos[0]
    else:
        schema = EOSSchema(
            context={
                'db': request.db,
                'tenant_id': tenant_id,
                'user_id': user_info['_id'],
            }
        )
        eos = schema.load(
            {
                'device': {
                    'id': device_user['deviceId'],
                    'name': device_user['fullname'],
                },
                'shop': {'id': location['wh'], 'name': location['name']},
                'cashier': {'id': '', 'name': '', 'fullname': ''},
            }
        )

        request.db[ctx].insert_one(eos)

    return dict(status='ok', data=[eos])


class EOSResetFilterSchema(FilterSchema):
    _id = fields.String(required=True)

    class Meta:
        unknown = EXCLUDE
        fields = ('_id',)


class EOSResetSchema(Schema):
    filter = Nested(EOSResetFilterSchema, load_default=dict)


def reset(ctx, request):
    """
    Reset an existing eos document

    ---
    post:
      description: >
        Reset an existing eos document, essentially reopening a shift.
      parameters:
        - name: body
          in: body
          description: the filter
          required: true
          schema:
            $ref: 'eos_reset.json#/definitions/EOSResetSchema'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = request.json_payload
    tenant_id = request.requested_tenant_id
    user_info = get_user_info(request, purpose='stamp')['user']

    reset_filter = EOSResetSchema(context={'tenant_id': tenant_id}).load(input_data)
    reset_filter.update(
        {
            # These are the fields which should NOT be reset
            'projection': [
                'created',
                'cashier',
                '_id',
                'cycleID',
                'shop',
                'device',
                'periodStart',
                'status',
            ]
        }
    )

    eos = request.db[ctx].find_one(**reset_filter)
    if not eos:
        raise IllegalAction(_('document-not-found'))

    # We needed the original status to check the ability to reset it
    # now we can remove it
    if eos.pop('status') != 'completed':
        raise IllegalAction(_('eos-must-be-completed'))

    # Get a clean document, using some of the previous values
    schema = EOSSchema(
        context={'db': request.db, 'tenant_id': tenant_id, 'user_id': user_info['_id']},
        exclude=['periodStart'],
    )
    reset_eos = schema.load(eos)

    # The date needs to be updated here, otherwise the model complains
    reset_eos.update({'periodStart': eos['periodStart']})

    request.db[ctx].update_one(reset_filter['filter'], {'$set': reset_eos})

    insert_foxpro_events(request, reset_eos, schema.generate_reset_fpqueries)

    return dict(status='ok', data=[str(reset_eos['_id'])])


class EOSOverviewFilter(Schema):
    deviceId = fields.String(required=True)

    class Meta:
        unknown = EXCLUDE

    @post_load
    def handle_device_id(self, data, **kwargs):
        data['device.id'] = data.pop('deviceId')
        return data

    @post_load
    def handle_tenant_id(self, data, **kwargs):
        tenant_id = self.context['tenant_id']
        data.update({'tenant_id': {'$in': [tenant_id]}})
        return data


class EOSOverviewSchema(Schema):
    filter = Nested(EOSOverviewFilter, load_default=dict)

    class Meta:
        unknown = EXCLUDE

    @staticmethod
    def build_end_balance_query(data, period_end):
        q = {
            'filter': {
                'device.id': data['filter']['device.id'],
                'tenant_id': data['filter']['tenant_id'],
                'status': {'$in': ['completed', 'rectification']},
                'periodEnd': {'$lte': period_end},
                'active': True,
            },
            'projection': {'endBalance': 1, '_id': 0},
            'sort': [('periodEnd', -1)],
        }
        return q

    @staticmethod
    def build_receipt_query(data, cycle_id):
        """
        This query is run on transactions, so the cycleID is stored in the shift field.
        """

        def sum(type_):
            return {
                '$sum': {
                    '$cond': [{'$eq': ['$receipt.type', type_]}, '$receipt.price', 0]
                }
            }

        return [
            {
                '$match': {
                    'tenant_id': data['filter']['tenant_id'],
                    'shift': cycle_id,
                    'type': 2,
                    'active': True,
                }
            },
            {'$project': {'_id': 0, 'receipt.price': 1, 'receipt.type': 1}},
            {'$unwind': '$receipt'},
            {
                '$group': {
                    **{
                        key: sum(type_)
                        for key, type_ in [
                            ('creditReceipt', 'T'),
                            ('couponOut', 'I'),
                            ('couponIn', 'U'),
                            ('storeCredit', 'O'),
                        ]
                    },
                    '_id': 0,
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'couponIn': 1,
                    'couponOut': {'$multiply': ['$couponOut', -1]},
                    'creditReceipt': 1,
                    'storeCredit': 1,
                }
            },
        ]

    @staticmethod
    def build_payment_totals_query(data, cycle_id):
        """
        This query is run on transactions, so the cycleID is stored in the shift field.
        """
        q = [
            {
                '$match': {
                    'tenant_id': data['filter']['tenant_id'],
                    'shift': cycle_id,
                    '$or': [{'type': 2}, {'type': 9}],
                    'active': True,
                }
            },
            {
                '$group': {
                    '_id': 0,
                    'change': {'$sum': '$change'},
                    'cash': {'$sum': '$payments.cash'},
                    'consignment': {'$sum': '$payments.consignment'},
                    'creditcard': {'$sum': '$payments.creditcard'},
                    'creditreceipt': {'$sum': '$payments.creditreceipt'},
                    'pin': {'$sum': '$payments.pin'},
                    'storecredit': {'$sum': '$payments.storecredit'},
                    'deposit': {
                        '$sum': {
                            '$cond': [
                                {'$lt': ['$payments.withdrawel', 0]},
                                '$payments.withdrawel',
                                0,
                            ]
                        }
                    },
                    'withdrawel': {
                        '$sum': {
                            '$cond': [
                                {'$gt': ['$payments.withdrawel', 0]},
                                '$payments.withdrawel',
                                0,
                            ]
                        }
                    },
                }
            },
            {
                '$project': {
                    '_id': 0,
                    'cash': 1,
                    'change': 1,
                    'consignment': 1,
                    'creditcard': 1,
                    'creditreceipt': 1,
                    'deposit': {'$multiply': ['$deposit', -1]},
                    'pin': 1,
                    'storecredit': 1,
                    'withdrawel': 1,
                }
            },
        ]
        return q

    @staticmethod
    def calculate_expected_cash_in_drawer(start_balance, payment_totals):
        """
        Calculate the amount that should be in the cash register at the end
        of the day given the starting balance (= previous day's end balance)
        and payments.
        """
        expected_cash = start_balance
        expected_cash += payment_totals.get('cash', 0)
        expected_cash -= payment_totals.get('change', 0)

        return expected_cash


def get_eos_overview(ctx, request):
    """
    Return the last open EOS documents for a device and shift, payment and
    receipt totals, and the opening balance. This endpoint prepares the eos for closing.

    ---
    post:
      description: >
        This endpoint will return the last EOS documents which have
        a status of "open". This is useful for when a user forgets to
        close an older EOS document. If they are not closed sequentially,
        then the EOS reporting will not be correct.
      parameters:
        - name: body
          in: body
          description: the filter parameters
          required: true
          schema:
            $ref: 'eos_overview.json#/definitions/EOSOverviewSchema'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = request.json_payload
    schema = EOSOverviewSchema(context={'tenant_id': request.requested_tenant_id})

    data = schema.load(input_data)

    eos = request.db.eos
    transactions = request.db.transactions

    open_shifts = _get_last_open(eos, data)
    if not open_shifts:
        raise SpynlException(_('no-open-shifts'))

    period_end = open_shifts[0]['periodStart']
    cycle_id = open_shifts[0]['cycleID']

    # end_balance is the end balance of the PREVIOUS shift
    end_balance_query = schema.build_end_balance_query(data, period_end)
    try:
        end_balance = eos.find_one(**end_balance_query)['endBalance']
    except (TypeError, KeyError):
        end_balance = 0

    payment_totals_query = schema.build_payment_totals_query(data, cycle_id)
    payment_totals = list(transactions.aggregate(payment_totals_query)) or [{}]

    receipt_totals_query = schema.build_receipt_query(data, cycle_id)
    receipt_totals = list(transactions.aggregate(receipt_totals_query)) or [{}]

    return {
        'data': {
            'paymentTotals': payment_totals[0],
            'receiptTotals': receipt_totals[0],
            'expectedCashInDrawer': schema.calculate_expected_cash_in_drawer(
                end_balance, payment_totals[0]
            ),
            'endBalance': end_balance,
            'openShifts': open_shifts,
        }
    }


def _get_last_open(collection, data):
    query = {k: v for k, v in data['filter'].items() if k != 'periodEnd'}
    # find newest closed or rectification
    last_completed = collection.find_one(
        {**query, 'status': {'$in': ['completed', 'rectification']}},
        sort=[('periodStart', DESCENDING)],
    )

    query = {**query, 'status': 'generated', 'active': True}
    if last_completed:
        query['periodStart'] = {'$gt': last_completed['periodStart']}

    # find all open shifts newer than the newest closed and sort
    return list(collection.find(query, sort=[('periodStart', ASCENDING)]))


class EOSRectifySchema(Schema):
    userId = ObjectIdField(
        required=True, metadata={'description': 'The object id of the device user.'}
    )
    value = fields.Float(
        required=True,
        metadata={
            'description': 'The amount both openingBalance and endBalance should be '
            'set to.'
        },
    )
    remarks = fields.String(
        load_default='', metadata={'description': 'Optional remarks.'}
    )


def rectify(ctx, request):
    """
    Create a rectification document for eos.

    ---
    post:
      description: >
        This endpoint will create a new EOS rectification document.
      parameters:
        - name: body
          in: body
          description: the filter
          required: true
          schema:
            $ref: 'eos_rectify.json#/definitions/EOSRectifySchema'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = EOSRectifySchema().load(request.json_payload)

    device_user = request.db.users.find_one(
        {'_id': input_data['userId'], 'tenant_id': request.requested_tenant_id}
    )

    if not device_user:
        raise UserDoesNotExist(user=input_data['userId'])

    if not device_user.get('wh'):
        raise WarehouseNotFound()

    location = request.db.warehouses.find_one(
        {'tenant_id': request.requested_tenant_id, 'wh': device_user['wh']}
    )

    if not location:
        raise WarehouseNotFound()

    # Reject the rectification if another one was made in the last 24 hours.
    previous_rectification = request.db[ctx].find_one(
        {
            'status': 'rectification',
            'tenant_id': request.requested_tenant_id,
            'device.id': device_user['deviceId'],
            'created.date': {'$gt': datetime.now() - timedelta(days=1)},
        }
    )
    if previous_rectification:
        raise SpynlException(_('previous-rectification-found'))

    schema = EOSSchema(
        context={
            'db': request.db,
            'tenant_id': request.requested_tenant_id,
            'user_id': device_user['_id'],
        }
    )
    data = schema.load(
        {
            'openingBalance': input_data['value'],
            'endBalance': input_data['value'],
            'remarks': input_data['remarks'],
            'status': 'rectification',
            'device': {'id': device_user['deviceId'], 'name': device_user['fullname']},
            'shop': {'id': location['wh'], 'name': location['name']},
            'cashier': {'id': '', 'name': '', 'fullname': ''},
        }
    )
    request.db[ctx].insert_one(data)

    return {'data': [data]}
