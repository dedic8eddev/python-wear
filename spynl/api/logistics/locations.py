"""
New style endpoints for warehouses.
"""
import re

import bson
from bson.objectid import InvalidId, ObjectId
from marshmallow import fields, post_load

from spynl_schemas import Nested, Warehouse

from spynl.locale import SpynlTranslationString as _

from spynl.main.utils import required_args

from spynl.api.auth.exceptions import Forbidden
from spynl.api.auth.tenantid_utils import MASTER_TENANT_ID
from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events


class LocationsFilter(FilterSchema):
    _id = fields.String(
        metadata={
            'description': '_id for the warehouse, should be an ObjectId for new '
            "warehouses, but existing warehouses can have string _id's"
        }
    )
    name = fields.String()
    ean = fields.String()
    wh = fields.String(data_key='warehouseId')
    fullname = fields.String()
    text = fields.String()

    @post_load
    def handle_id(self, data, **kwargs):
        """cast to objectid if objectid, otherwise, leave as string"""
        try:
            data['_id'] = ObjectId(data['_id'])
        except (InvalidId, KeyError):
            pass
        return data

    @post_load
    def postprocess(self, data, **kwargs):
        if 'text' in data:
            pattern = {
                '$regex': bson.regex.Regex(re.escape(data.pop('text'))),
                '$options': 'i',
            }
            data['$or'] = [{f: pattern} for f in ['fullname', 'name']]
        return data


class LocationsGetSchema(MongoQueryParamsSchema):
    filter = Nested(LocationsFilter, load_default=dict)


def get(ctx, request):
    """
    Get locations (warehouses).

    ---
    post:
      description: >
        Get locations/warehouses.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'locations_get_parameters.json#/definitions/LocationsGetSchema'
      responses:
        "200":
          schema:
            $ref: 'locations_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    schema = LocationsGetSchema(context={'tenant_id': request.requested_tenant_id})

    data = schema.load(request.json_payload)

    locations = request.db[ctx].find(**data)
    return {'data': Warehouse(many=True).dump(list(locations))}


def count(ctx, request):
    """
    Count locations (warehouses).

    ---
    post:
      description: >
        count locations/warehouses.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'locations_get_parameters.json#/definitions/LocationsGetSchema'
      responses:
        "200":
          schema:
            type: object
            properties:
              status:
                type: string
                description: ok or error
              count:
                type: integer
                description: the number of locations that match the parameters.
      tags:
        - data
    """
    input_data = request.json_payload.get('data', {})
    schema = LocationsGetSchema(context={'tenant_id': request.requested_tenant_id})

    data = schema.load(input_data)
    # Should in principle use a new schema for count, without projection. (Cannot use
    # just exclude, because the set_projection method needs to be overwritten)
    data.pop('projection', None)

    return {'count': request.db[ctx].count(**data)}


@required_args('data')
def save(ctx, request):
    """
    Save a warehouse.

    ---
    post:
      description: >
        Save a warehouse. If the warehouse doesn't exist yet, you cannot use
        this endpoint to add it.

        Non-master user cannot change 'wh'
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'locations_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = request.json_payload.get('data', {})

    if request.current_tenant_id != MASTER_TENANT_ID:
        exclude = ['wh']
    else:
        exclude = []
    schema = Warehouse(
        context={'tenant_id': request.requested_tenant_id, 'db': request.db},
        exclude=exclude,
    )
    data = schema.load(input_data)

    count = request.db[ctx].count({'_id': data.get('_id')})
    if not count:
        raise Forbidden(_('add-not-allowed'))

    request.db[ctx].upsert_one({'_id': data['_id']}, data, immutable_fields=exclude)

    # find warehouse because excluded fields are needed for event
    warehouse = request.db[ctx].find_one({'_id': data['_id']})

    insert_foxpro_events(request, warehouse, schema.generate_fpqueries)

    return {'data': [str(data['_id'])]}


@required_args('data')
def add(ctx, request):
    """
    Add a warehouse.

    ---
    post:
      description: >
        Save a warehouse. If the warehouse exists already, you cannot use this
        endpoint to edit it.
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
    input_data = request.json_payload.get('data', {})

    schema = Warehouse(
        context={'tenant_id': request.requested_tenant_id, 'db': request.db}
    )
    data = schema.load(input_data)

    added_location = request.db[ctx].insert_one(data)

    insert_foxpro_events(request, data, schema.generate_fpqueries)

    return dict(status='ok', data=[str(added_location.inserted_id)])
