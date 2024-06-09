"""Endpoints for changing shop's inventory."""

from spynl_schemas import InventorySchema

from spynl.main.utils import required_args

from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.exceptions import DuplicateTransaction, WarehouseNotFound
from spynl.api.retail.receiving import ReceivingGetSchema


class InventoryGetSchema(ReceivingGetSchema):
    pass


@required_args('data')
def add(request):
    """
    Add transaction to update the quantities of products in shop's inventory.

    ---
    post:
      description: >
        Create a transaction to update the quantities of the given products in
        the shop's inventory. This also informs foxpro by creating appropriate
        events for the transaction.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'inventory_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    tenant_id = request.requested_tenant_id

    schema = InventorySchema(context=dict(tenant_id=tenant_id))

    data = schema.load(request.args['data'])
    # validate transaction uniqueness
    if request.db.inventory.count({'docNumber': data['docNumber']}) > 0:
        raise DuplicateTransaction(developer_message='The uuid already exists.')

    # validate warehouse exists and belongs to the tenant
    query = dict(_id=data['warehouseId'], tenant_id={'$in': [tenant_id]})
    warehouse = request.db.warehouses.find_one(query, {'wh': 1})
    if not warehouse:
        raise WarehouseNotFound()

    insert_foxpro_events(
        request, data, schema.generate_fpqueries, ('wh', warehouse['wh'])
    )
    # save transaction to mongo
    result = request.db[request.context].insert_one(data)

    return dict(status='ok', data=[str(result.inserted_id)])


def get(request):
    """
    Get inventory transactions for the requested tenant.

    ---
    post:
      description: >
        Get inventory transactions for the requested tenant. The transactions
        can be filtered with parameters.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'inventory_get_parameters.json#/definitions/InventoryGetSchema'
      responses:
        "200":
          schema:
            $ref: 'inventory_get_response.json#/definitions/GetResponse'

      tags:
        - data
    """
    context = {'tenant_id': request.requested_tenant_id}
    input_data = request.json_payload
    data = InventoryGetSchema(context=context).load(input_data)
    cursor = request.db.inventory.find(**data)
    return dict(status='ok', data=list(cursor))
