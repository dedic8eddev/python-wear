import datetime
import io
import os
import re
import uuid

import boto3
import pymongo
import requests
from marshmallow import EXCLUDE, fields, post_load, validate

from spynl_schemas import Nested, PackingListSchema, Schema, lookup
from spynl_schemas.packing_list import PACKING_LIST_STATUSES, ParcelSchema
from spynl_schemas.utils import BAD_CHOICE_MSG, split_address

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import IllegalAction, SpynlException
from spynl.main.serial.file_responses import (
    export_csv,
    export_excel,
    make_pdf_file_response,
    serve_csv_response,
    serve_excel_response,
)
from spynl.main.utils import get_settings

from spynl.api.auth.utils import MASTER_TENANT_ID, get_tenant_roles, get_user_info
from spynl.api.logistics.sales_orders import SalesOrderFilterSchema
from spynl.api.logistics.utils import (
    PACKING_LIST_DOWNLOAD_FIELDS,
    generate_list_of_skus,
)
from spynl.api.mongo.query_schemas import MongoQueryParamsSchema
from spynl.api.mongo.utils import insert_foxpro_events
from spynl.api.retail.exceptions import DuplicateTransaction
from spynl.api.retail.utils import flatten_result

from spynl.services.pdf.pdf import generate_packing_list_pdf, get_image_location


def packing_lists_get_access_control(filter_, request):
    if '_id' in filter_ or request.current_tenant_id == MASTER_TENANT_ID:
        return filter_

    roles = get_tenant_roles(
        request.db, request.cached_user, request.requested_tenant_id
    )
    if 'picking-admin' not in roles:
        allowed_statuses = ['open', 'complete', 'ready-for-shipping']
        if 'picking-user' in roles:
            allowed_statuses = [
                'open',
                'complete',
                'incomplete',
                'ready-for-shipping',
                'shipping',
            ]

        if 'status' in filter_:
            if '$in' in filter_['status']:
                for status in filter_['status']['$in']:
                    if status not in allowed_statuses:
                        filter_['status']['$in'].remove(status)

        else:
            # picking-users are not allowed to see 'picking', because they are not
            # allowed to start picking a packing list and come back to it later. They
            # are allowed to see the following statuses if they were the picker:
            allowed_statuses_picker = [
                'incomplete',
                'complete',
                'ready-for-shipping',
                'shipping',
            ]
            status_filter = {
                '$or': [
                    {'status': {'$in': allowed_statuses}},
                    {
                        'status': {'$in': allowed_statuses_picker},
                        'orderPicker': request.authenticated_userid,
                    },
                ]
            }
            if '$or' in filter_:
                # can only have one top level "or" condition. So we make a new $and
                # condition that combines the two $or statements.
                filter_.setdefault('$and', [])
                filter_['$and'].extend([{'$or': filter_.pop('$or')}, status_filter])
            else:
                filter_.update(status_filter)
    return filter_


class PackingListFilterSchema(SalesOrderFilterSchema):
    reservationDateMin = fields.DateTime()
    reservationDateMax = fields.DateTime()

    type = fields.Constant('packing-list')
    warehouseName = fields.List(fields.String())
    warehouseId = fields.List(fields.String())
    customerName = fields.List(fields.String())
    barcode = fields.List(fields.String())
    articleCode = fields.List(fields.String())
    status = fields.List(
        fields.String(
            validate=validate.OneOf(
                [
                    'pending',
                    'open',
                    'picking',
                    'incomplete',
                    'complete',
                    'ready-for-shipping',
                    'shipping',
                    'cancelled',
                ]
            )
        )
    )

    @post_load
    def postprocess(self, data, **kwargs):
        # this order is important
        self.set_filter(data)
        self.access_control(data)
        return data

    def set_filter(self, data):
        for key, filter_key in [
            ('warehouseId', 'warehouseId'),
            ('customerName', 'customer.name'),
            ('barcode', 'products.skus.barcode'),
            ('articleCode', 'products.articleCode'),
        ]:
            if key in data:
                data[filter_key] = data.pop(key)

        for key, value in data.items():
            if isinstance(value, list):
                data[key] = {'$in': value}

        range_ = {}
        for key, op in [('reservationDateMin', '$gte'), ('reservationDateMax', '$lte')]:
            if key in data:
                value = data.pop(key)
                range_[op] = value
                range_[op] = value

        if range_:
            data.setdefault('$or', [])
            data['$or'].extend(
                [
                    {'reservationDate': range_},
                    {
                        # if reservationDate is not a date field (type 9 in
                        # mongo) apply the range to created.date
                        'created.date': range_,
                        'reservationDate': {'$not': {'$type': 9}},
                    },
                ]
            )
        return data

    def access_control(self, data):
        return packing_lists_get_access_control(data, self.context['request'])

    class Meta:
        exclude = ('agentId',)
        unknown = EXCLUDE
        ordered = True


class PackingListGetSchema(MongoQueryParamsSchema):
    filter = Nested(PackingListFilterSchema, load_default=dict)


class PackingListDownloadSchema(Schema):
    _id = fields.UUID(required=True)

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


def get(context, request):
    """
    Get packing lists

    ---
    post:
      description: >
        Get packing lists for the logged in tenant.\n
        ![Picking flow chart](picking_document_status_flow.png "Picking flow chart")
      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'packing_list_get_parameters.json#/definitions/PackingListGetSchema'
      responses:
        '200':
          schema:
            type: object
            properties:
              status:
                type: string
                description: "'ok'"
              data:
                type: array
                description: "Array containing the item packing list."
                items:
                 type: object
                 "$ref": "packing_list_get_response.json#/definitions/PackingListSchema"

      tags:
        - data
    """
    input_data = request.json_payload
    schema = PackingListGetSchema(
        context={
            'tenant_id': request.requested_tenant_id,
            'user_id': request.authenticated_userid,
            'request': request,
        }
    )

    if 'filter' in input_data:
        if 'warehouseName' in input_data['filter']:
            warehouses = request.db.warehouses.find(
                {'name': {'$in': input_data['filter']['warehouseName']}}
            )
            warehousesIds = [str(warehouse['_id']) for warehouse in warehouses]
            input_data['filter']['warehouseId'] = warehousesIds
            input_data['filter'].pop('warehouseName')

    data = schema.load(input_data)
    cursor = request.db[context].find(**data)
    return dict(data=list(cursor))


def save(context, request):
    """
    Update a packing list.

    ---
    post:
      description: >
        Update a packing list.\n
        ![Picking flow chart](picking_document_status_flow.png 'Picking flow chart')
      parameters:
        - name: body
          in: body
          description: Data to be added
          required: true
          schema:
            $ref: 'packing_list_save.json#/definitions/SaveParameters'
      responses:
        '200':
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """

    input_data = request.json_payload.get('data', {})
    tenant_id = request.requested_tenant_id
    user_info = get_user_info(request, purpose='stamp')['user']
    roles = get_tenant_roles(
        request.db, request.cached_user, request.requested_tenant_id
    )

    schema = PackingListSchema(
        context={
            'tenant_id': tenant_id,
            'user_roles': roles,
            'db': request.db,
            'user_id': user_info['_id'],
            'user_fullname': request.cached_user['fullname'],
        }
    )
    # an incomplete packing list may be split up in a complete and pending one.
    packing_lists = schema.load(input_data)
    insert_packing_list(request, packing_lists, tenant_id, schema, context)

    return {'data': [str(o['_id']) for o in packing_lists]}


def insert_packing_list(request, packing_lists, tenant_id, schema, context):
    # get the current counters
    counters = request.db.tenants.find_one(
        {'_id': tenant_id}, {'counters.packingList': 1, '_id': 0}
    ).get('counters', {'packingList': 0})

    for i, packing_list in enumerate(packing_lists):
        # only update counter for new packing lists that were generated from the
        # original.
        if i > 0:
            counters['packingList'] += 1
            schema.format_ordernr(packing_list, counters['packingList'])

        try:
            request.db[context].upsert_one(
                {'_id': packing_list['_id']},
                packing_list,
                immutable_fields=['docNumber'],
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

        # send in foxpro event for split off packing list:
        if i > 0:
            insert_foxpro_events(request, packing_list, schema.generate_fpqueries)


def filters(ctx, request):
    """
    Return possible filter values.

    ---
    post:
      tags:
        - data
      description: >
        In order to know with what data to populate the front-end UI for
        filtering packing lists, return possible filter values.
      produces:
        - application/json
      responses:
        200:
          description: Possible filter values for packing lists
          schema:
            type: object
            properties:
              filter:
                type: object
                description: >
                  each key is a filter, the value is an array of possible values for
                  that filter. Possible keys: status, warehouseId,
                  customerName, barcode, articleCode
    """
    pipeline = [
        {
            '$match': {
                'type': 'packing-list',
                'active': True,
                'tenant_id': {'$in': [request.requested_tenant_id]},
            }
        },
        {
            '$lookup': {
                'from': 'warehouses',
                'let': {'warehouseId': "$warehouseId"},
                'pipeline': [
                    {
                        '$match': {
                            '$expr': {
                                '$eq': [
                                    {'$toString': "$_id"},
                                    {'$toString': "$$warehouseId"},
                                ]
                            }
                        }
                    }
                ],
                'as': 'warehouse',
            }
        },
        {"$set": {"warehouse": {"$arrayElemAt": ["$warehouse", 0]}}},
        {
            '$project': {
                'status': 1,
                'warehouse': 1,
                'customer.name': 1,
                'products': 1,
            }
        },
        {'$unwind': '$products'},
        {'$unwind': '$products.skus'},
        {
            '$group': {
                '_id': 0,
                'status': {'$addToSet': '$status'},
                'warehouseName': {'$addToSet': '$warehouse.name'},
                'customerName': {'$addToSet': '$customer.name'},
                'barcode': {'$addToSet': '$products.skus.barcode'},
                'articleCode': {'$addToSet': '$products.articleCode'},
            }
        },
        {'$project': {'_id': 0}},
    ]
    filter = {}
    packing_lists_get_access_control(pipeline[0]['$match'], request)

    try:
        filter = next(request.db[ctx].aggregate(pipeline))
        for k, v in filter.items():
            filter[k] = sorted(v)
    except StopIteration:
        pass

    return dict(status='ok', data={'filter': filter})


def set_status(context, request):
    """
    Update a packing list status.

    ---
    post:
      description: >
        Update a packing list status.\n
        ![Picking flow chart](picking_document_status_flow.png 'Picking flow chart')
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'packing_list_set_status.json#/definitions/SetStatus'
      responses:
        '200':
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
      tags:
        - data
    """
    parameters = SetStatus().load(request.json_payload)

    _id = parameters['_id']
    status = parameters['status']

    try:
        packing_list_id = _id
    except Exception:
        raise SpynlException(_('no-packing-list-shipping'))
    tenant_id = request.requested_tenant_id
    user_info = get_user_info(request, purpose='stamp')['user']
    roles = get_tenant_roles(
        request.db, request.cached_user, request.requested_tenant_id
    )

    schema = PackingListSchema(
        context={
            'tenant_id': tenant_id,
            'user_roles': roles,
            'db': request.db,
            'user_id': user_info['_id'],
            'user_fullname': request.cached_user['fullname'],
        }
    )

    packing_list = request.db[context].find_one({'_id': packing_list_id})
    if not packing_list:
        raise SpynlException(_('no-packing-list-shipping'))

    if packing_list['status'] == 'picking' == status:
        raise SpynlException(_('Illegal status update'))

    packing_list['status'] = status
    packing_lists = schema.load(packing_list)
    insert_packing_list(request, packing_lists, tenant_id, schema, context)

    new_packing_list_values = request.db[context].find_one({'_id': packing_list['_id']})
    return {'data': new_packing_list_values}


class ShippingFilter(Schema):
    _id = fields.UUID(
        required=True,
        metadata={'description': '_id of the packing list that is being shipped'},
    )


class SetStatus(Schema):
    _id = fields.UUID(
        required=True,
        metadata={'description': '_id of the packing list that is being updated'},
    )
    status = fields.String(
        load_default='open',
        validate=validate.OneOf(choices=PACKING_LIST_STATUSES, error=BAD_CHOICE_MSG),
    )


class ShippingParameters(Schema):
    filter = Nested(ShippingFilter, required=True)
    skipSendcloud = fields.Boolean(
        load_default=False,
        metadata={
            'description': 'Skip registering a package with sendcloud. No labels will '
            'be printed.'
        },
    )
    printDocuments = fields.Boolean(
        load_default=False,
        metadata={
            'description': 'Automatically send the shipping labels and packing list '
            'to the print queue.'
        },
    )


def ship(context, request):
    """
    Ship a packing list.

    ---
    post:
      description: >
        Ship a packing lists. Changes the status of the packing list and creates a
        foxpro event. If the token en secret for sendcloud are configured in the
        tenant settings, it will also register parcel(s) with sendcloud.
      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'packing_list_shipping.json#/definitions/ShippingParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
    """
    parameters = ShippingParameters().load(request.json_payload)
    packing_list = request.db[context].find_one(
        {
            '_id': parameters['filter']['_id'],
            'status': 'ready-for-shipping',
            'type': 'packing-list',
            'active': True,
        }
    )
    if not packing_list:
        raise SpynlException(_('no-packing-list-shipping'))

    settings = request.db.tenants.find_one(
        {'_id': request.requested_tenant_id}, {'settings': 1}
    ).get('settings', {})
    user_settings = request.db.users.find_one(
        {'_id': request.cached_user['_id']}, {'settings': 1}
    ).get('settings', {})
    try:
        token = settings['sendcloudApiToken']
        secret = settings['sendcloudApiSecret']
    except KeyError:
        parameters['skipSendcloud'] = True

    if not parameters['skipSendcloud']:
        parcels = register_sendcloud_parcels(request.db, packing_list, token, secret)
        packing_list['parcels'] = ParcelSchema(many=True).load(parcels)

    packing_list['status'] = 'shipping'
    request.db[context].upsert_one({'_id': packing_list['_id']}, packing_list)

    insert_foxpro_events(
        request, packing_list, PackingListSchema.generate_shipping_fp_event
    )

    if parameters['printDocuments']:
        # print packing list pdf
        if lookup(user_settings, 'picking.pickingListPrinterId'):
            result = generate_packing_list_pdf(
                request,
                packing_list,
                get_image_location(settings, sales=True),
            )
            payload = upload_pdf(result)
            send_document_to_printq(
                request, lookup(user_settings, 'picking.pickingListPrinterId'), payload
            )
        elif lookup(settings, 'picking.packingListPrintq'):
            result = generate_packing_list_pdf(
                request,
                packing_list,
                get_image_location(settings, sales=True),
            )
            payload = upload_pdf(result)
            send_document_to_printq(
                request, lookup(settings, 'picking.packingListPrintq'), payload
            )
        elif lookup(user_settings, 'picking.pickingListPrinterId'):
            result = generate_packing_list_pdf(
                request,
                packing_list,
                get_image_location(settings, sales=True),
            )
            payload = upload_pdf(result)
            send_document_to_printq(
                request, lookup(user_settings, 'picking.pickingListPrinterId'), payload
            )
        # print package label(s)
        if (
            lookup(user_settings, 'picking.shippingLabelPrinterId')
            and not parameters['skipSendcloud']
        ):
            label_response = get_sendcloud_labels(
                request, [p['id'] for p in packing_list['parcels']]
            )
            pdf = io.BytesIO()
            pdf.write(label_response.content)
            pdf.seek(0)
            payload = upload_pdf(pdf)
            send_document_to_printq(
                request,
                lookup(user_settings, 'picking.shippingLabelPrinterId'),
                payload,
            )
        elif (
            lookup(settings, 'picking.packageLabelPrintq')
            and not parameters['skipSendcloud']
        ):
            if packing_list.get('parcels', []):
                label_response = get_sendcloud_labels(
                    request, [p['id'] for p in packing_list['parcels']]
                )
                pdf = io.BytesIO()
                pdf.write(label_response.content)
                pdf.seek(0)
                payload = upload_pdf(pdf)
                send_document_to_printq(
                    request, lookup(settings, 'picking.packageLabelPrintq'), payload
                )
        elif (
            lookup(user_settings, 'picking.shippingLabelPrinterId')
            and not parameters['skipSendcloud']
        ):
            label_response = get_sendcloud_labels(
                request, [p['id'] for p in packing_list['parcels']]
            )
            pdf = io.BytesIO()
            pdf.write(label_response.content)
            pdf.seek(0)
            payload = upload_pdf(pdf)
            send_document_to_printq(
                request,
                lookup(user_settings, 'picking.shippingLabelPrinterId'),
                payload,
            )

    return {'data': [str(packing_list['_id'])]}


def register_sendcloud_parcels(db, packing_list, token, secret):
    """
    Register all parcels from a packing list with SendCloud
    To be able to use this endpoint correctly, the client needs to have configured a
    default weight and shipping rules in their SendCloud account.
    """
    address = split_address(packing_list['customer']['deliveryAddress']['address'])
    data = {
        'name': packing_list['customer']['name'],
        'address': address['street'],
        'house_number': address['houseno'] + address.get('houseadd', ''),
        'city': packing_list['customer']['deliveryAddress']['city'],
        'postal_code': packing_list['customer']['deliveryAddress']['zipcode'],
        'country': packing_list['customer']['deliveryAddress']['country'],
        'order_number': packing_list['orderNumber'],
        'request_label': True,
        # 8 is Unstamped letter. apply_shipping_rules will overwrite this if the
        # shipping rules are configured correctly.
        'shipment': {'id': 8},
        'apply_shipping_rules': True,
        'quantity': packing_list['numberOfParcels'],
    }

    if 'telephone' in packing_list['customer']['deliveryAddress']:
        data['telephone'] = packing_list['customer']['deliveryAddress']['telephone']
    if 'email' in packing_list['customer']:
        data['email'] = packing_list['customer']['email']

    if packing_list.get('warehouseId'):
        warehouse = db.warehouses.find_one(
            {'_id': packing_list['warehouseId']}, {'sendcloudSenderAddressId': 1}
        )
        if warehouse and warehouse.get('sendcloudSenderAddressId'):
            data['sender_address'] = warehouse['sendcloudSenderAddressId']

    payload = {'parcels': [data]}
    headers = {'Content-Type': 'application/json'}

    response = requests.post(
        'https://panel.sendcloud.sc/api/v2/parcels',
        headers=headers,
        json=payload,
        auth=(token, secret),
    )

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        if 'to_state' in lookup(response.json(), 'error.message'):
            raise SpynlException(_('only-ship-within-europe'))
        raise SpynlException(
            _('sendcloud-error'),
            developer_message=lookup(response.json(), 'error.message'),
        )

    return response.json().get('parcels', [])


class LabelsParameters(Schema):
    filter = Nested(ShippingFilter, required=True)


def shipping_labels(context, request):
    """
    Ship a packing list

    ---
    post:
      description: >
        Returns a number
      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'packing_list_labels.json#/definitions/LabelsParameters'
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the receiving.
          schema:
            type: file
    """
    parameters = LabelsParameters().load(request.json_payload)
    packing_list = request.db[context].find_one(
        {'_id': parameters['filter']['_id'], 'status': 'shipping'}
    )
    if not packing_list:
        raise SpynlException(_('no-packing-list-labels'))
    parcels = [parcel['id'] for parcel in packing_list.get('parcels', [])]
    if not parcels:
        raise SpynlException(_('no-parcels-for-packing-list'))

    label_response = get_sendcloud_labels(request, parcels)

    pdf = io.BytesIO()
    pdf.write(label_response.content)
    return make_pdf_file_response(request, pdf)


def get_sendcloud_labels(request, parcels):
    """get labels for parcels"""
    settings = request.db.tenants.find_one(
        {'_id': request.requested_tenant_id}, {'settings': 1}
    ).get('settings', {})

    try:
        token = settings['sendcloudApiToken']
        secret = settings['sendcloudApiSecret']
    except KeyError:
        raise SpynlException(_('sendcloud-not-configured'))

    payload = {'label': {'parcels': parcels}}
    try:
        response = requests.post(
            'https://panel.sendcloud.sc/api/v2/labels',
            json=payload,
            auth=(token, secret),
        )
        response.raise_for_status()
        label_response = requests.get(
            response.json()['label']['label_printer'], auth=(token, secret)
        )
        label_response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        raise SpynlException(
            _('sendcloud-error'),
            developer_message=error.response.json().get('error', {}).get('message', ''),
        )
    return label_response


def upload_pdf(fileobj):
    bucket = get_settings('spynl.printq.bucket')
    region = get_settings('spynl.printq.bucket.region')
    access_key_id = get_settings('spynl.printq.bucket.aws_access_key_id')
    secret_access_key = get_settings('spynl.printq.bucket.aws_secret_access_key')

    s3 = boto3.client(
        's3',
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )

    key = '{}/{}-{}.pdf'.format(
        os.environ.get('SPYNL_ENVIRONMENT', 'local'),
        datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
        uuid.uuid4().hex,
    )
    s3.upload_fileobj(fileobj, bucket, key)
    return {'url': 'https://s3.{}.amazonaws.com/{}/{}'.format(region, bucket, key)}


def send_document_to_printq(request, queue, payload):
    url = '{}/queue'.format(get_settings('spynl.printq.url'))
    try:
        response = requests.post(url, params={'queue': queue}, json=payload)
        response.raise_for_status()
    except requests.exceptions.HTTPError as error:
        raise SpynlException(
            _('printq-error'),
            # todo: what to put?
            developer_message=error.response.json().get('error', {}).get('message', ''),
        )


class CancelParameters(Schema):
    _id = fields.UUID(
        required=True,
        metadata={'description': '_id of the packing list that is being canceled'},
    )


def cancel(context, request):
    """
    Cancel a packing list.

    ---
    post:
      description: >
        Cancel a packing list. This will send a foxpro event to free up stock.
      tags:
        - data
      parameters:
        - name: body
          in: body
          required: false
          schema:
            $ref: 'packing_list_cancel.json#/definitions/CancelParameters'
      responses:
        "200":
          schema:
            $ref: 'save_response.json#/definitions/SaveResponse'
    """
    parameters = CancelParameters().load(request.json_payload)
    packing_list = request.db[context].find_one(
        {'_id': parameters['_id'], 'type': 'packing-list', 'active': True}
    )
    if not packing_list:
        raise SpynlException(_('document-does-not-exist'))

    packing_list = PackingListSchema.cancel(packing_list, request.cached_user['_id'])
    request.db[context].upsert_one({'_id': packing_list['_id']}, packing_list)

    insert_foxpro_events(
        request, packing_list, PackingListSchema.generate_cancel_fpqueries
    )

    return {'data': [str(packing_list['_id'])]}


def download_csv(context, request):
    """
    Download a csv document of a packing list in which each sku has its own line

    ---
    post:
      description: >
        Download a csv document of a packing list in which each sku has its own line.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'packing_list_download.json#/definitions/PackingListDownloadSchema'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The packing list as a csv file.
          schema:
            type: file
      tags:
        - data
    """
    parameters = PackingListDownloadSchema().load(request.json_payload)
    fields = PACKING_LIST_DOWNLOAD_FIELDS

    order = request.db[context].find_one(
        {
            '_id': parameters['_id'],
            'type': 'packing-list',
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
    temp_file = export_csv(header, result)

    return serve_csv_response(request.response, temp_file)


def download_excel(context, request):
    """
    Download an excel document of a packing list in which each sku has its own line

    ---
    post:
      description: >
        Download an excel document of a packing list in which each sku has its own line.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'packing_list_download.json#/definitions/PackingListDownloadSchema'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The packing list as an excel file.
          schema:
            type: file
      tags:
        - data
    """
    parameters = PackingListDownloadSchema().load(request.json_payload)
    fields = PACKING_LIST_DOWNLOAD_FIELDS

    order = request.db[context].find_one(
        {
            '_id': parameters['_id'],
            'type': 'packing-list',
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
