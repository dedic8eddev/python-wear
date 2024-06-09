import datetime

from marshmallow import ValidationError, fields, post_load, validate, validates_schema

from spynl_schemas import Nested, Schema

from spynl.main.serial.file_responses import (
    METADATA_DESCRIPTION,
    ColumnMetadata,
    export_csv,
    export_excel,
    export_header,
    serve_csv_response,
    serve_excel_response,
)

from spynl.api.mongo.query_schemas import format_documentation_possibilities
from spynl.api.retail.sales_reports import TURNOVER_CALCULATION
from spynl.api.retail.utils import PAYMENT_METHODS, SortSchema, flatten_result

GROUPS = {
    'shopName': 'shop.name',
    'shopId': 'shop.id',
    'cashierName': 'cashier.fullname',
    'loyaltyNr': 'customer.loyaltynr',
    'customerEmail': 'customer.email',
    'customerLastName': 'customer.lastname',
    'docNumber': 'nr',
    'discountReason': 'discountreason',
    'withdrawalReason': 'withdrawelreason',
    'day': {'$dateToString': {'date': '$created.date', 'format': '%Y-%m-%d'}},
    'month': {'$dateToString': {'date': '$created.date', 'format': '%m'}},
    'week': {'$dateToString': {'date': '$created.date', 'format': '%U'}},
    'year': {'$dateToString': {'date': '$created.date', 'format': '%Y'}},
    'dow': {'$dateToString': {'date': '$created.date', 'format': '%w'}},
    'cardProvider': 'cardProvider',
    'device': 'created.user.username',
    'remark': 'remark',
}

GROUPS_FILTER = {
    'shopName': 'shop.name',
    'cashierName': 'cashier.fullname',
    'loyaltyNr': 'customer.loyaltynr',
    'customerEmail': 'customer.email',
    'discountReason': 'discountreason',
    'withdrawalReason': 'withdrawelreason',
    'day': {'$dateToString': {'date': '$created.date', 'format': '%Y-%m-%d'}},
    'month': {'$dateToString': {'date': '$created.date', 'format': '%m'}},
    'week': {'$dateToString': {'date': '$created.date', 'format': '%U'}},
    'year': {'$dateToString': {'date': '$created.date', 'format': '%Y'}},
    'dow': {'$dateToString': {'date': '$created.date', 'format': '%w'}},
    'cardProvider': 'cardProvider',
}

FIELDS = [
    'storeCreditPaid',
    'turnover',
    'cash',
    'numberOfSales',
    'creditcard',
    'creditreceipt',
    'pin',
    'storeCredit',
    'totalAmount',
    'vatHigh',
    'vatLow',
    'withdrawal',
    'deposit',
    'netQty',
    'qtySold',
    'qtyReturned',
    'numberOfItemSales',
    'netQtyPerReceipt',
    'turnoverPerReceipt',
    'turnoverPerItem',
    'totalDiscountCoupon',
    'totalCashBackCoupon',
    'totalGiftVoucherInactive',
    'totalGiftVoucherActive',
    'totalCreditReceipt',
    'totalCouponAsArticle',
]

AVERAGES = {
    'netQtyPerReceipt': {
        '$cond': {
            'if': {'$gt': ['$numberOfItemSales', 0]},
            'then': {'$divide': ['$netQty', '$numberOfItemSales']},
            'else': 0,
        }
    },
    'turnoverPerReceipt': {
        '$cond': {
            'if': {'$gt': ['$numberOfItemSales', 0]},
            'then': {'$divide': ['$turnover', '$numberOfItemSales']},
            'else': 0,
        }
    },
    'turnoverPerItem': {
        '$cond': {
            'if': {'$ne': ['$netQty', 0]},
            'then': {'$divide': ['$turnover', {'$abs': '$netQty'}]},
            'else': 0,
        }
    },
}

FIELD_DEPENDENCIES = {
    'netQtyPerReceipt': ['numberOfItemSales', 'netQty'],
    'turnoverPerReceipt': ['numberOfItemSales', 'turnover'],
    'turnoverPerItem': ['turnover', 'netQty'],
}


class GroupsAndFieldsDocumentation(Schema):
    """Schema used for documenting the response"""

    # GROUPS
    shopName = fields.String()
    shopId = fields.String()
    cashierName = fields.String()
    loyaltyNr = fields.String()
    customerEmail = fields.String()
    docNumber = fields.String(metadata={'description': 'Can be a UUID'})
    discountReason = fields.String()
    withdrawalReason = fields.String()
    day = fields.Integer()
    month = fields.Integer(metadata={'description': 'January is 1.'})
    week = fields.Integer()
    year = fields.Integer()
    dow = fields.Integer(
        metadata={
            'description': 'Int representation of the day of the week. Sunday is 1.'
        }
    )
    customerLastName = fields.String()
    cardProvider = fields.String()
    device = fields.String()
    remark = fields.String()
    # FIELDS
    storeCreditPaid = fields.Decimal()
    turnover = fields.Decimal()
    cash = fields.Decimal()
    numberOfSales = fields.Integer(
        metadata={
            'description': 'Number of sales, includes returns and sales without '
            'items. Contrast with numberOfItemSales.'
        }
    )
    creditcard = fields.Decimal()
    creditreceipt = fields.Decimal()
    pin = fields.Decimal()
    storeCredit = fields.Decimal()
    totalAmount = fields.Decimal()
    vatHigh = fields.Decimal(metadata={'description': 'The amount of high VAT paid'})
    vatLow = fields.Decimal(metadata={'description': 'The amount of low VAT paid'})
    withdrawal = fields.Decimal()
    deposit = fields.Decimal()
    netQty = fields.Integer(
        metadata={'description': 'The net quantity of items, returns are substracted.'}
    )
    qtySold = fields.Integer()
    qtyReturned = fields.Integer()
    numberOfItemSales = fields.Integer(
        metadata={
            'description': 'The number of transactions that have at least one item '
            'sold or returned. Contrast with numberOfSales'
        }
    )
    netQtyPerReceipt = fields.Decimal(
        metadata={
            'description': 'The average net quantity per item receipt (see '
            'numberOfItemSales definition).'
        }
    )
    turnoverPerReceipt = fields.Decimal(
        metadata={
            'description': 'The average turnover per item receipt (see '
            'numberOfItemSales definition).'
        }
    )
    turnoverPerItem = fields.Decimal(
        metadata={'description': 'The average turnover per net quantity.'}
    )
    totalDiscountCoupon = fields.Decimal(metadata={'description': 'K'})
    totalCashBackCoupon = fields.Decimal(metadata={'description': 'KC'})
    totalGiftVoucherInactive = fields.Decimal(metadata={'description': 'KI'})
    totalGiftVoucherActive = fields.Decimal(metadata={'description': 'KU'})
    totalCreditReceipt = fields.Decimal(metadata={'description': 'KT'})
    totalCouponAsArticle = fields.Decimal(metadata={'description': 'KA'})


class FloatCompare(Schema):
    value = fields.Float(required=True)
    operator = fields.String(required=True, validate=validate.OneOf(['gt', 'lt']))

    @post_load
    def postprocess(self, data, **kwargs):
        return {'$' + data['operator']: data['value']}


class JournalFilter(Schema):
    DEFAULT_DATE_RANGE = 7  # days

    startDate = fields.DateTime()
    endDate = fields.DateTime()
    turnover = Nested(FloatCompare)
    storeCreditPaid = Nested(FloatCompare)
    totalNumber = Nested(FloatCompare)

    withdrawelReason = fields.Method(deserialize='filter_in')
    discountReason = fields.Method(deserialize='filter_in')
    docNumber = fields.Method(deserialize='filter_in')
    customerEmail = fields.Method(deserialize='filter_in')
    shopName = fields.Method(deserialize='filter_in')
    shopId = fields.Method(deserialize='filter_in')
    cashierName = fields.Method(deserialize='filter_in')
    loyaltyNr = fields.Method(deserialize='filter_in')
    customerLastName = fields.Method(deserialize='filter_in')
    cardProvider = fields.Method(deserialize='filter_in')
    device = fields.Method(deserialize='filter_in')
    remark = fields.Method(deserialize='filter_in')

    paymentMethod = fields.List(
        fields.String, validate=validate.ContainsOnly(PAYMENT_METHODS)
    )

    def filter_in(self, value):
        return {'$in': fields.List(fields.Field).deserialize(value)}

    @post_load
    def postprocess(self, data, **kwargs):
        data.update({'tenant_id': self.context['tenant_id'], 'active': True})

        data['type'] = 2
        for key in GROUPS:
            if key in data:
                data[GROUPS[key]] = data.pop(key)

        if 'discountreason' in data:
            filter_ = data.pop('discountreason')

            data.setdefault('$or', [])
            data['$or'].extend(
                [{'discountreason': filter_}, {'discountreason.desc': filter_}]
            )

        if len(data.get('paymentMethod', [])) == 1:
            data['payments.{}'.format(data['paymentMethod'][0])] = {'$ne': 0}
            data.pop('paymentMethod')
        elif len(data.get('paymentMethod', [])) > 1:
            payment_filter = []
            for method in data.pop('paymentMethod', []):
                payment_filter.append({f'payments.{method}': {'$ne': 0}})
            if '$or' in data:
                data['$and'] = [{'$or': data.pop('$or')}, {'$or': payment_filter}]
            else:
                data['$or'] = payment_filter

        return data

    @post_load
    def handle_dates(self, data, **kwargs):
        # TODO: this won't work if only an enddate is given that is more than
        # DEFAULT_DATE_RANGE ago
        data['created.date'] = {}
        now = datetime.datetime.utcnow()
        start = datetime.datetime(now.year, now.month, now.day) - datetime.timedelta(
            days=JournalFilter.DEFAULT_DATE_RANGE
        )
        for field, operator, default in [
            ('startDate', '$gte', start),
            ('endDate', '$lte', now),
        ]:
            data['created.date'][operator] = data.pop(field, default)
        return data


class Journal(Schema):
    limit = fields.Integer(validate=validate.Range(min=0))
    skip = fields.Integer(validate=validate.Range(min=0), load_default=0)
    filter = Nested(JournalFilter, load_default=dict)
    sort = Nested(SortSchema, many=True, load_default=lambda: [])
    groups = fields.List(
        fields.String,
        validate=validate.ContainsOnly(GROUPS.keys()),
        metadata={
            'description': format_documentation_possibilities('groups', GROUPS.keys())
        },
    )
    fields_ = fields.List(
        fields.String,
        load_default=lambda: FIELDS,
        validate=[validate.ContainsOnly(FIELDS), validate.Length(min=1)],
        data_key='fields',
        metadata={
            'description': 'By default all fields are returned. {}'.format(
                format_documentation_possibilities('fields', FIELDS)
            )
        },
    )
    columnMetadata = fields.Dict(
        keys=fields.Str(),
        values=Nested(ColumnMetadata),
        load_default=dict,
        metadata={'description': METADATA_DESCRIPTION},
    )

    @validates_schema
    def validate_sort(self, data, **kwargs):
        if 'sort' in data:
            requested_keys = data.get('groups', []) + data.get('fields_', [])
            if not all([s['field'] in requested_keys for s in data['sort']]):
                raise ValidationError(
                    'Cannot sort by fields that are not requested in "fields" or '
                    '"groups".',
                    'sort',
                )

    @post_load
    def add_field_dependencies(self, data, **kwargs):
        """
        Add dependencies for average fields to the fields to be calculated, and keep
        track of which fields were added, so they can be left out in the projection
        stage.
        """
        data['added_dependencies'] = []
        for key, value in FIELD_DEPENDENCIES.items():
            if key in data['fields_']:
                for dependency in value:
                    if dependency not in data['fields_']:
                        data['fields_'].append(dependency)
                        data['added_dependencies'].append(dependency)
        return data

    @staticmethod
    def build_query(data):
        """
        Build a query with the following stages:
        Match:      the filter
        Add fields: add calulated fields that are more than just sums and need to be
                    done on the receipt level, in two stages.
        Group:      group on the groups provided and sum all other fields, includes a
                    project to calculate average fields and get rid of _id
        Sort:       sort
        Project:    change the datastructure to {'data': [], 'totals': {}}. If any
                    grouping was done, this includes a group stage for the totals
        """
        # turnover needs to be calculated before we can filter:
        turnover_filter = data['filter'].pop('turnover', None)

        def reduce_quantities(key):
            """
            return an add statement for items sold, returned, an and overall
            total to be used in the reduce statement for return and sale
            quantities.

            results in the following fields:
            {
                'qty': 4,
                'sold': 10,
                'returned': -6,
            }
            """
            operator = {'returned': '$lt', 'sold': '$gt', 'netQty': '$ne'}

            return {
                '$add': [
                    f'$$value.{key}',
                    {
                        '$cond': [
                            {
                                '$and': [
                                    {'$eq': ['$$this.category', 'barcode']},
                                    {operator[key]: ['$$this.qty', 0]},
                                ]
                            },
                            '$$this.qty',
                            0,
                        ]
                    },
                ]
            }

        # MATCH AND ADD FIELDS
        pipeline = [
            {'$match': data['filter']},
            {
                '$addFields': {
                    'qty': {
                        '$reduce': {
                            'input': '$receipt',
                            'initialValue': {'sold': 0, 'returned': 0, 'netQty': 0},
                            'in': {
                                'returned': reduce_quantities('returned'),
                                'sold': reduce_quantities('sold'),
                                'netQty': reduce_quantities('netQty'),
                            },
                        }
                    },
                    'totalAmount_': {
                        '$subtract': [
                            {'$subtract': ['$totalAmount', '$overallReceiptDiscount']},
                            '$totalDiscountCoupon',
                        ]
                    },
                    'cash': {'$subtract': ['$payments.cash', '$change']},
                    'withdrawal': {
                        '$cond': [
                            {'$gt': ['$payments.withdrawel', 0]},
                            '$payments.withdrawel',
                            0,
                        ]
                    },
                    'deposit': {
                        '$cond': [
                            {'$lt': ['$payments.withdrawel', 0]},
                            {'$abs': '$payments.withdrawel'},
                            0,
                        ]
                    },
                    'turnover': TURNOVER_CALCULATION,
                }
            },
            {
                '$addFields': {
                    'numberOfItemSales': {
                        '$cond': {
                            'if': {'$or': ['$qty.returned', '$qty.sold']},
                            'then': 1,
                            'else': 0,
                        }
                    }
                }
            },
        ]

        if turnover_filter:
            pipeline.append({'$match': {'turnover': turnover_filter}})

        # GROUP
        # sum all fields
        group = {
            '$group': {
                k: v
                for k, v in {
                    'storeCreditPaid': {'$sum': '$totalStoreCreditPaid'},
                    'turnover': {
                        '$sum': {'$subtract': ['$turnover', '$couponTotals.A']}
                    },
                    'cash': {'$sum': '$cash'},
                    'numberOfSales': {'$sum': 1},
                    'creditcard': {'$sum': '$payments.creditcard'},
                    'creditreceipt': {'$sum': '$payments.creditreceipt'},
                    'pin': {'$sum': '$payments.pin'},
                    'storeCredit': {'$sum': '$payments.storecredit'},
                    'totalAmount': {'$sum': '$totalAmount_'},
                    'vatHigh': {'$sum': '$vat.highamount'},
                    'vatLow': {'$sum': '$vat.lowamount'},
                    'withdrawal': {'$sum': '$withdrawal'},
                    'deposit': {'$sum': '$deposit'},
                    'netQty': {'$sum': '$qty.netQty'},
                    'qtySold': {'$sum': '$qty.sold'},
                    'qtyReturned': {'$sum': '$qty.returned'},
                    'numberOfItemSales': {'$sum': '$numberOfItemSales'},
                    'totalDiscountCoupon': {'$sum': '$couponTotals. '},
                    'totalCashBackCoupon': {'$sum': '$couponTotals.C'},
                    'totalGiftVoucherInactive': {
                        '$sum': {'$multiply': ['$couponTotals.I', -1]}
                    },
                    'totalGiftVoucherActive': {'$sum': '$couponTotals.U'},
                    'totalCreditReceipt': {'$sum': '$couponTotals.T'},
                    'totalCouponAsArticle': {'$sum': '$couponTotals.A'},
                }.items()
                if k in data['fields_']
            }
        }
        # keep track of keys we sum
        summed = [k for k in group['$group']]
        # construct _id for group
        groups = {}
        for key in data.get('groups', []):
            definition = GROUPS[key]
            if isinstance(definition, str):
                definition = '$' + definition
            groups[key] = definition
        group['$group']['_id'] = groups

        averages = {
            key: value for key, value in AVERAGES.items() if key in data['fields_']
        }

        pipeline.extend(
            [
                group,
                {
                    '$project': {
                        '_id': 0,
                        **{k: '$_id.' + k for k in groups},
                        **{k: '$' + k for k in summed},
                        **averages,
                    }
                },
            ]
        )

        # SORT
        if data.get('sort'):
            pipeline.append(
                {'$sort': {s['field']: s['direction'] for s in data['sort']}}
            )

        # PROJECT
        data_fields = {
            **{key: f'${key}' for key in groups},
            **{
                key: f'${key}'
                for key in summed
                if key not in data['added_dependencies']
            },
            **{key: f'${key}' for key in averages},
        }
        if groups:
            # if we group then we put the data in a nested key and calculate the
            # totals for all the numerical fields.

            # resulting in
            # {
            #     'data': [
            #         {'pin': 5, 'shopId': 1},
            #         {'pin': 1, 'shopId': 2},
            #     ],
            #     'pin': 6,
            # }
            pipeline.append(
                {
                    '$group': {
                        '_id': 0,
                        'data': {'$push': data_fields},
                        **{key: {'$sum': f'${key}'} for key in summed},
                    }
                }
            )

            projection = {'data': '$data'}
        else:
            # {
            #     'data': [
            #       {'pin': 5, 'cash': 1},
            #     ],
            # }
            projection = {'data': [data_fields]}  # does not contain any groups

        projection.update(
            {
                '_id': 0,
                'totals': {
                    # non numerical fields are not shown in the totals
                    # data structure but are set to make the structure the same
                    # as the regular entries in 'data'.
                    # resulting in
                    # {
                    #     'data': [
                    #         {'pin': 5, 'shopId': 1},
                    #         {'pin': 1, 'shopId': 2},
                    #     ],
                    #     'totals': {
                    #         'shopId': '',
                    #         'pin': 6,
                    #     }
                    # }
                    **{key: '' for key in groups},
                    **{
                        key: f'${key}'
                        for key in summed
                        if key not in data['added_dependencies']
                    },
                    **averages,
                },
            }
        )
        pipeline.append({'$project': projection})

        if data.get('limit'):
            pipeline.extend([{'$skip': data['skip']}, {'$limit': data['limit']}])

        return pipeline


def journal(request, format):
    data = Journal(context={'tenant_id': request.requested_tenant_id}).load(
        request.json_payload
    )
    query = Journal.build_query(data)
    try:
        result = list(
            request.db.transactions.aggregate(query, hint='tenant_id_1_created.date_-1')
        )[0]
    except IndexError:
        result = {'data': [], 'totals': {}}

    if format == 'json':
        return result

    # for the downloadable reports add the totals as the last row.
    result['data'].append(result['totals'])
    result = flatten_result(result['data'])
    header = export_header(result, data.get('groups', []) + data.get('fields_', []))

    if format == 'excel':
        temp_file = export_excel(header, result, data['columnMetadata'])
        return serve_excel_response(request.response, temp_file, 'journal.xlsx')
    elif format == 'csv':
        temp_file = export_csv(header, result)
        return serve_csv_response(request.response, temp_file)


class JournalResponseDocumentation(Schema):
    data = Nested(
        GroupsAndFieldsDocumentation,
        many=True,
        metadata={'description': 'Only the selected groups and fields are shown.'},
    )
    totals = Nested(
        GroupsAndFieldsDocumentation,
        many=True,
        metadata={
            'description': 'Totals are only shown if at least one group is selected.'
        },
    )


def journal_json(ctx, request):
    """
    Get the sales journal

    ---
    post:
      description: >
        Get the sales journal.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'journal.json#/definitions/Journal'
      produces:
        - application/json
      responses:
        200:
          description: Daily journal
          schema:
            $ref: 'journal_response.json#/definitions/JournalResponseDocumentation'
      tags:
        - data
        - reporting
    """
    return journal(request, 'json')


def journal_csv(ctx, request):
    """
    Get the sales journal

    ---
    post:
      description: >
        Get the sales journal.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'journal.json#/definitions/Journal'
      produces:
        - text/csv
      responses:
        200:
          description: The report in csv format.
      tags:
        - data
        - reporting
    """
    return journal(request, 'csv')


def journal_excel(ctx, request):
    """
    Get the sales journal

    ---
    post:
      description: >
        Get the sales journal.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'journal.json#/definitions/Journal'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The report as an excel file.
          schema:
            type: file
      tags:
        - data
        - reporting
    """
    return journal(request, 'excel')


class JournalFilterQueryFilter(Schema):
    startDate = fields.DateTime()
    endDate = fields.DateTime()

    @post_load
    def postprocess(self, data, **kwargs):
        data.update({'tenant_id': self.context['tenant_id'], 'active': True})
        data['type'] = 2

        # Restrict to a year based on a setting for tenants with many transactions:
        if 'startDate' not in data:
            settings = (
                self.context['db']
                .tenants.find_one({'_id': self.context['tenant_id']}, {'settings': 1})
                .get('settings')
                or {}
            )
            # This is a temporary setting that is not available in the settings schema
            # and will need to be added in the database directly.
            if settings.get('limit_journal_filter_timeframe'):
                now = datetime.datetime.utcnow()
                data['startDate'] = datetime.datetime(
                    now.year, now.month, now.day
                ) - datetime.timedelta(days=365)

        if 'startDate' not in data:
            one_year_ago = datetime.datetime.now() - datetime.timedelta(days=365)
            data['startDate'] = one_year_ago
        for field, operator in [('startDate', '$gte'), ('endDate', '$lte')]:
            if field in data:
                if 'created.date' not in data:
                    data['created.date'] = {}
                data['created.date'][operator] = data.pop(field)
        return data


class JournalFilterQuery(Schema):
    filter = Nested(JournalFilterQueryFilter, load_default=dict)


def get_journal_filters(ctx, request):
    """
    Return fields, groups and possible filter values.

    ---
    post:
      tags:
        - reporting
      description: >
        In order to know with what data to populate the front-end UI for
        filtering the tenant's shifts, return fields, groups and possible
        filter values.

        ### Response

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | ok or error\n
        data      | dict   | the filters, groups, columns\n
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'journal_filter.json#/definitions/JournalFilterQuery'
    """
    data = JournalFilterQuery(
        context={'tenant_id': request.requested_tenant_id, 'db': request.db}
    ).load(request.json_payload)

    calendar_groups = ['day', 'month', 'week', 'year', 'dow']
    project = {
        key: f'${value}'
        for key, value in GROUPS_FILTER.items()
        if key not in ['discountReason', *calendar_groups]
    }
    group = {
        key: {'$addToSet': f'${key}'}
        for key in GROUPS_FILTER
        if key not in calendar_groups
    }

    pipeline = [
        {'$match': data['filter']},
        {
            '$project': {
                '_id': 0,
                'discountReason': {
                    '$cond': {
                        'if': {'$eq': [{'$type': '$discountreason'}, 'string']},
                        'then': '$discountreason',
                        'else': '$discountreason.desc',
                    }
                },
                **project,
            }
        },
        {'$group': {'_id': 0, **group}},
        {'$project': {'_id': 0}},
    ]

    def sorter(i):
        """
        sorts everything based on its string value. If the value is falsy sort it
        as if it's an empty string.
        """
        if not i:
            return ''
        elif not isinstance(i, str):
            return str(i)
        return i

    result = request.db.transactions.aggregate(
        pipeline, hint='tenant_id_1_created.date_-1'
    )
    try:
        filters = {k: sorted(v, key=sorter) for k, v in next(result).items()}
    except StopIteration:
        filters = {}

    filters['paymentMethod'] = PAYMENT_METHODS
    return {
        'data': {'filter': filters, 'fields': FIELDS, 'groups': list(GROUPS_FILTER)}
    }
