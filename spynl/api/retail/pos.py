"""
Endpoints for managing POS workflow.

* get_new_pos_instance_id
"""

from pymongo import ReturnDocument

from spynl.api.auth.utils import lookup_tenant


def get_new_pos_instance_id(request):
    """
    Get a new unique POS instance ID.

    ---
    get:
      tags:
        - pos
      description: >
        Get a new unique (for the current tenant) POS instance ID.
        This can be used by POS instances to maintain a session independent of
        the browser or the user. This is an incremental number that denotes
        when a new browser session of the POS is started.
        This number is used in the printed receipt number as the middle digit
        (ie. warehouse-instanceId-receipt incremental number).
        Example: 51-1-100 is warehouse 51, with instance id 1
        and receipt number 100. Defaults to 1.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | int    | the new unique number per tenant
    """
    tid = request.current_tenant_id
    lookup_tenant(request.db, tid)  # ensure tenant exists

    # TODO: do we change this so modified gets added?
    tenant = request.db.pymongo_db.tenants.find_one_and_update(
        {'_id': tid},
        {'$inc': {'counters.posInstanceId': 1}},
        return_document=ReturnDocument.AFTER,
        projection={'counters.posInstanceId': 1, '_id': 0},
    )

    return dict(status='ok', data=tenant['counters']['posInstanceId'])


def init_pos(ctx, request):
    """
    Retrieve information to init the pos

    ---
    post:
      tags:
        - pos
      description: >
        Retrieve information to init the pos, currently returns the max receipt
        numbers

      responses:
        "200":
          schema:
            type: object
            properties:
              counters:
                type: object
                properties:
                  sales:
                    type: integer
                  consignments:
                    type: integer
                  transits:
                    type: integer
    """
    transaction_types = {2: 'sales', 9: 'consignments', 3: 'transits'}
    counters = {}
    for type_, name in transaction_types.items():
        result = request.db[ctx].find_one(
            {
                'device': str(request.cached_user['_id']),
                'tenant_id': request.requested_tenant_id,
                'type': type_,
            },
            {'receiptNr': 1},
            sort=[('receiptNr', -1)],
        )
        if result:
            counters[name] = result['receiptNr'] + 1
        else:
            counters[name] = 1

    return {'data': {'counters': counters}}
