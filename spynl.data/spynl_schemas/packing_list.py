import copy
import datetime
import re
import uuid

from marshmallow import ValidationError, fields, post_load, validate, validates_schema

from spynl_schemas.fields import Nested, ObjectIdField
from spynl_schemas.foxpro_serialize import resolve, serialize
from spynl_schemas.order_terms import OrderTermsSchema
from spynl_schemas.shared_order_schemas import (
    AddressSchema,
    BaseOrderSchema,
    OrderProductSchema,
    WholesaleCustomerSchema,
)
from spynl_schemas.shared_schemas import BaseSkuSchema, Property, Schema
from spynl_schemas.utils import BAD_CHOICE_MSG

PACKING_LIST_STATUSES = [
    'pending',
    'open',
    'picking',
    'incomplete',
    'complete',
    'complete-and-discard',
    'complete-and-move',
    'ready-for-shipping',
    'shipping',
    'cancelled',
]


class PackingListWholesaleCustomerSchema(WholesaleCustomerSchema):
    deliveryAddress = Nested(AddressSchema, required=True)


class PackingListBaseSkuSchema(BaseSkuSchema):
    picked = fields.Integer(
        load_default=0,
        metadata={
            'description': 'Items on a sales order often become available at different '
            'times. When assembling an order, this field is used to keep track of how '
            'many items are picked.'
        },
    )
    link = fields.List(
        fields.UUID,
        metadata={
            'description': 'A list of all the docNumbers linked to the sku. e.g. the '
            'sales order the packing list was made from, or a packing list it was '
            'split of off.'
        },
    )

    @staticmethod
    def add_link(sku, doc_number):
        if 'link' not in sku:
            sku['link'] = []
        sku['link'].append(doc_number)

    @classmethod
    def fill_in_color_fields(cls, sku):
        """
        Packing lists from the packing list sync don't have colorCode and
        colorDescription fields filled.
        """
        # also overwrite if empty string:
        if not sku.get('colorCode'):
            strings = [sku.get('mainColorCode'), sku.get('subColorCode')]
            sku['colorCode'] = '/'.join([s for s in strings if s])
        if not sku.get('colorDescription'):
            strings = [sku.get('mainColorDescription'), sku.get('subColorDescription')]
            sku['colorDescription'] = ' '.join([s for s in strings if s])
        return sku


class PackingListProductSchema(OrderProductSchema):
    skus = Nested(PackingListBaseSkuSchema, many=True, required=True)
    customsProperties = Nested(
        Property,
        many=True,
        metadata={
            'description': 'Properties needed for customs. If they are needed, FoxPro '
            'will sync them'
        },
    )

    class Meta(OrderProductSchema.Meta):
        exclude = ('skus.purchaseOrder', 'directDelivery')


class StatusHistorySchema(Schema):
    user = ObjectIdField(
        required=True, metadata={'description': 'The user setting the status'}
    )
    status = fields.String(required=True, metadata={'description': 'The status'})
    date = fields.DateTime(
        required=True, metadata={'description': 'The date the status was set'}
    )


class ParcelSchema(Schema):
    """Schema used to load the information retrieved from sendcloud"""

    id = fields.Integer(
        required=True, metadata={'description': 'The id of the parcel in sendcloud'}
    )
    tracking_number = fields.String(
        required=True, metadata={'description': 'The tracking number for the parcel'}
    )
    tracking_url = fields.String(
        metadata={'description': 'The url to track the parcel'}
    )
    collo_nr = fields.Integer(
        metadata={
            'description': 'A number indicating the collo number within a shipment. '
            'For a non-multi-collo shipment, this value will always be 0. In a '
            'multi-collo shipment with 3 collos, this number will range from 0 to 2.'
        }
    )
    colli_tracking_number = fields.String(
        metadata={
            'description': 'Multi-collo only. This is a tracking number assigned by '
            'the carrier to identify the entire multi-collo shipment.'
        }
    )


class PackingListSchema(BaseOrderSchema):
    type = fields.Constant(
        constant='packing-list',
        metadata={
            '_jsonschema_type_mapping': {
                'type': 'string',
                'default': 'packing-list',
                'enum': ['packing-list'],
            }
        },
    )
    products = Nested(PackingListProductSchema, many=True, load_default=list)
    customer = Nested(PackingListWholesaleCustomerSchema, required=True)
    orderPicker = ObjectIdField(
        metadata={
            'description': 'The id of the user who is picking, or picked the order.'
        }
    )
    orderPickerName = fields.String(
        metadata={'description': 'The fullname of the orderpicker.'}
    )
    # status_history = Nested(
    #     StatusHistorySchema,
    #     many=True,
    #     metadata={'description': 'History of status changes'},
    # )
    status_history = fields.List(
        fields.Dict, metadata={'description': 'History of status changes'}
    )
    status = fields.String(
        load_default='open',
        validate=validate.OneOf(choices=PACKING_LIST_STATUSES, error=BAD_CHOICE_MSG),
    )
    warehouseId = fields.String(
        metadata={
            'description': 'The Mongo-id of the warehouse document from the database.'
        }
    )
    orderTerms = Nested(
        OrderTermsSchema, exclude=['tenant_id', '_id', 'active', 'orderPreviewText5']
    )
    numberOfParcels = fields.Integer(
        metadata={'description': 'Number of parcels for the packing list'}
    )
    parcels = Nested(
        ParcelSchema,
        many=True,
        metadata={'description': 'List of parcels the order is shipping in.'},
    )

    @validates_schema
    def validate_no_parcels(self, data, **kwargs):
        if data['status'] in [
            'incomplete',
            'complete',
            'complete-and-discard',
            'complete-and-move',
            'ready-for-shipping',
        ]:
            if 'numberOfParcels' not in data:
                raise ValidationError(
                    'Field is required for this status', field_name='numberOfParcels'
                )

    @post_load
    def postprocess(self, data, **kwargs):
        self.set_order_picker(data)
        self.set_date_fields(data)

        db = self.context['db']
        original = db.sales_orders.find_one({'_id': data['_id']}) or {}
        status_history = original.get('status_history', [])

        # status check might split up the packing list
        packing_lists = self.status_check(data, status_history)

        # the potential new packing_list already has it's status history
        # only set it for the original here.
        self.set_status_history(packing_lists[0], status_history)

        # remove empty products and skus:
        for packing_list in packing_lists:
            for product in packing_list['products']:
                product['skus'] = [sku for sku in product['skus'] if sku['qty']]
            packing_list['products'] = [
                product for product in packing_list['products'] if product['skus']
            ]

        return packing_lists

    @staticmethod
    def reset(data):
        data.pop('orderPicker', None)
        data.pop('orderPickerName', None)
        for p in data['products']:
            for sku in p['skus']:
                sku['picked'] = 0
        if 'numberOfParcels' in data:
            data.pop('numberOfParcels')

    def status_check(self, data, status_history):
        if not status_history:
            return [data]

        roles = self.context['user_roles']
        user_id = self.context['user_id']

        old_status = status_history[0]['status']
        new_status = data['status']

        # cannot edit cancelled packing lists or cancel via /save enpoint:
        if old_status == 'cancelled' or new_status == 'cancelled':
            raise ValidationError('Invalid status change')

        if old_status == new_status:
            return [data]

        elif {old_status, new_status} == {
            'pending',
            'open',
        } and 'picking-admin' in roles:
            return [data]

        elif [old_status, new_status] == ['open', 'picking']:
            return [data]

        elif old_status == 'picking':
            if new_status == 'open' and user_id == data['orderPicker']:
                self.reset(data)
                return [data]

            elif new_status == 'pending' and 'picking-admin' in roles:
                self.reset(data)
                return [data]

            elif new_status == 'complete' and user_id == data['orderPicker']:
                if any(
                    s['qty'] != s['picked'] for p in data['products'] for s in p['skus']
                ):
                    data['status'] = 'incomplete'
                else:
                    data['status'] = (
                        'ready-for-shipping'
                        if self.check_autoship(data)
                        else 'complete'
                    )
                return [data]

        elif old_status == 'incomplete':
            if new_status == 'pending' and 'picking-admin' in roles:
                self.reset(data)
                return [data]
            elif new_status == 'complete-and-discard' and 'picking-admin' in roles:
                for p in data['products']:
                    for sku in p['skus']:
                        sku['qty'] = sku['picked']
                data['status'] = (
                    'ready-for-shipping' if self.check_autoship(data) else 'complete'
                )
                return [data]
            elif new_status == 'complete-and-move' and 'picking-admin' in roles:
                data['status'] = (
                    'ready-for-shipping' if self.check_autoship(data) else 'complete'
                )

                original, new = self.split_packing_list(data)
                self.set_status_history(new, [])
                return original, new

        raise ValidationError('Invalid status change')

    @staticmethod
    def check_autoship(packing_list):
        """
        Dummy function. In the future this should check if the tenant has autoshipping
        in place and return False if this is not the case.
        """
        return True

    @staticmethod
    def split_packing_list(packing_list):
        new_packing_list = copy.deepcopy(packing_list)
        new_packing_list.update(
            {
                '_id': uuid.uuid4(),
                'docNumber': uuid.uuid4(),
                'products': [],
                'status': 'pending',
            }
        )
        new_packing_list.pop('numberOfParcels')
        for product in packing_list['products']:
            included = False
            for sku in product['skus']:
                if sku['picked'] != sku['qty']:
                    if not included:
                        new_packing_list['products'].append(
                            {**copy.deepcopy(product), 'skus': []}
                        )
                        included = True
                    not_picked = sku['qty'] - sku['picked']
                    new_packing_list['products'][-1]['skus'].append(
                        {**copy.deepcopy(sku), 'qty': not_picked, 'picked': 0}
                    )
                    PackingListBaseSkuSchema.add_link(
                        new_packing_list['products'][-1]['skus'][-1],
                        packing_list['docNumber'],
                    )
                    sku['qty'] = sku['picked']
        return [packing_list, new_packing_list]

    def set_status_history(self, data, status_history, **kwargs):
        if len(status_history) < 1 or data['status'] != status_history[0]['status']:
            data['status_history'] = [
                {
                    'user': self.context['user_id'],
                    'status': data['status'],
                    'date': datetime.datetime.utcnow(),
                }
            ] + status_history

    def set_order_picker(self, data, **kwargs):
        if data['status'] == 'picking':
            data['orderPicker'] = self.context['user_id']
            data['orderPickerName'] = self.context.get('user_fullname', '')

    @classmethod
    def cancel(cls, packing_list, user_id):
        packing_list['status'] = 'cancelled'
        cls.reset(packing_list)
        cls(context={'user_id': user_id}).set_status_history(
            packing_list, copy.deepcopy(packing_list['status_history'])
        )
        return packing_list

    @staticmethod
    def add_sku_links(packing_list, doc_number):
        for product in packing_list.get('products', []):
            for sku in product.get('skus', []):
                PackingListBaseSkuSchema.add_link(sku, doc_number)

    @classmethod
    def fill_in_color_fields(cls, order):
        for product in order.get('products', []):
            for sku in product.get('skus', []):
                sku = PackingListBaseSkuSchema.fill_in_color_fields(sku)
        return order

    @classmethod
    def prepare_for_pdf(cls, order, db=None, tenant_id=None):
        """
        Get the order terms before calling super, because unknown languages
        get removed there.
        """
        if order['customer'].get('language') == '':
            # remove an empty language so it gets defaulted properly:
            order['customer'].pop('language')
        cls.get_order_terms_for_draft(order, db, tenant_id)
        order = cls.fill_in_color_fields(order)
        # For when we want to add the sales orders to the packing list:
        # sales_orders = {
        #     sku['salesOrder']
        #     for product in order['products']
        #     for sku in product['skus']
        #     if sku.get('salesOrder')
        # }

        order = super().prepare_for_pdf(order, db=db, tenant_id=tenant_id)
        return order

    @staticmethod
    def generate_shipping_fp_event(data, *common):
        """
        Return the needed foxpro query for a shipped packing list.

        The foxpro database expects a ; separated list for every product
        separated by a "|", example: PL-12345;123456;2;2;1|PL-12345;123457;3;2;1
        """
        tracking_numbers = []
        for parcel in list(resolve(data, 'parcels')):
            tracking_numbers.append(parcel['tracking_number'])
        query = [
            *common,
            ('refid', resolve(data, 'docNumber')),
            ('ordernumber', resolve(data, 'orderNumber')),
        ]

        if len(tracking_numbers) > 0:
            query.append(
                (
                    'tracking_number',
                    ",".join("'" + str(x) + "'" for x in tracking_numbers),
                )
            )
        barcodes = ['orderNumber;ean;qty_original;qty_loaded;qty_colli']
        for product in data['products']:
            for sku in product['skus']:
                barcodes.append(
                    ';'.join(
                        [
                            resolve(data, 'orderNumber'),
                            resolve(sku, 'barcode'),
                            str(resolve(sku, 'qty')),
                            str(resolve(sku, 'picked')),
                            str(data.get('numberOfParcels', 0)),
                        ]
                    )
                )

        query.append(('barcodes', '|'.join(barcodes)))

        return serialize([('shipPackingList', query)])

    @staticmethod
    def generate_cancel_fpqueries(data, *common):
        sendorder = [
            *common,
            ('refid', resolve(data, 'docNumber')),
            ('ordernumber', resolve(data, 'orderNumber')),
            ('uuid', resolve(data, 'customer._id')),
        ]

        sendorder.append(('action', 'pakbon'))

        for product in data['products']:
            for sku in product['skus']:
                barcode = resolve(sku, 'barcode')
                if 'remarks' in sku:
                    barcode += ':' + resolve(sku, 'remarks')
                sendorder.extend(
                    [
                        ('barcode', barcode),
                        ('qty', 0),
                        # NOTE We don't save prices so we set price to 0 which forces
                        # foxpro to look them up when they pick up the event
                        ('price', 0),
                        ('picked', 0),
                    ]
                )

        return serialize([('sendOrder', sendorder)])


class PackingListSyncSchema(PackingListSchema):
    """Schema for the lambda packing list sync (foxpro to mongo)."""

    warehouseId = fields.Method(
        deserialize='set_warehouse', required=True, data_key='warehouse'
    )

    def set_warehouse(self, value):
        warehouse = self.context['db'].warehouses.find_one(
            {'wh': value, 'tenant_id': self.context['tenant_id']}, {'_id': 1}
        )
        if not warehouse:
            raise ValidationError('warehouse does not exist')
        return str(warehouse['_id'])

    @post_load
    def postprocess(self, data, **kwargs):
        self.set_date_fields(data)
        return data
