import re

import bson
from marshmallow import fields, post_load

from spynl_schemas import Nested, ObjectIdField, WholesaleCustomerSchema

from spynl.main.utils import required_args

from spynl.api.auth.utils import check_agent_access, get_user_region
from spynl.api.hr.utils import find_unused, generate_random_cust_id
from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.utils import limit_wholesale_queries


class _WholesaleCustomerFilterSchema(FilterSchema):
    _id = fields.UUID()
    cust_id = fields.String()
    name = fields.String(metadata={'description': 'Regex style search'})
    legalName = fields.String()
    agentId = ObjectIdField()

    @post_load
    def _post_load(self, data, **kwargs):
        if 'name' in data:
            data['name'] = {
                '$regex': bson.regex.Regex(re.escape(data['name'])),
                '$options': 'i',
            }

        data = limit_wholesale_queries(data, self.context)
        return data


class WholesaleCustomerGetSchema(MongoQueryParamsSchema):
    filter = Nested(_WholesaleCustomerFilterSchema, load_default=dict)


def query_wholesale_customers(ctx, request, count=False):
    input_data = request.json_payload

    schema = WholesaleCustomerGetSchema(
        context={
            'tenant_id': request.requested_tenant_id,
            'user_id': request.authenticated_userid,
            'request': request,
            'region': get_user_region(request.cached_user),
        }
    )
    data = schema.load(input_data)

    if count:
        # properly we should use a different schema for this, without projection
        data.pop('projection', None)
        return request.db[ctx].count_documents(**data)

    return request.db[ctx].find(**data)


def get(ctx, request):
    """
    Get wholesale customer(s).

    ---
    post:
      description: >
        Customers can be filtered by _id, name and legalName.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'wholesale_customer_get_parameters.json#/definitions/\
WholesaleCustomerGetSchema'
      responses:
        "200":
          schema:
            $ref: 'wholesale_customer_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    cursor = query_wholesale_customers(ctx, request)
    return dict(data=list(cursor))


def count(ctx, request):
    """
    Count wholesale customer(s).

    ---
    post:
      description: >
        Count the number of wholesale customers

      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'wholesale_customer_get_parameters.json#/definitions/\
WholesaleCustomerGetSchema'
      responses:
        "200":
          schema:
            type: object
            properties:
              status:
                type: string
                description: "'ok' or 'error'"
              count:
                type: integer
                description: "The number of customers found"
      tags:
        - data
    """
    count = query_wholesale_customers(ctx, request, count=True)
    return dict(count=count)


@required_args('data')
def save(ctx, request):
    """
    Save a given wholesale customer. Save have upsert behavior.

    ---
    post:
      description: >
        Save a given wholesale customer. Save has upsert behavior.
        This also informs foxpro by creating an event.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'wholesale_customer_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = request.json_payload.get('data', {})

    tenant_id = request.requested_tenant_id
    schema = WholesaleCustomerSchema(context=dict(tenant_id=tenant_id, db=request.db))
    customer = schema.load(input_data)

    for k, v in [
        ('cust_id', find_unused(request.db[ctx], 'cust_id', generate_random_cust_id)),
        ('agentId', request.authenticated_userid),
        ('agentEmail', request.cached_user.get('email', '')),
    ]:
        customer.setdefault(k, v)
    check_agent_access(customer['agentId'], request)

    request.db[ctx].upsert_one({'_id': customer['_id']}, customer)

    # Do not generate an event if the customer/save comes from foxpro:
    # (this feature is not documented)
    if not request.json_payload.get('doNotGenerateEvent'):
        insert_foxpro_events(request, customer, schema.generate_fpqueries)

    return dict(data=[str(customer['_id'])])
