from marshmallow import fields, post_load, validate

from spynl_schemas import Nested

from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema


class LogisticsTransactionsFilterSchema(FilterSchema):
    _id = fields.UUID()
    text = fields.String(
        metadata={
            'description': 'This field allows a plain-text search of the '
            'supplierOrderReference, orderNumber, and warehouseId fields.'
        }
    )
    status = fields.String(
        validate=validate.OneOf(['draft', 'complete', 'unconfirmed'])
    )
    type = fields.String(
        validate=validate.OneOf(['receivings', 'transits', 'inventory'])
    )

    @post_load
    def text_search(self, data, **kwargs):
        if 'text' in data:
            val = data.pop('text')
            data['$or'] = [
                {'supplierOrderReference': val},
                {'orderNumber': val},
                {'warehouseId': val},
            ]
        return data


class LogisticsTransactionsGetSchema(MongoQueryParamsSchema):
    filter = Nested(LogisticsTransactionsFilterSchema, load_default=dict)

    @post_load
    def set_projection(self, data, **kwargs):
        if '_id' not in data['filter'] and 'projection' not in data:
            data['projection'] = [
                '_id',
                'status',
                'created',
                'modified',
                'totalQty',
                'orderNumber',
                'supplierOrderReference',
                'warehouseName',
            ]
        return data

    @post_load
    def set_default_sort(self, data, **kwargs):
        if not data.get('sort'):
            data['sort'] = [('modified.date', -1)]
        return data


def get(ctx, request):
    """
    Get logistics transactions.

    ---
    post:
      description: >
        Get a list of transactions for the requested tenant. They can be
        filtered by the following parameters.
        Parameters are taken into account only when in request's body.
        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | array  | array of inventory and/or receiving transactions.

      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'logistics_transactions_parameters.json#/definitions/\
LogisticsTransactionsGetSchema'
      tags:
        - data
    """
    input_data = request.json_payload

    schema = LogisticsTransactionsGetSchema(
        context={'tenant_id': request.requested_tenant_id}
    )
    data = schema.load(input_data)
    type_ = data['filter'].pop('type', None)

    if not type_:
        query = build_query(data, type_='receivings')
        receivings = list(request.db.receivings.aggregate(query))
        query = build_query(data, type_='inventory')
        inventory = list(request.db.inventory.aggregate(query))
        result = sorted(
            inventory + receivings, key=lambda i: i['created']['date'], reverse=True
        )
    else:
        query = build_query(data, type_=type_)
        result = list(request.db[type_].aggregate(query))

    return dict(status='ok', data=result)


def build_query(data, type_=None):
    query = [
        {'$match': data['filter']},
        {
            '$lookup': {
                'from': 'warehouses',
                'localField': 'warehouseId',
                'foreignField': '_id',
                'as': 'warehouse',
            }
        },
        {
            '$addFields': {
                'type': type_,
                'warehouseName': {'$arrayElemAt': ['$warehouse.name', 0]},
            }
        },
    ]
    if 'projection' in data and isinstance(data['projection'], list):
        query.append(
            {'$project': {k: 1 for k in data['projection'] + ['type', 'warehouseName']}}
        )
    else:
        query.append({'$project': {'_id': 0, 'warehouse': 0, 'modified_history': 0}})

    query.append({'$sort': {'created.date': -1}})
    return query
