import re
import uuid
from copy import deepcopy

import bson
import pymongo
from marshmallow import ValidationError, fields, post_load, validate

from spynl_schemas import Nested, ObjectIdField, SalesOrderSchema, Schema, lookup

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction, SpynlException
from spynl.main.serial.file_responses import export_excel, serve_excel_response

from spynl.api.auth.exceptions import Forbidden
from spynl.api.auth.utils import (
    check_agent_access,
    get_user_info,
    get_user_region,
    is_sales_admin,
)
from spynl.api.logistics.utils import generate_list_of_skus
from spynl.api.mongo.query_schemas import FilterSchema, MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.exceptions import DuplicateTransaction
from spynl.api.retail.utils import flatten_result, limit_wholesale_queries


class SalesOrderFilterSchema(FilterSchema):
    _id = fields.UUID()
    docNumber = fields.UUID()
    agentId = ObjectIdField()
    customerId = fields.String()
    status = fields.String(
        validate=validate.OneOf(['complete', 'draft', 'complete-open-for-edit'])
    )
    text = fields.String(
        metadata={
            'description': "Regex search for this text on the customer's legalname, "
            'name, city (both normal and delivery) and the collection of the products'
        }
    )
    type = fields.Constant('sales-order')

    @post_load
    def postprocess(self, data, **kwargs):
        if 'customerId' in data:
            data['customer.id'] = data.pop('customerId')

        if 'text' in data:
            pattern = {
                '$regex': bson.regex.Regex(re.escape(data.pop('text'))),
                '$options': 'i',
            }
            data['$or'] = [
                {f: pattern}
                for f in [
                    'customer.legalName',
                    'customer.name',
                    'customer.address.city',
                    'customer.deliveryAddress.city',
                    'products.collection',
                ]
            ]
        return data

    @post_load
    def access_control(self, data, **kwargs):
        data = limit_wholesale_queries(data, self.context)
        if 'region' in data:
            data['customer.region'] = data.pop('region')
        return data


class SalesOrderGetSchema(MongoQueryParamsSchema):
    filter = Nested(SalesOrderFilterSchema, load_default=dict)


class SalesOrderRemoveFilterSchema(SalesOrderFilterSchema):
    _id = fields.UUID(required=True)
    status = fields.Constant(
        constant='draft',
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'string',
                'default': 'draft',
                'enum': ['draft'],
                'description': 'Only drafts can be deleted.',
            }
        },
    )

    class Meta(SalesOrderFilterSchema.Meta):
        fields = ('_id', 'type', 'status')


class SalesOrderRemoveSchema(Schema):
    # If you remove required=True, add a test to make sure the tenant_id
    # always ends up in the filter.
    filter = Nested(SalesOrderRemoveFilterSchema, required=True)


def remove(context, request):
    """
    Remove a sales order

    ---
    post:
      description: >
        Remove a sales order

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------
        %s

        ### # Filter

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        _id       | string | | The string form of the document ObjectId.\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        data         | array  | array of order term objects.


      tags:
        - data
    """
    input_data = request.json_payload

    schema = SalesOrderRemoveSchema(
        context={
            'tenant_id': request.requested_tenant_id,
            'user_id': request.authenticated_userid,
            'region': get_user_region(request.cached_user),
            'request': request,
        }
    )
    data = schema.load(input_data)

    request.db[context].update_one(data['filter'], {'$set': {'active': False}})
    return dict(data={})


def get(context, request):
    """
    Get sales orders

    ---
    post:
      description: >
        Get sales orders for the logged in tenant.
      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'sales_order_get_parameters.json#/definitions/SalesOrderGetSchema'
      responses:
        "200":
          schema:
            $ref: 'sales_order_get_response.json#/definitions/GetResponse'

      tags:
        - data
    """
    input_data = request.json_payload
    schema = SalesOrderGetSchema(
        context={
            'tenant_id': request.requested_tenant_id,
            'user_id': request.authenticated_userid,
            'region': get_user_region(request.cached_user),
            'request': request,
        }
    )
    data = schema.load(input_data)

    cursor = request.db[context].find(**data)
    return dict(data=list(cursor))


def save(context, request):
    """
    Save a sales order. Will insert if _id is not

    ---
    post:
      description: >
        Save an order term. Has upsert behavior. If _id is provided we assume
        it's an edit operation. In which case we don't allow editing
        'complete' orders.

        If _id is not provided we will insert the document.

      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            type: object
            properties:
              data:
                type: object
                $ref: 'sales_order_save.json#/definitions/SalesOrderSchema'
              auditRemark:
                type: String
                description: "Required remark when editing 'complete-open-for-edit'"
            required:
              - data
      responses:
        "200":
          schema:
            type: object
            properties:
              status:
                type: string
                description: "'ok' or 'error'"
              data:
                type: array
                description: "Array containing the _id's of the added items."
                items:
                  type: string
              type:
                type: object
                properties:
                  salesOrders:
                    type: array
                    description: "Array with the _id's of sales orders added."
                    items:
                      type: string
                  packingLists:
                    type: array
                    description: "Array with the _id's of packing lists added."
                    items:
                      type: string
      tags:
        - data
    """
    input_data = request.json_payload.get('data', {})

    tenant_id = request.requested_tenant_id
    tenant = request.db.tenants.find_one({'_id': tenant_id})
    packing_list_on_direct_delivery = lookup(
        tenant, 'settings.sales.directDeliveryPackingList', True
    )
    user_info = get_user_info(request, purpose='stamp')['user']
    schema_context = {
        'tenant_id': tenant_id,
        'agentId': request.authenticated_userid,
        'db': request.db,
        'user_id': user_info['_id'],  # is this ever something other than agentId?
        'username': user_info['username'],
        'packing_list_on_direct_delivery': packing_list_on_direct_delivery,
    }

    # Check if a complete-open-for-edit sales order is being edited:
    if input_data.get('_id'):
        order = request.db[context].find_one(
            {'_id': uuid.UUID(input_data['_id']), 'status': 'complete-open-for-edit'}
        )
        if order:
            schema_context['editing_open_order'] = True
            audit_remark = request.json_payload.get('auditRemark')
            if not audit_remark:
                raise ValidationError(
                    'auditRemark is required when editing completed sales orders.'
                )
            schema_context['audit_remark'] = audit_remark

    schema = SalesOrderSchema(context=schema_context)

    # orders may be split in to a sales_order and packing list so this returns
    # a list.
    orders = schema.load(input_data, many=False)
    check_agent_access(orders[0]['agentId'], request)

    # get the current counters
    counters = tenant.get('counters', {})
    for key in 'salesOrder', 'packingList':
        counters.setdefault(key, 0)

    for order in orders:
        if (
            order['type'] == 'sales-order'
            and order['status'] == 'complete'
            and not schema_context.get('editing_open_order')
        ):
            counters['salesOrder'] += 1
            schema.format_ordernr(order, counters['salesOrder'])
        elif order['type'] == 'packing-list':
            counters['packingList'] += 1
            schema.format_ordernr(order, counters['packingList'])

        try:
            immutable_fields = ['docNumber']
            if schema_context.get('editing_open_order'):
                immutable_fields.extend(['signature', 'signatureDate', 'signedBy'])
            request.db[context].upsert_one(
                {'_id': order['_id'], 'status': {'$ne': 'complete'}},
                order,
                immutable_fields=immutable_fields,
            )
        except pymongo.errors.DuplicateKeyError as e:
            match = re.compile(
                r'index: (.*[\.\$])?(?P<key>.*?)(_\d)? dup key', flags=re.IGNORECASE
            ).search(e.details['errmsg'])

            if not match:
                # can't figure out the key, just reraise
                raise
            elif match['key'] == '_id_':
                # If _id collides it means we tried to update a complete order.
                raise IllegalAction(_('order-completed'))
            else:
                # Otherwise we have a docnumber collision.
                raise DuplicateTransaction()

        # update the counters
        request.db.tenants.update_one(
            {'_id': tenant_id},
            {'$set': {'counters.' + k: v for k, v in counters.items()}},
        )

        # Only sync complete sales orders:
        if order['type'] == 'sales-order' and order['status'] == 'complete':
            sync = True
            # But not if a corresponding packing list was generated:
            if order.get('directDelivery') and packing_list_on_direct_delivery:
                sync = False
        elif order['type'] == 'packing-list':
            sync = True
        else:
            sync = False

        if sync:
            insert_foxpro_events(request, order, SalesOrderSchema.generate_fpqueries)

    return {
        'data': [str(o['_id']) for o in orders],
        'type': {
            'salesOrders': [
                str(o['_id']) for o in orders if o['type'] == 'sales-order'
            ],
            'packingLists': [
                str(o['_id']) for o in orders if o['type'] == 'packing-list'
            ],
        },
    }


class SalesOrderOpenSchema(Schema):
    _id = fields.UUID(required=True)


def open_for_edit(context, request):
    """
    Open completed sales order for editing.
    ---
    post:
      description: >
        Open a complete sales order for editing.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'sales_order_open.json#/definitions/SalesOrderOpenSchema'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    if not is_sales_admin(request):
        raise Forbidden(
            _(
                'permission-denial',
                mapping={'permission': 'edit', 'context': 'sales-order'},
            )
        )
    parameters = SalesOrderOpenSchema().load(request.json_payload)
    order = request.db[context].find_one(
        {
            '_id': parameters['_id'],
            'status': 'complete',
            'type': 'sales-order',
            'active': True,
        }
    )
    if not order:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist or cannot be opened.',
        )
    order_copy = deepcopy(order)
    order_copy.pop('_id')
    result = request.db.sales_order_audit_trail.insert_one(order_copy)

    SalesOrderSchema.open_for_edit(order, request.cached_user, result.inserted_id)
    request.db[context].upsert_one({'_id': order['_id']}, order)

    return {'data': [order['_id']]}


class SalesOrderDownloadFilterSchema(Schema):
    _id = fields.UUID(required=True)


class SalesOrderDownloadSchema(Schema):
    filter = Nested(SalesOrderDownloadFilterSchema, required=True)

    @post_load
    def add_metadata(self, data, **kwargs):
        data['metadata'] = {
            'orderNumber': {'label': _('order-number').translate()},
            'customReference': {'label': _('custom-reference').translate()},
            'type': {'label': _('order-type').translate()},
            'customerName': {'label': _('name').translate()},
            'customerAddressAddress': {'label': _('address').translate()},
            'customerAddressZipcode': {'label': _('zipcode').translate()},
            'customerAddressCity': {'label': _('city').translate()},
            'customerAddressCountry': {'label': _('country').translate()},
            'articleCode': {'label': _('article-code').translate()},
            'articleDescription': {'label': _('article-description').translate()},
            'localizedPrice': {'label': _('price').translate(), 'type': 'money'},
            'localizedSuggestedRetailPrice': {
                'label': _('suggested-retail-price').translate(),
                'type': 'money',
            },
            'barcode': {'label': _('barcode').translate()},
            'qty': {'label': _('quantity').translate(), 'type': 'quantity'},
            'size': {'label': _('sizeLabel').translate()},
            'colorCode': {'label': _('color-code').translate()},
            'colorDescription': {'label': _('color-description').translate()},
        }
        return data


def download_excel(context, request):
    """
    Download an excel document of a sales order in which each sku has its own line

    ---
    post:
      description: >
        Download an excel document of a sales order in which each sku has its own line.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'sales_order_excel.json#/definitions/SalesOrderDownloadSchema'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The sales order as an excel file.
          schema:
            type: file
      tags:
        - data
    """
    parameters = SalesOrderDownloadSchema().load(request.json_payload)
    fields = {
        field: 1
        for field in [
            'orderNumber',
            'type',
            'customReference',
            'customer.name',
            'customer.address.address',
            'customer.address.zipcode',
            'customer.address.city',
            'customer.address.country',
            'products.articleCode',
            'products.articleDescription',
            'products.localizedPrice',
            'products.localizedSuggestedRetailPrice',
            'products.skus.barcode',
            'products.skus.qty',
            'products.skus.size',
            'products.skus.colorCode',
            'products.skus.colorDescription',
        ]
    }

    order = request.db[context].find_one(
        {
            '_id': parameters['filter']['_id'],
            'type': 'sales-order',
            'active': True,
            'tenant_id': request.requested_tenant_id,
        },
        {'_id': 0, **fields},
    )
    if not order:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )
    result = generate_list_of_skus(order)
    result = flatten_result(result)
    header = list(parameters['metadata'].keys())
    temp_file = export_excel(header, result, parameters['metadata'])

    return serve_excel_response(request.response, temp_file, 'order.xlsx')
