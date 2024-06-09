from marshmallow import fields
from pyramid.httpexceptions import HTTPNotFound

from spynl_schemas import DeliveryPeriodSchema, Nested, Schema

from spynl.main.utils import required_args

from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema


class DeliveryPeriodFilter(FilterSchema):
    _id = fields.UUID()
    label = fields.String()


class DeliveryPeriodGetSchema(MongoQueryParamsSchema):
    filter = Nested(DeliveryPeriodFilter, load_default=dict)


class DeliveryPeriodDeleteFilter(Schema):
    _id = fields.UUID(required=True)


class DeliveryPeriodDeleteSchema(Schema):
    filter = Nested(DeliveryPeriodDeleteFilter, load_default=dict)


def get(ctx, request):
    """
    Get delivery periods.

    ---
    post:
      description: >
        Get delivery periods.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: >
              'delivery_periods_get_parameters.json#/definitions/DeliveryPeriodGetSchema'
      responses:
        "200":
          schema:
            $ref: 'delivery_periods_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    schema = DeliveryPeriodGetSchema(context={'tenant_id': request.requested_tenant_id})

    data = schema.load(request.json_payload)

    labels = request.db[ctx].find(**data)
    return {'data': list(labels)}


@required_args('data')
def save(ctx, request):
    """
    Save a delivery period.

    ---
    post:
      description: >
        Save a delivery period.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'delivery_periods_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = request.json_payload['data']

    schema = DeliveryPeriodSchema(
        context={'tenant_id': request.requested_tenant_id, 'db': request.db}
    )
    data = schema.load(input_data)
    request.db[ctx].upsert_one({'_id': data['_id']}, data)
    return {'data': [str(data['_id'])]}


def delete(ctx, request):
    """
    Delete a delivery period.

    ---
    post:
      description: >
        Save a delivery period.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'delivery_periods_del.json#/definitions/DeliveryPeriodDeleteSchema'
      responses:
        "200":
             description: success
      tags:
        - data
    """
    data = DeliveryPeriodDeleteSchema().load(request.json_payload)
    result = request.db[ctx].delete_one(**data)
    if not result.deleted_count:
        raise HTTPNotFound
    return {}
