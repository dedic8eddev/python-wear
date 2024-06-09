"""
The endpoints for spynl.services.pdf
"""

import datetime
import uuid
from os import path

from babel import Locale, UnknownLocaleError
from marshmallow import EXCLUDE, fields, post_load
from pyramid_mailer.message import Attachment

from spynl_schemas import (
    BleachedHTMLField,
    ObjectIdField,
    SaleSchema,
    SalesOrderSchema,
    Schema,
    TransitSchema,
    lookup,
)
from spynl_schemas.tenant import OrderTemplate
from spynl_schemas.utils import get_address

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException
from spynl.main.mail import send_template_email
from spynl.main.serial.file_responses import make_pdf_file_response
from spynl.main.utils import required_args

from spynl.api.auth.utils import lookup_tenant

from spynl.services.pdf.pdf import (
    generate_eos_pdf,
    generate_packing_list_pdf,
    generate_pdf,
    generate_receipt_html_css,
    generate_receiving_pdf,
    generate_sales_order_pdf,
    generate_transit_html_css,
    get_image_location,
)
from spynl.services.pdf.preview_sales_order import PREVIEW_ORDER
from spynl.services.pdf.utils import get_email_settings, non_babel_translate


class SalesReceiptDownloadSchema(Schema):
    _id = ObjectIdField(
        required=True,
        metadata={
            'description': 'The objectId of the sales or consignment transaction'
        },
    )
    footer = BleachedHTMLField(
        load_default='',
        metadata={
            'description': 'The footer is a setting in the old printer settings. '
            'Until this has been moved to the user settings, the frontend should send '
            'it in. (key in printer settins: "receipt_footer")'
        },
    )
    printLoyaltyPoints = fields.Boolean(
        load_default=True, metadata={'description': 'Print loyalty points or not.'}
    )
    printExtendedReceipt = fields.Boolean(
        load_default=False,
        metadata={'description': 'Print extra information for barcode items.'},
    )

    class Meta:
        unknown = EXCLUDE
        ordered = True


class SalesReceiptEmailSchema(SalesReceiptDownloadSchema):
    # TODO: or should it default this to the email in the transaction?
    email = fields.Email(
        required=True, metadata={'description': 'The email the pdf should be send to'}
    )


def _generate_receipt_file(ctx, request, parameters):
    """generate the file for a sales receipt"""
    sale = request.db[ctx].find_one(
        {
            '_id': parameters['_id'],
            'tenant_id': request.requested_tenant_id,
            'type': {'$in': [2, 9]},
        }
    )
    if not sale:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )
    sale = SaleSchema().prepare_for_pdf(sale)
    user = request.cached_user
    tenant = lookup_tenant(request.db, request.requested_tenant_id)

    html, css = generate_receipt_html_css(request, sale, parameters, user, tenant)
    result = generate_pdf(html, css)

    filename = sale['nr'] + '.pdf'

    return result, filename


def email_sales_receipt(ctx, request):
    """
    Make a PDF from the html data for the receipt and email it.

    ---
    post:
      tags:
        - services
      description: >
        Email a pdf for a sales receipt.
        \n
        Located in spynl-services.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok', 'warning' or 'error'\n
        message      | string | description of errors
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: email_sales_receipt.json#/definitions/SalesReceiptEmailSchema
    """
    parameters = SalesReceiptEmailSchema().load(request.json_payload)
    result, filename = _generate_receipt_file(ctx, request, parameters)

    attachment = Attachment(filename, 'application/pdf', result.getvalue())
    email_settings = get_email_settings(request.cached_user, wholesale=False)

    send_template_email(
        request,
        parameters['email'],
        template_file='receipt_email',
        replacements={'body': email_settings['body']},
        subject=email_settings['subject'],
        reply_to=email_settings['reply_to'],
        sender=email_settings['sender'],
        sender_name=email_settings['sender_name'],
        attachments=[attachment],
        fail_silently=False,
    )

    result.close()

    return {'status': 'ok'}


def download_sales_receipt(ctx, request):
    """
    Make a PDF from the html data for a sales receipt.

    ---
    post:
      tags:
        - services
      description: >
        Generate a pdf for a sales receipt.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: download_sales_receipt.json#/definitions/SalesReceiptDownloadSchema
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the sales receipt.
          schema:
            type: file
    """
    parameters = SalesReceiptDownloadSchema().load(request.json_payload)
    result, filename = _generate_receipt_file(ctx, request, parameters)
    return make_pdf_file_response(request, result, filename)


class TransitEmailSchema(Schema):
    _id = ObjectIdField(
        required=True,
        metadata={
            'description': 'The objectId of the sales or consignment transaction'
        },
    )
    recipients = fields.List(
        fields.Email,
        required=True,
        metadata={'description': 'The email the pdf should be send to'},
    )
    message = BleachedHTMLField(
        metadata={
            'description': 'An optional message that will be added to the body of the '
            'email.'
        },
        load_default=None,
    )


def _get_transit_warehouse(request, wh):
    warehouse = request.db.warehouses.find_one(
        {'tenant_id': request.requested_tenant_id, 'wh': wh}
    )
    if not warehouse:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This warehouse does not exist',
        )
    data = get_address(warehouse.get('addresses', []), 'delivery')
    data['name'] = warehouse['name']
    if 'email' in warehouse:
        data['email'] = warehouse['email']
    return data


def _generate_transit_file(ctx, request, parameters):
    """generate the file for a sales receipt"""
    transit = request.db[ctx].find_one(
        {'_id': parameters['_id'], 'tenant_id': request.requested_tenant_id, 'type': 3}
    )
    if not transit:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )
    # TODO: add test for this!!!
    if transit['transit']['dir'] == 'to':
        to_warehouse = _get_transit_warehouse(
            request, transit['transit']['transitPeer']
        )
        from_warehouse = _get_transit_warehouse(request, transit['shop']['id'])
    else:
        from_warehouse = _get_transit_warehouse(
            request, transit['transit']['transitPeer']
        )
        to_warehouse = _get_transit_warehouse(request, transit['shop']['id'])

    transit = TransitSchema().prepare_for_pdf(transit)
    user = request.cached_user
    tenant = lookup_tenant(request.db, request.requested_tenant_id)

    html, css = generate_transit_html_css(
        request, transit, from_warehouse, to_warehouse, user, tenant
    )
    result = generate_pdf(html, css)

    filename = transit['nr'] + '.pdf'

    return dict(
        pdf_file=result,
        filename=filename,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
    )


def email_transit_pdf(ctx, request):
    """
    Make a PDF from the html data for the receipt and email it.

    ---
    post:
      tags:
        - services
      description: >
        Email a pdf for a sales receipt.
        \n
        Located in spynl-services.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok', 'warning' or 'error'\n
        message      | string | description of errors
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: email_transit_pdf.json#/definitions/TransitEmailSchema
    """
    parameters = TransitEmailSchema().load(request.json_payload)
    result = _generate_transit_file(ctx, request, parameters)

    attachment = Attachment(
        result['filename'], 'application/pdf', result['pdf_file'].getvalue()
    )
    email_settings = get_email_settings(request.cached_user, wholesale=False)

    replacements = {
        'message': parameters.get('message'),
        'from_warehouse': result['from_warehouse']['name'],
        'to_warehouse': result['to_warehouse']['name'],
    }

    for email in parameters['recipients']:
        send_template_email(
            request,
            email,
            template_file='transit_email',
            replacements=replacements,
            reply_to=email_settings['reply_to'],
            sender=email_settings['sender'],
            sender_name=email_settings['sender_name'],
            attachments=[attachment],
            fail_silently=False,
        )

    result['pdf_file'].close()

    return {'status': 'ok'}


class EmailOrderSchema(Schema):
    _id = fields.UUID(
        required=True, metadata={'description': 'The _id of the sales order.'}
    )
    recipients = fields.List(
        fields.Email,
        metadata={
            'description': 'If these emails are specified, no email is sent to the '
            'emails in the settings of the tenant or the customer. Instead the email '
            'is sent with the agent email as recipient, and to these emails as bcc.'
        },
    )


def email_sales_order_receipt(ctx, request):
    """
    Make a PDF receipt of a sales order and email it to the agent and customer.

    ---
    post:
      tags:
        - services
      description: >
        Agents can send a mail containing the receipt of the sales order to
        themselves, the customer and the email address registered under
        sales.confirmationEmail in the tenant settings. Or, if email addresses are
        specified, the email will be send to the agent as recipient, and to those
        addresses as bcc.

        \n
        Located in spynl-services.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok', 'warning' or 'error'\n
        message      | string | description of errors
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: email_sales_order_receipt.json#/definitions/EmailOrderSchema
    """
    recipients = []
    parameters = EmailOrderSchema().load(request.json_payload)
    order = request.db[ctx].find_one(
        {
            '_id': parameters['_id'],
            'type': 'sales-order',
            'tenant_id': request.requested_tenant_id,
        }
    )
    if not order:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )

    tenant_settings = request.db.tenants.find_one(
        {'_id': request.requested_tenant_id}, {'settings': 1}
    ).get('settings', {})

    if parameters.get('recipients'):
        bcc = parameters['recipients']
    else:
        bcc = None
        confirmation_email = lookup(tenant_settings, 'sales.confirmationEmail')
        if confirmation_email:
            if isinstance(confirmation_email, str):
                confirmation_email = [confirmation_email]
            recipients.extend(confirmation_email)

        customer_email = order['customer'].get('email')
        if customer_email:
            recipients.append(customer_email)

    agent = request.db.users.find_one({'_id': order['agentId']}, {'email': 1})
    recipients.append(agent['email'])

    settings = OrderTemplate().load(lookup(tenant_settings, 'sales.orderTemplate', {}))

    # PDF without terms and conditions:
    settings['print_terms_and_conditions'] = False
    result = generate_sales_order_pdf(
        request, order, settings, get_image_location(tenant_settings, sales=True)
    )
    pdf_name = _sales_order_file_name(order)
    attachments = [Attachment(pdf_name, 'application/pdf', result.getvalue())]

    # PDF with only the terms and conditions:
    if order.get('orderTerms', {}).get('orderPreviewText5'):
        settings['print_body'] = False
        settings['print_terms_and_conditions'] = True
        result = generate_sales_order_pdf(
            request,
            order,
            settings,
            get_image_location(tenant_settings, sales=True),
            load_order=False,
        )
        pdf_name = _sales_order_file_name(order, suffix='_tos')
        attachments.append(Attachment(pdf_name, 'application/pdf', result.getvalue()))
    email_settings = get_email_settings(request.cached_user, wholesale=True)

    send_template_email(
        request,
        recipients,
        template_file='receipt_email',
        replacements={
            'body': email_settings['body'],
            'customer': order['customer'].get('name'),
            'order_number': order.get('orderNumber', ''),
            'agent_email': agent['email'],
        },
        subject=email_settings['subject'],
        reply_to=email_settings['reply_to'],
        sender_name=email_settings['sender_name'],
        bcc=bcc,
        attachments=attachments,
        fail_silently=False,
    )

    result.close()

    # if you change recipients, in the test inbox[0].recipients also changes:
    recipients = recipients.copy()
    if bcc:
        recipients.extend(bcc)
    return {'data': {'recipients': recipients}}


class DownloadOrderSchema(Schema):
    _id = fields.UUID(
        required=True, metadata={'description': 'The _id of the sales order.'}
    )
    includeTOS = fields.Boolean(
        load_default=False,
        metadata={
            'description': 'Determines whether the terms of service/terms and '
            'conditions (orderTerms5) are included in the pdf.'
        },
    )


def download_sales_order_receipt(ctx, request):
    """
    Returns a pdf of a sales order for downloading.

    ---
    post:
      tags:
        - services
      description: >
        Generate a pdf for a sales order.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: download_sales_order_receipt.json#/definitions/DownloadOrderSchema
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the sales order.
          schema:
            type: file
    """
    parameters = DownloadOrderSchema().load(request.json_payload)

    order = request.db[ctx].find_one(
        {
            '_id': parameters['_id'],
            'type': 'sales-order',
            'tenant_id': request.requested_tenant_id,
        }
    )
    if not order:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )

    tenant_settings = request.db.tenants.find_one(
        {'_id': request.requested_tenant_id}, {'settings': 1}
    ).get('settings', {})
    settings = OrderTemplate().load(lookup(tenant_settings, 'sales.orderTemplate', {}))
    settings['print_terms_and_conditions'] = parameters['includeTOS']

    result = generate_sales_order_pdf(
        request, order, settings, get_image_location(tenant_settings, sales=True)
    )

    filename = _sales_order_file_name(order)

    return make_pdf_file_response(request, result, filename)


def _sales_order_file_name(order, suffix=''):
    """determine what the name of the order pdf should be"""
    if order.get('status') == 'complete':
        return '{}{}.pdf'.format(order['orderNumber'], suffix)
    else:
        language = order.get('customer', {}).get('language', 'en')
        return '{}{}.pdf'.format(non_babel_translate('draft', language), suffix)


def preview_sales_order_receipt(ctx, request):
    """
    Returns a preview pdf of a sales order for downloading.

    ---
    post:
      tags:
        - services
      description: >
        Download a preview pdf of a sales order. If an orderTermsId is supplied
        via the filter, a preview is made using those particular order terms.
        If no id is provided, the order terms are left blank.
        \n
        Located in spynl-services.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        filter    | object       |          | Can contain orderTermsId\n

        ### Response

        pdf-file\n
    """

    class PreviewOrderSchema(SalesOrderSchema):
        """overwrite method that needs database"""

        @post_load
        def add_audit_trail(self, data, **kwargs):
            return data

    order = PreviewOrderSchema(partial=True).load(PREVIEW_ORDER)[0]
    # is not defaulted because of partial and cannot be added before,
    # because it is popped in pre load:
    order['type'] = 'sales-order'

    if 'orderTermsId' in request.args.get('filter', {}):
        try:
            _id = uuid.UUID(request.args['filter']['orderTermsId'])
        except ValueError:
            raise SpynlException(
                message=_('validation-error'),
                developer_message='The orderTermsId given is not a valid UUID.',
            )

        order_terms = request.db.order_terms.find_one(
            {'_id': _id, 'tenant_id': request.requested_tenant_id}
        )
        if not order_terms:
            raise SpynlException(
                message=_('validation-error'),
                developer_message='The orderTermsId given does not exist.',
            )
        order['orderTerms'] = order_terms
        order['customer']['language'] = order_terms.get('language', 'en')
        try:
            Locale.parse(order['customer']['language'])
        except UnknownLocaleError:
            order['customer']['language'] = 'en'

    tenant = request.db.tenants.find_one({'_id': request.requested_tenant_id})

    # use local images for the preview pdf
    image_location = 'file:///' + path.join(
        path.dirname(path.abspath(__file__)), 'pdf-templates', 'images/'
    )

    settings = OrderTemplate().load(
        tenant.get('settings', {}).get('sales', {}).get('orderTemplate', {})
    )
    properties = [
        {'name': field, 'value': 'dummy'}
        for field in settings.get('propertiesOnOrder', [])
    ]
    for product in order['products']:
        product['properties'] = properties
    result = generate_sales_order_pdf(request, order, settings, image_location)

    return make_pdf_file_response(request, result)


@required_args('_id')
def download_packing_list_pdf(ctx, request):
    """
    Returns a pdf of a packing list for downloading.

    ---
    post:
      tags:
        - services
      description: >
        Generate a pdf for a packing list.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              _id:
                type: string
                description: the _id of the packing list.
            required:
              - _id
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the packing list.
          schema:
            type: file
    """
    _id = fields.UUID().deserialize(request.args['_id'])

    order = request.db[ctx].find_one(
        {'_id': _id, 'type': 'packing-list', 'tenant_id': request.requested_tenant_id}
    )
    if not order:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )

    wholesale_id = order['customer']['_id']
    employee = request.pymongo_db.wholesale_customers.find_one({'_id': wholesale_id})
    if employee:
        order['customer']['employee'] = employee.get('employee', False)
    else:
        order['customer']['employee'] = False

    tenant_settings = request.db.tenants.find_one(
        {'_id': request.requested_tenant_id}, {'settings': 1}
    ).get('settings', {})
    result = generate_packing_list_pdf(
        request, order, get_image_location(tenant_settings, sales=True)
    )

    filename = '{}.pdf'.format(order['orderNumber'])

    return make_pdf_file_response(request, result, filename)


# TODO move to spynl/api/logistics/packing_lists.py after spynl.services
# is removed
@required_args('_id')
def download_receivings_pdf(ctx, request):
    """
    Returns a pdf of a receiving order for downloading.

    ---
    post:
      tags:
        - services
      description: >
        Download a pdf of a receiving order.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
             type: object
             properties:
               _id:
                 type: string
                 description: the _id of the receiving.
             required:
             - _id
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the receiving.
          schema:
            type: file
    """
    _id = fields.UUID().deserialize(request.args['_id'])

    receiving = request.db[ctx].find_one(
        {'_id': _id, 'tenant_id': request.requested_tenant_id}
    )

    if not receiving:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This order does not exist',
        )

    if receiving['status'] != 'complete':
        raise SpynlException(_('pdf-needs-complete-receiving'))

    settings = request.db.tenants.find_one(
        {'_id': request.requested_tenant_id}, {'settings': 1}
    ).get('settings', {})
    result = generate_receiving_pdf(request, receiving, get_image_location(settings))

    filename = receiving['orderNumber']

    return make_pdf_file_response(request, result, filename)


@required_args('_id')
def download_eos_pdf(ctx, request):
    """
    Returns a pdf of a End of Shift document for downloading.

    ---
    post:
      tags:
        - services
      description: >
        Download a pdf of a End of Shift document.
        \n
        Located in spynl-services.

        ### Response

        pdf-file\n
      parameters:
        - name: body
          in: body
          required: true
          schema:
             type: object
             properties:
               _id:
                 type: string
                 description: the _id of the End of Shift document.
             required:
             - _id
    """
    _id = request.args['_id']

    document = request.db[ctx].find_one(
        {'_id': _id, 'tenant_id': request.requested_tenant_id}
    )

    if not document:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This document does not exist',
        )

    if document['status'] != 'completed':
        raise SpynlException(_('pdf-needs-complete-eos'))

    result = generate_eos_pdf(request, document)

    filename = _('end-of-shift').translate()

    return make_pdf_file_response(request, result, filename)


class EOSDocumentEmailSchema(Schema):
    _id = fields.String(
        required=True, metadata={'description': 'The objectId of the eos report'}
    )
    recipients = fields.List(
        fields.Email,
        required=True,
        metadata={'description': 'The email the pdf should be send to'},
    )
    message = BleachedHTMLField(
        metadata={
            'description': 'An optional message that will be added to the body of the '
            'email.'
        },
        load_default=None,
    )


def email_eos_document(ctx, request):
    """
    Make a PDF for the eos document and email it.

    ---
    post:
      tags:
        - services
      description: >
        Email a pdf for an eos document.
        \n
        Located in spynl-services.

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: email_eos_document.json#/definitions/EOSDocumentEmailSchema
    """
    parameters = EOSDocumentEmailSchema().load(request.json_payload)

    document = request.db[ctx].find_one(
        {'_id': parameters['_id'], 'tenant_id': request.requested_tenant_id}
    )

    if not document:
        raise SpynlException(
            message=_('document-does-not-exist'),
            developer_message='This document does not exist',
        )

    if document['status'] != 'completed':
        raise SpynlException(_('pdf-needs-complete-eos'))

    result = generate_eos_pdf(request, document)
    filename = _('end-of-shift').translate()
    attachment = Attachment(filename, 'application/pdf', result.getvalue())
    email_settings = get_email_settings(request.cached_user, wholesale=False)

    replacements = {
        'message': parameters.get('message'),
        'tz': request.cached_user.get('tz', 'Europe/Amsterdam'),
        'locale': request.cached_user.get('language', 'nl-nl')[0:2],
        'device': document['device']['name'],
        'location': document['shop'].get('name', document['shop']['id']),
        'periodStart': document['periodStart'],
        'periodEnd': document['periodEnd'],
        'fullname': request.cached_user.get(
            'fullname', request.cached_user['username']
        ),
        'now': datetime.datetime.now(datetime.timezone.utc),
    }

    for email in parameters['recipients']:
        send_template_email(
            request,
            email,
            template_file='email_eos_document',
            replacements=replacements,
            reply_to=email_settings['reply_to'],
            sender=email_settings['sender'],
            sender_name=email_settings['sender_name'],
            attachments=[attachment],
            fail_silently=False,
        )

    result.close()

    return {'status': 'ok'}
