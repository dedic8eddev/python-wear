"""Endpoints for Sale Transaction."""
import re
import uuid

import bson
from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    post_load,
    validate,
    validates,
)

from spynl_schemas import ConsignmentSchema, Nested, SaleSchema

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction
from spynl.main.utils import required_args

from spynl.api.auth.utils import get_user_info
from spynl.api.mongo.query_schemas import MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.exceptions import DuplicateTransaction
from spynl.api.retail.utils import TransactionFilterSchema


class SaleFilterSchema(TransactionFilterSchema):
    type = fields.Constant(2)


class SaleGetSchema(MongoQueryParamsSchema):
    filter = Nested(SaleFilterSchema, load_default=dict)


class SaleCancelSchema(Schema):
    filter = Nested(SaleFilterSchema, load_default=dict, only=('_id', 'nr'))

    @validates('filter')
    def validate_id_docnr(self, value):
        if '_id' not in value and 'nr' not in value:
            raise ValidationError('Missing value, provide one of "_id" or "nr"')

    class Meta:
        unknown = EXCLUDE
        ordered = True


class WithdrawalFilterSchema(SaleFilterSchema):
    withdrawelreason = fields.String(data_key='withdrawalReason')

    @post_load
    def set_withdrawal_filter(self, data, **kwargs):
        """
        payments.withdrawel should exist, and not be 0 (negative withdrawal is
        a deposit).
        """
        data['payments.withdrawel'] = {'$ne': 0, '$exists': True}
        return data

    @post_load
    def search_name_by_regex(self, data, **kwargs):
        if 'withdrawelreason' in data:
            data['withdrawelreason'] = {
                '$regex': bson.regex.Regex(re.escape(data['withdrawelreason'])),
                '$options': 'i',
            }
        return data


class WithdrawalGetSchema(MongoQueryParamsSchema):
    filter = Nested(WithdrawalFilterSchema, load_default=dict)


class ConsignmentFilterSchema(SaleFilterSchema):
    type = fields.Constant(9)
    status = fields.String(validate=validate.OneOf(['open', 'closed']))


class ConsignmentGetSchema(MongoQueryParamsSchema):
    filter = Nested(ConsignmentFilterSchema, load_default=dict)


def _deactivate_buffer(db, data):
    buffer_id = data.get('buffer_id')
    if buffer_id:
        db.buffer.update_one({'_id': buffer_id}, {'$set': {'active': False}})


def _update_loyalty_points(db, data):
    # in case customer is present but None
    customer = data.get('customer') or {}
    customer_id = customer.get('id')
    if customer_id:
        try:
            customer_id = uuid.UUID(customer_id, version=4)
        except ValueError:
            pass

        points = data.get('loyaltyPoints')
        if customer_id and points:
            db.customers.update_one({'_id': customer_id}, {'$set': {'points': points}})


def _add(ctx, request, transaction_schema=SaleSchema, webshop=False):
    """
    Common function for adding a sale, withdrawal or consignment transaction.
    """
    tenant_id = request.requested_tenant_id
    vat = request.db.tenants.find_one({'_id': tenant_id})['settings'].get('vat')
    user_info = get_user_info(request, purpose='stamp')['user']
    context = {
        'vat_settings': vat,
        'tenant_id': tenant_id,
        'db': request.db,
        'user_info': user_info,
        'webshop': webshop,
    }
    schema = transaction_schema(context=context)

    data = schema.load(request.args['data'])
    # validate uniqueness
    if request.db[ctx].count(
        {'tenant_id': tenant_id, 'nr': data['nr'], 'type': data['type']}
    ):
        raise DuplicateTransaction()

    # save the transaction and the events.
    saved_transaction = request.db[ctx].insert_one(data)
    _deactivate_buffer(request.db, data)
    _update_loyalty_points(request.db, data)

    insert_foxpro_events(request, data, transaction_schema.generate_fpqueries)

    return dict(status='ok', data=[str(saved_transaction.inserted_id)])


def sale_cancel(ctx, request):
    """
    Cancel a sale.

    ---
    post:
      description: >
        Cancel a sale. multiplies all the quantities and payments by -1 and
        recalculates the totals and taxes. Requires either 'nr' or '_id'.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'sale_cancel_parameters.json#/definitions/SaleCancel'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    tenant_id = request.requested_tenant_id
    context = {'db': request.db, 'tenant_id': tenant_id}
    data = SaleCancelSchema(context=context).load(request.json_payload)
    sale = request.db[ctx].find_one(**data)
    if not sale:
        raise IllegalAction(_('document-not-found'))

    user_info = get_user_info(request, purpose='stamp')['user']

    context = {
        'tenant_id': tenant_id,
        'db': request.db,
        'user_info': user_info,
        'cancel': True,
    }
    schema = SaleSchema(context=context)
    canceled = schema.load(sale)
    # save the transaction and the events.
    saved_transaction = request.db[ctx].insert_one(canceled)

    insert_foxpro_events(request, canceled, SaleSchema.generate_fpqueries, cancel=True)
    return dict(
        status='ok',
        data=[str(saved_transaction.inserted_id)],
        message='The order was cancelled',
    )


def _save(ctx, request, transaction_schema=SaleSchema):
    """
    Common function for upserting a sale, withdrawal or consignment transaction.
    """
    tenant_id = request.requested_tenant_id
    vat = request.db.tenants.find_one({'_id': 'tenant_id'})['settings'].get('vat')
    user_info = get_user_info(request, purpose='stamp')['user']
    context = {
        'vat_settings': vat,
        'tenant_id': tenant_id,
        'db': request.db,
        'user_info': user_info,
    }
    schema = transaction_schema(context=context)
    data = schema.load(request.args['data'])

    result = request.db[ctx].upsert_one(
        {'_id': data['_id']}, data, immutable_fields=['nr']
    )

    if result.upserted_id:
        _deactivate_buffer(request.db, data)
        _update_loyalty_points(request.db, data)

        insert_foxpro_events(request, data, transaction_schema.generate_fpqueries)

    return dict(status='ok', data=[str(result.upserted_id or data['_id'])])


def _get(ctx, request):
    """
    Common function for getting sale, withdrawal or consignment transactions.
    """
    context = {'db': request.db, 'tenant_id': request.requested_tenant_id}
    input_data = request.json_payload
    data = SaleGetSchema(context=context).load(input_data)
    cursor = request.db[ctx].find(**data)
    return dict(status='ok', data=list(cursor))


@required_args('data')
def withdrawal_save(ctx, request):
    """
    Modify a withdrawal transaction.

    ---
    post:
      description: >
        Modify a withdrawal transaction make all the appropriate calculations and
        validations needed.
      tags:
        - data
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'sale_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
    """
    return _save(ctx, request)


@required_args('data')
def consignment_save(ctx, request):
    """
    Modify a consignment transaction.

    ---
    post:
      description: >
        Modify a consignment transaction make all the appropriate
        calculations and validations needed.

        If the consignment links to another transaction the only value required is
        link.id (the string representation of the _id of the linked transaction.
        If the linked transaction is a consignment closing the consignment will
        be handled by the backend.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'consignment_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    return _save(ctx, request, transaction_schema=ConsignmentSchema)


@required_args('data')
def sale_save(ctx, request):
    """
    Modify a sales transaction.

    ---
    post:
      description: >
        Modify a sale transaction make all the appropriate calculations and
        validations needed.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'sale_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    return _save(ctx, request)


@required_args('data')
def sale_add(ctx, request):
    """
    Add a new sales transaction.

    ---
    post:
      description: >
        Create a new sale transaction make all the appropriate calculations and
        validations needed. This also informs foxpro by creating appropriate
        events for the transaction, adding/redeeming coupons and paying
        customer's store credit.

        If the sale links to another transaction the only extra value required is
        link.id (the string representation of the _id of the linked transaction.
        If the linked transaction is a consignment closing the consignment will
        be handled by the backend.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'sale_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    return _add(ctx, request)


@required_args('data')
def webshop_sale_add(ctx, request):
    """
    Add a new sales transaction.

    ---
    post:
      description: >
        Create a new sale transaction make all the appropriate calculations and
        validations needed. This also informs foxpro by creating appropriate
        events for the transaction, adding/redeeming coupons and paying
        customer's store credit.

        If the sale links to another transaction the only extra value required is
        link.id (the string representation of the _id of the linked transaction.
        If the linked transaction is a consignment closing the consignment will
        be handled by the backend.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'sale_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    return _add(ctx, request, webshop=True)


def sale_get(ctx, request):
    """
    Get sales transactions.

    ---
    post:
      description: >
        Get a list of sales transactions for the requested tenant. They can be
        filtered by the following parameters.
        Parameters are taken into account only when in request's body.

      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'sale_get_parameters.json#/definitions/SaleGet'
      responses:
        "200":
          schema:
            $ref: 'sale_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    return _get(ctx, request)


@required_args('data')
def withdrawal_add(ctx, request):
    """
    Add a new withdrawal transaction.

    ---
    post:
      description: >
        Create a new withdrawal transaction make all the appropriate calculations and
        validations needed. This also informs foxpro by creating appropriate
        events for the transaction, adding/redeeming coupons.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'sale_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    return _add(ctx, request)


def withdrawal_get(ctx, request):
    """
    Get withdrawal transactions.

    ---
    post:
      description: >
        Get a list of withdrawal transactions for the requested tenant. They can be
        filtered by the following parameters.
        Parameters are taken into account only when in request's body.
      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'withdrawal_get_parameters.json#/definitions/WithdrawalGet'
      responses:
        "200":
          schema:
            $ref: 'sale_get_response.json#/definitions/GetResponse'
    """
    context = {'db': request.db, 'tenant_id': request.requested_tenant_id}
    input_data = request.json_payload
    data = WithdrawalGetSchema(context=context).load(input_data)
    cursor = request.db[ctx].find(**data)
    return dict(status='ok', data=list(cursor))


@required_args('data')
def consignment_add(ctx, request):
    """
    Add a new consignment transaction.

    ---
    post:
      description: >
        Create a new consignment transaction make all the appropriate
        calculations and validations needed. This also informs foxpro by
        creating appropriate events for the transaction.

        If the consignment links to another transaction the only value required is
        link.id (the string representation of the _id of the linked transaction.
        If the linked transaction is a consignment closing the consignment will
        be handled by the backend.
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'consignment_save.json#/definitions/SaveParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    return _add(ctx, request, transaction_schema=ConsignmentSchema)


def consignment_get(ctx, request):
    """
    Get consignment transactions.

    ---
    post:
      description: >
        Get a list of consignment transactions for the requested tenant. They can be
        filtered by the following parameters.
        Parameters are taken into account only when in request's body.
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'consignment_get_parameters.json#/definitions/ConsignmentGet'
      responses:
        "200":
          schema:
            $ref: 'consignment_get_response.json#/definitions/GetResponse'
      tags:
        - data
    """
    context = {'db': request.db, 'tenant_id': request.requested_tenant_id}
    input_data = request.json_payload
    data = ConsignmentGetSchema(context=context).load(input_data)
    cursor = request.db[ctx].find(**data)
    return dict(status='ok', data=list(cursor))


def add_fiscal_receipt(ctx, request):
    """
    Set the fiscal receipt number of a sale.
    ---
    post:

      description: >
        Set the fiscal receipt number of a sale.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
         status       | string | 'ok' or 'error'\n
         data         | dict   | the updated sale\n
    """
    # get context tenant_id and sale_id
    input_data = request.json_payload

    # set filter by id or nr
    if "_id" in input_data:
        filter = {"_id": bson.ObjectId(input_data["_id"])}
    elif "nr" in input_data:
        filter = {"nr": input_data["nr"]}
    else:
        return dict(status='Error', message='Request body should contain _id or nr')

    cursor = request.db[ctx].find_one(filter)
    if cursor:
        # get the document _id and cast it to prevent any validation errors
        sale_id = bson.ObjectId(str(cursor["_id"]))
        # build the changes
        changes = {}

        if "fiscal_receipt_nr" in input_data:
            changes['fiscal_receipt_nr'] = input_data['fiscal_receipt_nr']
        if "fiscal_shift_nr" in input_data:
            changes['fiscal_shift_nr'] = input_data['fiscal_shift_nr']
        if "fiscal_date" in input_data:
            changes['fiscal_date'] = input_data['fiscal_date']
        if "fiscal_printer_id" in input_data:
            changes['fiscal_printer_id'] = input_data['fiscal_printer_id']
        # update the document if there are changes
        if changes:
            request.db[ctx].update_one(
                {'_id': sale_id}, {'$set': changes}, upsert=False
            )
        # return the data updated
        cursor = request.db[ctx].find_one({'_id': sale_id})
        return dict(status='ok', data=cursor)
    else:
        return dict(status='Error', message='Could not find sale')
