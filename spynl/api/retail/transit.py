"""Endpoints for transit transaction."""
from marshmallow import fields, post_load

from spynl_schemas import Nested, TransitSchema

from spynl.main.utils import required_args

from spynl.api.auth.utils import get_user_info
from spynl.api.mongo.query_schemas import MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.utils import TransactionFilterSchema


class TransitFilterSchema(TransactionFilterSchema):
    type = fields.Constant(3)
    transitPeer = fields.String()

    @post_load
    def handle_transit_peer(self, data, **kwargs):
        if 'transitPeer' in data:
            data['transit.transitPeer'] = data.pop('transitPeer')
        return data


class TransitGetSchema(MongoQueryParamsSchema):
    filter = Nested(TransitFilterSchema, load_default=dict)


@required_args('data')
def add(ctx, request):
    """
    Add a new transit transaction.

    ---
    post:
      description: >
        Create a new transit transaction. This also informs foxpro by creating
        appropriate events for the transaction.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'transit_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    tenant_id = request.requested_tenant_id
    schema = TransitSchema(context={'db': request.db, 'tenant_id': tenant_id})

    data = schema.load(request.json_payload['data'])

    saved_transit = request.db[ctx].insert_one(data)
    insert_foxpro_events(request, data, TransitSchema.generate_fpqueries)

    return dict(status='ok', data=[str(saved_transit.inserted_id)])


@required_args('data')
def save(ctx, request):
    """
    Add a new or edit a transit transaction.

    ---
    post:
      description: >
        Create a new or edit a transit transaction. This also informs foxpro by
        creating appropriate events for the transaction.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'transit_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    schema = TransitSchema(
        context={'db': request.db, 'tenant_id': request.requested_tenant_id}
    )

    data = schema.load(request.json_payload['data'])

    user_info = get_user_info(request, purpose='stamp')['user']
    result = request.db[ctx].upsert_one({'_id': data['_id']}, data, user=user_info)
    if result.upserted_id:
        insert_foxpro_events(request, data, TransitSchema.generate_fpqueries)

    return dict(status='ok', data=[str(data['_id'])])


def get(ctx, request):
    """
    Get transit transactions

    ---
    post:
      description: >
        Get a list of transit transactions for the requested tenant. They can be
        filtered by the following parameters.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'transit_get_parameters.json#/definitions/TransitGet'
      responses:
        "200":
          schema:
            $ref: 'transit_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    context = {'tenant_id': request.requested_tenant_id}
    data = TransitGetSchema(context=context).load(request.json_payload)
    cursor = request.db[ctx].find(**data)
    return dict(status='ok', data=list(cursor))
