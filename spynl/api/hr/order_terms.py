from marshmallow import EXCLUDE, Schema, fields

from spynl_schemas import Nested, OrderTermsSchema

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction
from spynl.main.utils import required_args

from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema


class OrderTermsFilter(FilterSchema):
    _id = fields.UUID()
    country = fields.String()


class OrderTermsGetSchema(MongoQueryParamsSchema):
    filter = Nested(OrderTermsFilter, load_default=dict)


class OrderTermsRemoveFilter(OrderTermsFilter):
    _id = fields.UUID(required=True)

    class Meta(OrderTermsFilter.Meta):
        fields = ('_id',)


class OrderTermsRemoveSchema(Schema):
    # If you remove required=True, add a test to make sure the tenant_id
    # always ends up in the filter.
    filter = Nested(OrderTermsRemoveFilter, required=True)

    class Meta:
        unknown = EXCLUDE


def get(ctx, request):
    """
    Get order terms, which are the terms of conditions for orders.

    ---
    post:
      description: >
        Get order terms for the logged in tenant.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'order_terms_get_parameters.json#/definitions/OrderTermsGetSchema'
      responses:
        "200":
          schema:
            $ref: 'order_terms_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    input_data = request.json_payload

    schema = OrderTermsGetSchema(context={'tenant_id': request.requested_tenant_id})
    data = schema.load(input_data)

    terms = request.db[ctx].find(**data)
    return {'data': list(terms)}


@required_args('data')
def save(ctx, request):
    """
    Save an order term, which are the terms of conditions for orders.

    ---
    post:
      description: >
        Save an order term, by saving a new one or updating an existing one
        depending if one exists with the provided _id.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'order_terms_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    input_data = request.json_payload.get('data', {})
    schema = OrderTermsSchema(
        context={'tenant_id': request.requested_tenant_id, 'db': request.db}
    )

    data = schema.load(input_data)

    query = {
        'tenant_id': request.requested_tenant_id,
        'country': data['country'],
        'language': data['language'],
        '_id': {'$ne': data['_id']},
    }
    if request.db[ctx].count(query):
        raise IllegalAction(
            _(
                'duplicate-order-terms',
                mapping={'country': data['country'], 'language': data['language']},
            )
        )

    request.db[ctx].upsert_one({'_id': data['_id']}, data)

    return {'data': [str(data['_id'])]}


def remove(ctx, request):
    """
    Remove an order term, which are the terms of conditions for orders.

    ---
    post:
      description: >
        Remove an order term.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n

      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'order_terms_del_parameters.json#/definitions/OrderTermsRemoveSchema'
      tags:
        - data
    """
    input_data = request.json_payload

    data = OrderTermsRemoveSchema(
        context={'tenant_id': request.requested_tenant_id}
    ).load(input_data)

    result = request.db[ctx].delete_one(**data)
    if not result.deleted_count:
        raise IllegalAction(_('document-not-found'))

    return {}
