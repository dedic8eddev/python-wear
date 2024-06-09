import base64
import binascii
import copy
import datetime
import uuid

from marshmallow import (
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)

from spynl_schemas.fields import Nested, ObjectIdField
from spynl_schemas.order_terms import OrderTermsSchema
from spynl_schemas.packing_list import PackingListSchema
from spynl_schemas.shared_order_schemas import BaseOrderSchema, OrderProductSchema
from spynl_schemas.shared_schemas import Schema
from spynl_schemas.utils import BAD_CHOICE_MSG


class AuditEntry(Schema):
    username = fields.String(required=True)
    user_id = ObjectIdField(required=True)
    edit_date = fields.DateTime()

    @post_load
    def set_date(self, data, **kwargs):
        data['edit_date'] = datetime.datetime.utcnow()
        return data


class SalesOrderAuditTrailSchema(Schema):
    original_version_id = ObjectIdField(
        required=True,
        metadata={
            'description': '_id of the original document in the audit collection'
        },
    )
    remark = fields.String(
        # required=True, # todo make required when edited is added
        validate=validate.Length(min=1),
        metadata={'description': 'description of why it was edited'},
    )
    opened = fields.Nested(
        AuditEntry,
        metadata={'description': 'At what time and by who the order was opened.'},
    )
    edited = fields.Nested(
        AuditEntry,
        metadata={'description': 'At what time and by who the order was edited.'},
    )


class SalesOrderSchema(BaseOrderSchema):
    type = fields.Constant(
        constant='sales-order',
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'string',
                'default': 'sales-order',
                'enum': ['sales-order'],
            }
        },
    )
    directDelivery = fields.Boolean(
        metadata={
            'description': 'Set automatically after a sales order has been completed. '
            'A sales order that has both direct-delivery and non-direct-delivery '
            'products will be split up into two sales orders during the save. The '
            'sales order with the direct-delivery products will have this field set '
            'to True.'
        }
    )
    agentId = ObjectIdField()
    agentName = fields.String(metadata={'description': 'Full name of the agent.'})
    discountTerm1 = fields.Int()
    discountPercentage1 = fields.Float()
    discountTerm2 = fields.Int()
    discountPercentage2 = fields.Float()
    nettTerm = fields.Int()
    termsAndConditionsAccepted = fields.Boolean(load_default=False)
    signature = fields.String()
    signatureDate = fields.DateTime(
        metadata={
            'description': 'The local date and time the document was signed. Because '
            'the user might be offline during signing, this might be different '
            'from the date the order gets completed in the database.'
        }
    )
    signedBy = fields.String()
    completedDate = fields.DateTime(
        metadata={
            'description': 'The date the order was stored as complete in the database.'
        }
    )
    orderTerms = Nested(OrderTermsSchema, exclude=['tenant_id', '_id', 'active'])

    products = Nested(OrderProductSchema, many=True, load_default=list)
    # These two fields help continuing a draft by remembering the articles that
    # you've seen (in the UI) and the articles you favorited.
    visitedArticles = fields.List(fields.String)
    favoriteArticles = fields.List(fields.String)

    status = fields.String(
        required=True,
        validate=validate.OneOf(
            choices=['complete', 'draft'],
            error=BAD_CHOICE_MSG,
        ),
        metadata={
            'description': 'A draft order can be edited and deleted. As soon as an '
            'order is complete, a sales order cannot be edited again, unless an admin '
            'changes the status to "complete-open-for-edit" with the dedicated '
            'endpoint.'
        },
    )
    audit_trail = Nested(
        SalesOrderAuditTrailSchema,
        # this is always set automatically when appropriate:
        dump_only=True,
        many=True,
        metadata={
            'description': 'The audit trail is added if a complete sales order is '
            'opened for editing.'
        },
    )

    def load(self, data, *args, **kwargs):
        """
        Load and split sales orders. Sales orders that include direct deliveries will be
        split up into one sales order without direct deliveries, and one with all the
        direct deliveries. There will be a packing list made from the second sales order
        as well.
        """
        data = super().load(data, *args, **kwargs)

        if not kwargs.get('many'):
            data = [data]

        orders = []

        for sales_order in data:
            # we always save the original
            orders.append(sales_order)

            if sales_order['status'] != 'complete':
                continue

            sales_order['completedDate'] = datetime.datetime.utcnow()

            direct_delivery = []
            to_order = []

            for p in sales_order['products']:
                if p.get('directDelivery') == 'on':
                    direct_delivery.append(p)
                else:
                    to_order.append(p)

            if not direct_delivery:
                continue

            if to_order:
                # set the correct procucts on the sales order
                sales_order['products'] = to_order

                # make a new sales_order with the direct delivery items only
                for product in direct_delivery:
                    for sku in product['skus']:
                        sku['salesOrder'] = sales_order['_id']

                orders.append(
                    {
                        **copy.deepcopy(sales_order),
                        '_id': uuid.uuid4(),
                        'docNumber': uuid.uuid4(),
                        'products': direct_delivery,
                        'directDelivery': True,
                    }
                )
            # all products are direct delivery:
            else:
                sales_order['directDelivery'] = True

            if self.context.get('packing_list_on_direct_delivery', True):
                # make the packing list for the direct delivery items
                packing_list_data = copy.deepcopy(orders[-1])
                for key in ('_id', 'docNumber', 'status'):
                    packing_list_data.pop(key, None)

                # these fields are loaded from strings into datetime fields.
                for key in ('reservationDate', 'fixDate'):
                    if key in packing_list_data:
                        packing_list_data[key] = str(packing_list_data[key])

                self.check_customer_status(packing_list_data, self.context.get('db'))
                packing_list = PackingListSchema(context=self.context).load(
                    packing_list_data
                )
                PackingListSchema.add_sku_links(
                    packing_list[0], orders[-1]['docNumber']
                )
                orders.extend(packing_list)

        return orders

    @staticmethod
    def check_customer_status(data, db):
        """
        If the customer is blocked, the default status of 'open' for a packing list
        should be overwritten by 'pending'.
        """
        if not db:
            return
        customer = db.wholesale_customers.find_one({'_id': data['customer']['_id']})
        if not customer:
            raise ValidationError('Unknown customer')
        if customer.get('blocked'):
            data['status'] = 'pending'

    @pre_load
    def preprocess(self, data, **kwargs):
        if 'agentId' in self.context:
            data.setdefault('agentId', self.context['agentId'])

        # let the schema handle it.
        data.pop('type', None)
        return data

    @pre_load
    def check_status(self, data, **kwargs):
        # set status to complete when editing an opened order
        if self.context.get('editing_open_order'):
            data['status'] = 'complete'
        elif data.get('status') == 'complete-open-for-edit':
            raise ValidationError('Status not allowed, use dedicated endpoint.')
        return data

    @post_load
    def postprocess(self, data, **kwargs):
        data = super().postprocess(data, **kwargs)

        # These fields are to help continuing a draft. No need for them on a
        # completed order.
        if data['status'] == 'complete':
            if not data['products']:
                msg = 'Missing data for required field on completed order.'
                raise ValidationError(msg, 'products')

            data.pop('visitedArticles', None)
            data.pop('favoriteArticles', None)

        # set agentName
        if 'db' in self.context and 'agentId' in data:
            agent = self.context['db'].users.find_one({'_id': data['agentId']})
            if agent:
                data['agentName'] = agent.get('fullname', '')

        return data

    @post_load
    def add_audit_trail(self, data, **kwargs):
        """
        The audit trail cannot be edited, and is fetched from the database directly
        """
        original = self.context['db'].sales_orders.find_one({'_id': data['_id']})
        if self.context.get('editing_open_order'):
            try:
                audit_trail = original['audit_trail']
                audit_trail[0]['remark'] = self.context['audit_remark']
                audit_trail[0]['edited'] = AuditEntry().load(
                    {
                        'username': self.context['username'],
                        'user_id': self.context['user_id'],
                    }
                )
            except (KeyError, TypeError):
                raise ValidationError(
                    'Cannot edit an order without a partial audit log'
                )
            data['audit_trail'] = audit_trail
        else:
            if original and original.get('audit_trail'):
                data['audit_trail'] = original['audit_trail']
        return data

    @validates_schema
    def validate_accepted_order_terms(self, data, **kwargs):
        if data['status'] != 'complete':
            return
        if not data['termsAndConditionsAccepted']:
            raise ValidationError(
                'Must accept terms and conditions to complete order',
                'termsAndConditionsAccepted',
            )

    @validates_schema
    def validate_signed_by(self, data, **kwargs):
        if data['status'] != 'complete':
            return
        if 'signedBy' not in data:
            raise ValidationError('Missing data for required field', 'signedBy')

    @validates_schema
    def validate_signature(self, data, **kwargs):
        """
        Signature is supposed to be a base64 encoded image of a signature.

        Here we simply validate it's not empty if the order is complete.
        And that it is valid base64.
        """
        if data['status'] != 'complete':
            return

        if 'signature' not in data:
            raise ValidationError('Missing data for required field', 'signature')
        elif not data['signature']:
            raise ValidationError('May not be an empty base64 string.', 'signature')
        try:
            data_uri, signature = data['signature'].split(',')
            if data_uri != 'data:image/png;base64':
                raise ValueError

            base64.b64decode(signature, validate=True)
        except binascii.Error:
            raise ValidationError('Invalid base64 signature.', 'signature')
        except ValueError:
            msg = 'Invalid signature. Expects data:image/png;base64,SIGNATURE'
            raise ValidationError(msg, 'signature')

    @classmethod
    def prepare_for_pdf(cls, order, db=None, tenant_id=None):
        """
        Get the order terms for a draft before calling super, because unknown languages
        get removed there.
        """
        if order['customer'].get('language') == '':
            # remove an empty language so it gets defaulted properly:
            order['customer'].pop('language')
        if order['status'] == 'draft':
            cls.get_order_terms_for_draft(order, db, tenant_id)
        order = super().prepare_for_pdf(order, db=db, tenant_id=tenant_id)
        return order

    @staticmethod
    def open_for_edit(order, user, audit_id):
        order['status'] = 'complete-open-for-edit'
        audit_log = SalesOrderAuditTrailSchema().load(
            {
                'original_version_id': audit_id,
                'opened': {'username': user['username'], 'user_id': user['_id']},
            }
        )
        # order comes from database in endpoint, so we assume audit_trail is clean:
        order['audit_trail'] = [audit_log] + order.get('audit_trail', [])
