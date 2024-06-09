from marshmallow import fields, post_load

from spynl_schemas import Nested

from spynl.api.mongo.query_schemas import MongoQueryParamsSchema
from spynl.api.retail.utils import TransactionFilterSchema

FIELDS = [
    'nr',
    'type',
    'shop',
    'status',
    'created',
    'overallReceiptDiscount',
    'transit',
    'totalAmount',
    'totalDiscount',
    'totalDiscountCoupon',
    'totalCoupon',
    'totalPaid',
    'fiscal_receipt_nr',
    'fiscal_shift_nr',
]


class TransactionGetSchema(MongoQueryParamsSchema):
    filter = Nested(TransactionFilterSchema, load_default=dict)
    projection = fields.List(
        fields.String,
        data_key='fields',
        metadata={
            'description': 'If "_id" or "nr" is in the filter, all fields will be '
            'returned by default. Otherwise, only the following fields are returned '
            'by default: {}. This behaviour can be overwritten by not leaving this '
            'parameter empty.'.format(
                ', '.join('`{}`'.format(field) for field in FIELDS)
            )
        },
    )

    @post_load
    def set_projection(self, data, **kwargs):
        if (
            all(field not in data.get('filter') for field in ['_id', 'nr'])
            and 'projection' not in data
        ):
            data['projection'] = FIELDS
        elif 'projection' not in data:
            data['projection'] = {'modified_history': 0}
        return data


def get(ctx, request):
    """
    Get transactions.

    ---
    post:
      description: >
        Get a list of transactions for the requested tenant. They can be
        filtered by the following parameters. Because this endpoint can return documents
        with different data models, it's not possible to show the data models. You can
        find them in the sales/get, transits/get and consignment/get endpoints.

        By default only a small number of fields is returned (unless filtering on "_id"
        or "nr"), this can be overwritten by using the projection parameter.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | array  | array of sale, transit and/or consignment transactions.

      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'retail_transactions.json#/definitions/TransactionGetSchema'

      tags:
        - data
    """
    context = {'db': request.db, 'tenant_id': request.requested_tenant_id}
    input_data = request.json_payload
    data = TransactionGetSchema(context=context).load(input_data)
    cursor = request.db[ctx].find(**data)
    return dict(status='ok', data=list(cursor))
