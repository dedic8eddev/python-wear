"""Endpoints for Sale Transaction."""
from spynl_schemas import BufferSchema

from spynl.main.utils import required_args


@required_args('data')
def add(ctx, request):
    """
    Add a new buffer

    ---
    post:
      description: >
        Create a new buffer transaction.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        data      | dict         | &#10004; | The details for the
        new buffer such as receipt, payments etc. it must conform with the
        [Sale model](
        https://gitlab.com/softwearconnect/spynl.data/blob/master/spynl_schemas/buffer.py).\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | array  | array of new entry id.

      tags:
        - data
    """
    tenant_id = request.requested_tenant_id
    vat = request.db.tenants.find_one({'_id': tenant_id})['settings'].get('vat')
    context = {'vat_settings': vat, 'tenant_id': tenant_id, 'db': request.db}
    schema = BufferSchema(context=context)

    # NOTE Buffer is a mongo resource so it will be wrapped in a list. Get the
    # first item.
    data = schema.load(request.args['data'][0])

    result = request.db[ctx].insert_one(data)

    return dict(status='ok', data=[str(result.inserted_id)])
