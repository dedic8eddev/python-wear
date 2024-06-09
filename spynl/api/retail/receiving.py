"""Endpoints for Receiving Transaction."""
from bson.objectid import InvalidId, ObjectId
from marshmallow import fields

from spynl_schemas import Nested, ReceivingSchema

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction
from spynl.main.utils import required_args

from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.exceptions import DuplicateTransaction, WarehouseNotFound


class ReceivingFilterSchema(FilterSchema):
    _id = fields.UUID()
    warehouseId = fields.String()
    docNumber = fields.UUID()


class ReceivingGetSchema(MongoQueryParamsSchema):
    filter = Nested(ReceivingFilterSchema, load_default=dict)


@required_args('data')
def save(ctx, request):
    """
    Save a receiving order which is a document of good received from various
    suppliers.

    ---
    post:
      description: >
        Save a receiving order, by saving a new one or updating an existing one
        depending if one exists with the provided _id. This also informs foxpro by
        creating appropriate events for the order.

      tags:
        - data
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'receiving_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'

    """
    tenant_id = request.requested_tenant_id
    schema = ReceivingSchema(context={'tenant_id': tenant_id, 'db': request.db})
    data = schema.load(request.json_payload['data'])

    # validate warehouse exists and belongs to the tenant
    try:
        query = {'_id': ObjectId(data['warehouseId'])}
    except InvalidId:
        query = {'_id': data['warehouseId']}
    query['tenant_id'] = tenant_id

    warehouse = request.db.warehouses.find_one(query)
    if not warehouse:
        raise WarehouseNotFound()

    if request.db[ctx].count_documents(
        {
            '$or': [{'docNumber': data['docNumber']}, {'_id': data['_id']}],
            'status': 'complete',
        }
    ):
        raise IllegalAction(_('order-completed'))

    # validate uniqueness
    if request.db[ctx].count_documents(
        {
            'tenant_id': tenant_id,
            '_id': {'$ne': data['_id']},
            'docNumber': data['docNumber'],
        }
    ):
        raise DuplicateTransaction()

    counter = None
    if 'orderNumber' not in data:
        counter = (
            request.db.tenants.find_one(
                {'_id': tenant_id}, {'counters.receivings': 1, '_id': 0}
            )
            .get('counters', {})
            .get('receivings', 0)
            + 1
        )
        schema.format_ordernr(data, counter)

    request.db[ctx].upsert_one({'_id': data['_id']}, data)

    if counter:
        request.db.tenants.update_one(
            {'_id': tenant_id}, {'$set': {'counters.receivings': counter}}
        )

    if data.get('status') == 'complete':
        insert_foxpro_events(
            request, data, schema.generate_fpqueries, ('wh', warehouse['wh'])
        )

    return dict(status='ok', data=[str(data['_id'])])


def get(ctx, request):
    """
    Get receiving type of transactions for the requested tenant.

    ---
    post:
      description: >
        Get receiving type of transactions for the requested tenant. They can
        be filtered by parameters.
        Parameters are taken into account only when in request's body.

      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'receiving_get_parameters.json#/definitions/ReceivingGetSchema'
      responses:
        "200":
          schema:
            $ref: 'receiving_get_response.json#/definitions/GetResponse'
    """
    context = {'tenant_id': request.requested_tenant_id}
    input_data = request.json_payload
    data = ReceivingGetSchema(context=context).load(input_data)
    cursor = request.db.receivings.find(**data)
    return dict(status='ok', data=list(cursor))
