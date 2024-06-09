"""
Endpoints which run reporting queries for sales data.

(transactions with type 2)
"""

from datetime import datetime, timedelta

from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    post_load,
    validate,
    validates_schema,
)

from spynl_schemas.utils import BAD_CHOICE_MSG

from spynl.locale import SpynlTranslationString as _

from spynl.main.dateutils import localize_date, now
from spynl.main.exceptions import IllegalAction, IllegalParameter
from spynl.main.serial.file_responses import (
    export_csv,
    export_excel,
    serve_csv_response,
    serve_excel_response,
)
from spynl.main.utils import required_args

from spynl.api.mongo.exceptions import CannotFindLinkedData
from spynl.api.mongo.serial_objects import decode_date
from spynl.api.retail.exceptions import IllegalPeriod
from spynl.api.retail.utils import check_warehouse, prepare_for_export, round_results

# totalAmount - overallReceiptDiscount - couponTotals.C - couponTotals.SPACE
# - totalStoreCreditPaid
TURNOVER_CALCULATION = {
    '$subtract': [
        {
            '$subtract': [
                {
                    '$subtract': [
                        {
                            '$subtract': [
                                {'$ifNull': ['$totalAmount', 0]},
                                {'$ifNull': ['$overallReceiptDiscount', 0]},
                            ]
                        },
                        {'$ifNull': ['$couponTotals.C', 0]},
                    ]
                },
                {'$ifNull': ['$couponTotals. ', 0]},
            ],
        },
        {'$ifNull': ['$totalStoreCreditPaid', 0]},
    ]
}


def get_start_end_dates(data):
    """Decode and check date range from the data"""
    if 'startDate' not in data:
        data['startDate'] = now() - timedelta(hours=48)
    else:
        decode_date(data, 'startDate', None)
    if 'endDate' not in data:
        data['endDate'] = now()
    else:
        decode_date(data, 'endDate', None)

    start, end = data['startDate'], data['endDate']

    if end < start:
        raise IllegalPeriod(_('illegal-period-end-over-start'))

    return start, end


def get_warehouse_id(user_wh, requested_wh):
    if user_wh:
        warehouse_id = user_wh
        if requested_wh and warehouse_id != requested_wh:
            msg = _('illegal-warehouse')
            dev_msg = {'user.wh': user_wh, 'request.args.warehouseId': requested_wh}
            raise IllegalAction(msg, developer_message=dev_msg)

    else:
        warehouse_id = requested_wh
    return warehouse_id


def period(ctx, request):
    start_date, end_date = get_start_end_dates(request.args)
    match = {
        'tenant_id': request.requested_tenant_id,
        'created.date': {'$gte': start_date, '$lte': end_date},
        'type': 2,
        'active': True,
    }

    warehouse_id = get_warehouse_id(
        request.cached_user.get('wh'), request.args.get('warehouseId')
    )

    if warehouse_id:
        check_warehouse(request.db, warehouse_id)
        match['shop.id'] = warehouse_id

    group_by = request.args.get('group_by')
    if group_by:
        keys = ('minute', 'hour', 'day', 'month', 'year')
        if group_by not in keys:
            raise IllegalParameter(
                _('invalid-group_by-parameter', mapping={'values': ', '.join(keys)})
            )
    else:
        if end_date - start_date > timedelta(days=365):
            group_by = 'month'
        elif end_date - start_date > timedelta(days=30):
            group_by = 'day'
        elif end_date - start_date > timedelta(days=1):
            group_by = 'hour'
        else:
            group_by = 'minute'
    if group_by == 'minute':
        max_days_on_minute_scale = 7
        if start_date < end_date - timedelta(days=max_days_on_minute_scale):
            raise IllegalAction(
                _('minute-group_by', mapping={'days': max_days_on_minute_scale})
            )

    group_id = {'year': {'$year': '$created.date'}}
    if group_by in ('minute', 'hour', 'day', 'month'):
        group_id['month'] = {'$month': '$created.date'}
    if group_by in ('minute', 'hour', 'day'):
        group_id['day'] = {'$dayOfMonth': '$created.date'}
    if group_by in ('minute', 'hour'):
        group_id['hour'] = {'$hour': '$created.date'}
    if group_by in ('minute'):
        group_id['minute'] = {'$minute': '$created.date'}

    filtr = [
        {'$match': match},
        {'$group': {'_id': group_id, 'turnover': {'$sum': TURNOVER_CALCULATION}}},
        {'$project': {'_id': 0, 'date': '$_id', 'turnover': '$turnover'}},
    ]
    result = list(request.db[ctx].aggregate(filtr))
    return result


def period_json(ctx, request):
    """
    Sales for a period, for one or all warehouses.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | | period start Date,
        default is 48 hours ago\n
        endDate   | ISO 8601 Date string | | period end date, default is now\n
        warehouseId   | string    | | ID of the warehouse (warehouses.wh)\n
        group_by  | string         | | "minute", "hour", "day", "month"
        or "year". If using "minute", the period cannot be longer than 7 days.
        If group_by is not given, the most sensible grouping is chosen by the
        length of the period: default value is 'hour' if endDate -
        startDate > 1 day, 'day' if endDate - startDate > 1 month,
        month' if endDate - startDate > 1 year.\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
        data         | list   | The result of the MongoDB aggregation,
        one row per affected time interval in the period.
        **date** contains the time interval information in this form:
        {timescale:value}. Example: {"year": 2015, "month": 11, "day": 2}.
        **turnover**
        **grouped_by** is what was used for grouping
        (see group_by parameter).\n
        limit        | int    | if not set by the filter the limit is set to
        the maximum limit to protect Spynl\n

      tags:
        - reporting
    """
    response = {}
    result = period(ctx, request)
    if result:
        if 'hour' in result[0]['date']:
            # if these fields are in the response, localise (also see SWPY-798)
            for row in result:
                localized_date = localize_date(datetime(**row['date']))
                row['date'] = {k: getattr(localized_date, k) for k in row['date']}

        for g in ['minute', 'hour', 'day', 'month', 'year']:
            if g in result[0]['date']:
                response['grouped_by'] = g
                break

    response['data'] = result
    return response


def period_csv(ctx, request):
    """
    Sales for a period, for one or all warehouses.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | | period start Date,
        default is 48 hours ago\n
        endDate   | ISO 8601 Date string | | period end date, default is now\n
        warehouseId   | string    | | ID of the warehouse (warehouses.wh)\n
        group_by  | string         | | "minute", "hour", "day", "month"
        or "year". If using "minute", the period cannot be longer than 7 days.
        If group_by is not given, the most sensible grouping is chosen by the
        length of the period: default value is 'hour' if endDate -
        startDate > 1 day, 'day' if endDate - startDate > 1 month,
        month' if endDate - startDate > 1 year.\n

        ### Response

        CSV output of report

      tags:
        - reporting
    """
    data, header = prepare_for_export(period(ctx, request))
    temp_file = export_csv(header, data)
    return serve_csv_response(request.response, temp_file)


def period_excel(ctx, request):
    """
    Sales for a period, for one or all warehouses.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | | period start Date,
        default is 48 hours ago\n
        endDate   | ISO 8601 Date string | | period end date, default is now\n
        warehouseId   | string    | | ID of the warehouse (warehouses.wh)\n
        group_by  | string         | | "minute", "hour", "day", "month"
        or "year". If using "minute", the period cannot be longer than 7 days.
        If group_by is not given, the most sensible grouping is chosen by the
        length of the period: default value is 'hour' if endDate -
        startDate > 1 day, 'day' if endDate - startDate > 1 month,
        month' if endDate - startDate > 1 year.\n

        ### Response

        Excel file of report.


      tags:
        - reporting
    """
    data, header = prepare_for_export(period(ctx, request))
    temp_file = export_excel(header, data)
    return serve_excel_response(request.response, temp_file, 'period.xlsx')


@required_args('startDate', 'endDate')
def summary(ctx, request):
    """
    Sales summary for a period, for one or all warehouses.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | &#10004; | period start Date\n
        endDate   | ISO 8601 Date string | &#10004; | period end date\n
        warehouseId   | string    | | ID of a warehouse (warehouses.wh)\n
        device | string | | _id of device user\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
        data         | dict   | The result of the MongoDB aggregation.
        **transactions** is the number of transactions in the period. consignment
        transactions are not counted. Unit value.
        **items**/**returns** are the number of overall bought/returned items.
        Unit value.
        **itemsPer** is the average number of items (per transaction that has
        actual items). Unit value.
        **nettItemsPer** is the average (items - returns) (per transaction that has
        actual items). Unit value.
        **itemTransactions** is the number of transactions that have actual
        items, so excluding withdrawals etc. Unit value.
        **turnover**  Currency value.
        **totalDiscount** sum of KC, K and receipt and product discount. Currency value.
        **withdrawal** is the sum of all withdrawal (positive number for cash
        taken out). Currency value.
        **totalPer** is the average turnover (per transaction that has actual
        items). Unit value.
        **consignment** the price of items given into consignment. Taken from
        payments.consignment. Currency value.
        **consignmentItems** is the number of items given into consignment. Returns are
        not taken into account. Unit value.\n
        limit        | int    | if not set by the filter the limit is set to
        the maximum limit to protect Spynl\n

      tags:
        - reporting
    """
    start_date, end_date = get_start_end_dates(request.args)
    match = {
        'tenant_id': request.requested_tenant_id,
        'created.date': {'$gte': start_date, '$lte': end_date},
        'type': {'$in': [2, 9]},
        'active': True,
    }
    if request.args.get('device'):
        match['device'] = request.args.get('device')
    else:
        warehouse_id = get_warehouse_id(
            request.cached_user.get('wh'), request.args.get('warehouseId')
        )

        if warehouse_id:
            check_warehouse(request.db, warehouse_id)
            match['shop.id'] = warehouse_id

    def coupon_condition(type_):
        return {
            '$and': [
                {'$eq': ['$receipt.type', type_]},
                {'$eq': ['$receipt.category', 'coupon']},
            ]
        }

    item_condition = {
        '$and': [
            {'$gt': ['$receipt.qty', 0]},
            {'$eq': ['$receipt.category', 'barcode']},
            {'$eq': ['$type', 2]},
        ]
    }

    return_condition = {
        '$and': [
            {'$lt': ['$receipt.qty', 0]},
            {'$eq': ['$receipt.category', 'barcode']},
            {'$eq': ['$type', 2]},
        ]
    }

    filtr = [
        {'$match': match},
        {
            '$project': {
                'receipt': 1,
                'type': 1,
                'payments': 1,
                'totalDiscount': {
                    '$sum': [
                        '$overallReceiptDiscount',
                        '$couponTotals. ',
                        '$couponTotals.C',
                    ]
                },
                'overallReceiptDiscount': 1,
                'turnover': {
                    '$cond': {
                        'if': {'$eq': ['$type', 2]},
                        'then': TURNOVER_CALCULATION,
                        'else': 0,
                    }
                },
                '_id': 1,
                'transaction': {
                    '$cond': {'if': {'$eq': ['$type', 2]}, 'then': 1, 'else': 0}
                },
            }
        },
        {'$unwind': {'path': '$receipt', 'preserveNullAndEmptyArrays': True}},
        {
            '$project': {
                '_id': 1,
                'KA': {
                    '$cond': {
                        'if': coupon_condition('A'),
                        'then': '$receipt.price',
                        'else': 0,
                    }
                },
                'KU': {
                    '$cond': {
                        'if': coupon_condition('U'),
                        'then': '$receipt.price',
                        'else': 0,
                    }
                },
                'KC': {
                    '$cond': {
                        'if': coupon_condition('C'),
                        'then': '$receipt.value',
                        'else': 0,
                    }
                },
                'K': {
                    '$cond': {
                        'if': coupon_condition(' '),
                        'then': '$receipt.value',
                        'else': 0,
                    }
                },
                'productDiscount': {
                    '$cond': {
                        'if': item_condition,
                        'then': {
                            '$subtract': [
                                {'$ifNull': ['$receipt.nettPrice', 0]},
                                {'$ifNull': ['$receipt.price', 0]},
                            ]
                        },
                        'else': 0,
                    }
                },
                'items': {
                    '$cond': {'if': item_condition, 'then': '$receipt.qty', 'else': 0}
                },
                'returns': {
                    '$cond': {'if': return_condition, 'then': '$receipt.qty', 'else': 0}
                },
                'item_transaction': {
                    '$cond': {
                        'if': {'$or': [item_condition, return_condition]},
                        'then': 1,
                        'else': 0,
                    }
                },
                'consignmentItems': {
                    '$cond': {
                        'if': {
                            '$and': [
                                {'$gt': ['$receipt.qty', 0]},
                                {'$eq': ['$receipt.category', 'barcode']},
                                {'$eq': ['$type', 9]},
                            ]
                        },
                        'then': '$receipt.qty',
                        'else': 0,
                    }
                },
                'payments': 1,
                'totalDiscount': 1,
                'overallReceiptDiscount': 1,
                'turnover': 1,
                'transaction': 1,
            }
        },
        {
            '$group': {
                '_id': '$_id',
                'KA': {'$sum': '$KA'},
                'KU': {'$sum': '$KU'},
                'KC': {'$sum': '$KC'},
                'K': {'$sum': '$K'},
                'productDiscount': {'$sum': '$productDiscount'},
                'items': {'$sum': '$items'},
                'returns': {'$sum': '$returns'},
                'itemTransactions': {'$max': '$item_transaction'},
                'withdrawal': {'$avg': '$payments.withdrawel'},
                'cash': {'$avg': '$payments.cash'},
                'consignment': {'$avg': '$payments.consignment'},
                'consignmentItems': {'$sum': '$consignmentItems'},
                'turnover': {'$avg': '$turnover'},
                'totalDiscount': {'$avg': '$totalDiscount'},
                'overallReceiptDiscount': {'$avg': '$overallReceiptDiscount'},
                'transaction': {'$avg': '$transaction'},
            }
        },
        {
            '$group': {
                'transactions': {'$sum': '$transaction'},
                'overallReceiptDiscount': {'$sum': '$overallReceiptDiscount'},
                'items': {'$sum': '$items'},
                'itemTransactions': {'$sum': '$itemTransactions'},
                'returns': {'$sum': '$returns'},
                'withdrawal': {'$sum': '$withdrawal'},
                'cash': {'$sum': '$cash'},
                'consignment': {'$sum': '$consignment'},
                'consignmentItems': {'$sum': '$consignmentItems'},
                'turnover': {'$sum': '$turnover'},
                'totalDiscount': {'$sum': '$totalDiscount'},
                'KA': {'$sum': '$KA'},
                'KU': {'$sum': '$KU'},
                'KC': {'$sum': '$KC'},
                'K': {'$sum': '$K'},
                'productDiscount': {'$sum': '$productDiscount'},
                '_id': None,
            }
        },
        {
            '$project': {
                'transactions': 1,
                'items': {'$sum': '$items'},
                'itemTransactions': 1,
                'overallReceiptDiscount': 1,
                'KA': {'$ifNull': ['$KA', 0]},
                'KU': {'$ifNull': ['$KU', 0]},
                'KC': {'$ifNull': ['$KC', 0]},
                'K': {'$ifNull': ['$K', 0]},
                'productDiscount': 1,
                'returns': {'$multiply': ['$returns', -1]},
                'withdrawal': 1,
                'cash': 1,
                'consignment': 1,
                'consignmentItems': 1,
                'itemsPer': {
                    '$cond': {
                        'if': {'$gt': ['$itemTransactions', 0]},
                        'then': {'$divide': ['$items', '$itemTransactions']},
                        'else': 0,
                    }
                },
                'turnover': {'$subtract': ['$turnover', '$KA']},
                'totalPer': {
                    '$cond': {
                        'if': {'$gt': ['$itemTransactions', 0]},
                        'then': {
                            '$divide': [
                                {'$subtract': ['$turnover', '$KA']},
                                '$itemTransactions',
                            ]
                        },
                        'else': 0,
                    }
                },
                'nettItemsPer': {
                    '$cond': {
                        'if': {'$gt': ['$itemTransactions', 0]},
                        'then': {
                            '$divide': [
                                {'$sum': ['$items', '$returns']},
                                '$itemTransactions',
                            ]
                        },
                        'else': 0,
                    }
                },
                'totalDiscount': {'$sum': ['$totalDiscount', '$productDiscount']},
            }
        },
    ]

    data = list(request.db[ctx].aggregate(filtr))
    if not data:
        data = dict(
            transactions=0,
            items=0,
            itemsPer=0,
            itemTransactions=0,
            totalPer=0,
            nettItemsPer=0,
            returns=0,
            turnover=0,
            withdrawal=0,
            consignmentItems=0,
            consignment=0,
            cash=0,
            KA=0,
            KU=0,
            KC=0,
            K=0,
            totalDiscount=0,
        )
    else:
        data = data[0]  # a list with one item is not useful :)]
    # calculate nettItems:
    data['nettItems'] = data['items'] - data['returns']
    return {'data': data}


def check_full_info_users(user, tenant_id):
    user_roles = user.get('roles', {}).get(tenant_id, {}).get('tenant', {})
    return 'dashboard-tenant_overview' not in user_roles


@required_args('startDate', 'endDate')
def per_warehouse(ctx, request):
    start_date, end_date = get_start_end_dates(request.args)
    match = {
        'type': 2,
        'tenant_id': request.requested_tenant_id,
        'created.date': {'$gte': start_date, '$lte': end_date},
        'active': True,
    }
    wh = request.cached_user.get('wh')
    if wh and check_full_info_users(request.cached_user, request.current_tenant_id):
        match.update({'shop.id': wh})
    filtr = [
        {'$match': match},
        {
            '$addFields': {
                'qty': {
                    '$reduce': {
                        'input': '$receipt',
                        'initialValue': 0,
                        'in': {
                            '$sum': [
                                "$$value",
                                {
                                    '$cond': {
                                        'if': {
                                            '$and': [
                                                {'$gt': ['$$this.qty', 0]},
                                                {'$eq': ['$$this.category', 'barcode']},
                                            ]
                                        },
                                        'then': '$$this.qty',
                                        'else': 0,
                                    }
                                },
                            ]
                        },
                    }
                },
                'KA': {
                    '$reduce': {
                        'input': '$receipt',
                        'initialValue': 0,
                        'in': {
                            '$sum': [
                                "$$value",
                                {
                                    '$cond': {
                                        'if': {
                                            '$and': [
                                                {'$eq': ['$$this.type', 'A']},
                                                {'$eq': ['$$this.category', 'coupon']},
                                            ]
                                        },
                                        'then': '$$this.price',
                                        'else': 0,
                                    }
                                },
                            ]
                        },
                    }
                },
            }
        },
        {
            '$group': {
                '_id': {'warehousename': '$shop.name', 'warehouseid': '$shop.id'},
                'qty': {'$sum': '$qty'},
                'KA': {'$sum': '$KA'},
                'turnover': {'$sum': TURNOVER_CALCULATION},
            }
        },
        {'$match': {'_id.warehousename': {'$exists': True}}},
        {
            '$project': {
                '_id': 0,
                'qty': '$qty',
                'warehouse': {'name': '$_id.warehousename', 'id': '$_id.warehouseid'},
                'turnover': {'$subtract': ['$turnover', '$KA']},
            }
        },
    ]
    result = list(request.db[ctx].aggregate(filtr))
    return result


def per_warehouse_json(ctx, request):
    """
    Sales per warehouse in a period.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | &#10004; | period start Date\n
        endDate   | ISO 8601 Date string | &#10004; | period end date\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n
        data         | list   | The result of the MongoDB aggregation.
        One dictionary per warehouse, where:
        **warehouse** contains information about the warehouse
        ("id" and "name").
        **turnover**
        limit        | int    | if not set by the filter the limit is set to
        the maximum limit to protect Spynl\n

      tags:
        - reporting
    """
    result = per_warehouse(ctx, request)
    return {'data': result}


def per_warehouse_csv(ctx, request):
    """
    Sales per warehouse in a period.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | &#10004; | period start Date\n
        endDate   | ISO 8601 Date string | &#10004; | period end date\n

        ### Response
        CSV output of report

      tags:
        - reporting
    """
    data, header = prepare_for_export(per_warehouse(ctx, request))
    temp_file = export_csv(header, data)
    return serve_csv_response(request.response, temp_file)


def per_warehouse_excel(ctx, request):
    """
    Sales per warehouse in a period.

    ---
    post:
      description: >

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        startDate | ISO 8601 Date string | &#10004; | period start Date\n
        endDate   | ISO 8601 Date string | &#10004; | period end date\n

        ### Response

        Excel file of report.

      tags:
        - reporting
    """
    data, header = prepare_for_export(per_warehouse(ctx, request))
    temp_file = export_excel(header, data)
    return serve_excel_response(request.response, temp_file, 'warehouse.xlsx')


class PerArticleSchema(Schema):
    startDate = fields.DateTime(required=True)
    endDate = fields.DateTime(required=True)
    warehouseId = fields.String(allow_none=True)
    category = fields.String(
        load_default='article',
        validate=validate.OneOf(
            choices=['article', 'brand', 'articleGroup', 'articleColorSize'],
            error=BAD_CHOICE_MSG,
        ),
        metadata={
            'description': 'Determines the grouping of the output. "article" groups '
            'on articlecode and articleDescription, "articleColorSize" extends that '
            'to include color and sizeLabel. "brand" only groups on brand, and '
            '"articleGroup" only groups on articleGroup.'
        },
    )

    @validates_schema
    def validate_daterange(self, data, **kwargs):
        if data['startDate'] >= data['endDate']:
            # raise IllegalPeriod for now, to not change behaviour
            raise IllegalPeriod(_('illegal-period-end-over-start'))

    @post_load
    def set_and_check_warehouse_id(self, data, **kwargs):
        """
        If a user has an associated warehouse, this is the only warehouse they
        are allowed to see. Set it if that is the case. If a warehouse is set,
        check if it exists.
        """
        data['warehouseId'] = get_warehouse_id(
            self.context.get('user_wh'), data.get('warehouseId')
        )
        if data['warehouseId'] and 'db' in self.context:
            check_warehouse(self.context['db'], data['warehouseId'])
        return data

    class Meta:
        unknown = EXCLUDE


@required_args('startDate', 'endDate')
def per_article(ctx, request):
    args = PerArticleSchema(
        context={'user_wh': request.cached_user.get('wh'), 'db': request.db}
    ).load(request.args)
    match = {
        'tenant_id': request.requested_tenant_id,
        'created.date': {'$gte': args['startDate'], '$lte': args['endDate']},
        'type': 2,
        'active': True,
        # receipt added here to optimize query per Prodyna recommendation:
        'receipt': {'$elemMatch': {'category': 'barcode', 'qty': {'$ne': 0}}},
    }

    _id = {
        'article': {
            'articleCode': '$receipt.articleCode',
            'articleDescription': '$receipt.articleDescription',
        },
        'articleColorSize': {
            'articleCode': '$receipt.articleCode',
            'articleDescription': '$receipt.articleDescription',
            'color': '$receipt.color',
            'sizeLabel': '$receipt.sizeLabel',
        },
        'brand': {'brand': '$receipt.brand'},
        'articleGroup': {'articleGroup': '$receipt.group'},
    }

    project = {
        'article': {
            'code': '$_id.articleCode',
            'description': '$_id.articleDescription',
        },
        'articleColorSize': {
            'code': '$_id.articleCode',
            'description': '$_id.articleDescription',
            'color': '$_id.color',
            'sizeLabel': '$_id.sizeLabel',
        },
        'brand': '$_id.brand',
        'articleGroup': '$_id.articleGroup',
    }

    if args.get('warehouseId'):
        match['shop.id'] = args['warehouseId']

    if request.args.get('device'):
        match['device'] = request.args.get('device')

    filtr = [
        {'$match': match},
        # added early project per Prodyna recommendation:
        {
            '$project': {
                '_id': 0,
                'receipt': {
                    '$filter': {
                        'input': '$receipt',
                        'cond': {
                            '$and': [
                                {'$eq': ['$$this.category', 'barcode']},
                                {'$ne': ['$$this.qty', 0]},
                            ]
                        },
                    }
                },
            }
        },
        {'$unwind': '$receipt'},
        {
            '$group': {
                '_id': _id[args['category']],
                'qty': {'$sum': '$receipt.qty'},
                'turnover': {'$sum': {'$multiply': ['$receipt.qty', '$receipt.price']}},
            }
        },
        {
            '$project': {
                '_id': 0,
                args['category']: project[args['category']],
                'qty': '$qty',
                'turnover': '$turnover',
            }
        },
    ]
    result = list(request.db[ctx].aggregate(filtr))
    round_results(result)
    return result


def per_article_json(ctx, request):
    """
    Sales per article in a period, for one or all warehouses.

    ---
    post:
      description: >

        This endpoint will give the sales per article for a given period.
        If you set the category parameter, you can instead also get the
        sales per brand or articleGroup

      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'per_article.json#/definitions/PerArticleSchema'
      produces:
        - application/json
      responses:
        200:
          description: Per article report
          schema:
            type: object
            properties:
              data:
                type: array
                items:
                  type: object
                description: array of objects that contain the rows of the report
      tags:
        - reporting
    """
    result = per_article(ctx, request)
    return {'data': result}


def per_article_csv(ctx, request):
    """
    Sales per article in a period, for one or all warehouses.

    ---
    post:
      description: >

        This endpoint will give the sales per article for a given period.
        If you set the category parameter, you can instead also get the
        sales per brand or articleGroup
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'per_article.json#/definitions/PerArticleSchema'
      produces:
        - text/csv
      responses:
        200:
          description: The report in csv format.
      tags:
        - reporting
    """
    data, header = prepare_for_export(per_article(ctx, request))
    temp_file = export_csv(header, data)
    return serve_csv_response(request.response, temp_file)


def per_article_excel(ctx, request):
    """
    Sales per article in a period, for one or all warehouses.

    ---
    post:
      description: >

        This endpoint will give the sales per article for a given period.
        If you set the category parameter, you can instead also get the
        sales per brand or articleGroup

      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'per_article.json#/definitions/PerArticleSchema'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The report as an excel file.
          schema:
            type: file
      tags:
        - reporting
    """
    data, header = prepare_for_export(per_article(ctx, request))
    temp_file = export_excel(header, data)
    return serve_excel_response(request.response, temp_file, 'article.xlsx')


class CustomerSalesSchema(Schema):
    """Schema for sold_barcodes_per_customer"""

    customerId = fields.UUID(
        required=True,
        metadata={
            'description': 'The uuid of the customer you want to see the sales of.'
        },
    )
    startDate = fields.DateTime(
        load_default=lambda: datetime.utcnow() - timedelta(days=7),
        metadata={'description': 'Start date.'},
    )
    endDate = fields.DateTime(
        load_default=datetime.utcnow, metadata={'description': 'End date.'}
    )

    @validates_schema
    def validate_daterange(self, data, **kwargs):
        if data['startDate'] >= data['endDate']:
            raise ValidationError('startDate should be before endDate')

    class Meta:
        ordered = True
        unknown = EXCLUDE


def sold_barcodes_per_customer(ctx, request):
    """
    Return barcodes sold since a given date for a given customer.

    ---
    post:
      description: >
        Return the articles bought by a specific customer in a specific period.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'sales_per_barcode.json#/definitions/CustomerSalesSchema'
      responses:
        "200":
          schema:
            type: object
            properties:
              data:
                type: array
                items:
                  type: object
                  $ref: 'sales_per_barcode_response.json#/definitions/\
CustomerSalesResponse'
              status:
                type: string
      tags:
        - reporting
    """
    args = CustomerSalesSchema().load(request.json_payload)
    customer_id = args['customerId']
    if not request.db.customers.find_one(
        {'_id': customer_id, 'tenant_id': {'$in': [request.requested_tenant_id]}}
    ):
        raise CannotFindLinkedData(customer_id)

    start_date, end_date = args['startDate'], args['endDate']

    pipeline = [
        {
            '$match': {
                'tenant_id': request.requested_tenant_id,
                'customer.id': str(customer_id),
                'type': 2,
                'active': True,
                'created.date': {'$gte': start_date, '$lte': end_date},
            }
        },
        {'$unwind': '$receipt'},
        {'$match': {'receipt.category': 'barcode'}},
        {'$sort': {'created.date': -1}},
        {
            '$project': {
                '_id': 0,
                'price': '$receipt.price',
                'category': '$receipt.category',
                'nettPrice': '$receipt.nettPrice',
                'articleCode': '$receipt.articleCode',
                'articleDescription': '$receipt.articleDescription',
                'brand': '$receipt.brand',
                'barcode': '$receipt.barcode',
                'color': '$receipt.color',
                'qty': '$receipt.qty',
                'sizeLabel': '$receipt.sizeLabel',
                'vat': '$receipt.vat',
                'date': '$created.date',
            }
        },
    ]

    response = list(request.db[ctx].aggregate(pipeline))
    return {'data': response}


class CustomerSalesResponse(Schema):
    """Only used for documenation"""

    articleCode = fields.String(metadata={'description': 'Article code.'})
    articleDescription = fields.String(metadata={'description': 'Article description.'})
    barcode = fields.String(metadata={'description': 'Barcode'})
    category = fields.String(metadata={'description': 'Article category.'})
    color = fields.String(metadata={'description': 'Color of the article.'})
    nettPrice = fields.Float()
    price = fields.Float()
    qty = fields.Integer()
    sizeLabel = fields.String()
    vat = fields.Float()
    date = fields.DateTime()

    class Meta:
        ordered = True
