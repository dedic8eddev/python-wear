"""Endpoints for customers collection."""
from pymongo.errors import DuplicateKeyError

from spynl_schemas import RetailCustomerSchema

from spynl.main.utils import required_args

from spynl.api.hr.exceptions import ExistingCustomer
from spynl.api.hr.utils import (
    find_unused,
    generate_random_cust_id,
    generate_random_loyalty_number,
)
from spynl.api.mongo.utils import insert_foxpro_events


@required_args('data')
def add(ctx, request):
    """
    Add a new customer.

    ---
    post:
      description: >
        Create a new customer in the database with his personal details. This
        also informs foxpro by creating an event.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'retail_customers_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    tenant_id = request.requested_tenant_id

    data = request.args['data'][0]
    data.update(
        {
            'cust_id': find_unused(
                request.db[ctx.collection], 'cust_id', generate_random_cust_id
            ),
            'loyalty_no': find_unused(
                request.db[ctx.collection], 'loyalty_no', generate_random_loyalty_number
            ),
        }
    )
    schema = RetailCustomerSchema(context=dict(tenant_id=tenant_id))
    customer = schema.load(data)

    try:
        result = request.db[ctx].insert_one(customer)
    except DuplicateKeyError:
        raise ExistingCustomer
    insert_foxpro_events(request, customer, schema.generate_fpqueries)

    return {'status': 'ok', 'data': [str(result.inserted_id)]}


@required_args('data')
def save(ctx, request):
    """
    Save(update) a given customer if no _id is passed create a new one.

    ---
    post:
      description: >
        Given an _id in data save the new information to the existing customer.
        If the _id is not included in the data then create a new customer with
        the given customer information.This also informs foxpro by creating an
        event.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'retail_customers_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    data = request.args['data'][0]

    tenant_id = request.requested_tenant_id
    schema = RetailCustomerSchema(context=dict(tenant_id=tenant_id))
    customer = schema.load(data)

    # NOTE upsert_one will prevent any existing values from being overridden.
    customer.setdefault(
        'cust_id',
        find_unused(request.db[ctx.collection], 'cust_id', generate_random_cust_id),
    )
    customer.setdefault(
        'loyalty_no',
        find_unused(
            request.db[ctx.collection], 'loyalty_no', generate_random_loyalty_number
        ),
    )

    request.db[ctx].upsert_one(
        {'_id': customer['_id']},
        customer,
        immutable_fields=['cust_id', 'loyalty_no', 'tenant_id'],
    )

    # Do not generate an event if the customer/save comes from foxpro:
    # (this feature is not documented)
    if not request.args.get('doNotGenerateEvent'):
        insert_foxpro_events(request, customer, schema.generate_fpqueries)

    return {'data': [str(customer['_id'])]}
