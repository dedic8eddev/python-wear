from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    post_load,
    validate,
    validates_schema,
)

from spynl_schemas import Nested, ObjectIdField

from spynl.main.serial.file_responses import (
    export_csv,
    export_excel,
    serve_csv_response,
    serve_excel_response,
)

from spynl.api.retail.utils import SortSchema, prepare_for_export

UNKNOWN_CARDTYPE = 'unknown'


AGGREGATED = ['storecredit', 'cash', 'creditcard', 'creditreceipt', 'couponin', 'pin']


GROUPS = ['user', 'location', 'device', 'dow', 'day', 'week', 'month', 'year']


class PaymentReportFilterSchema(Schema):
    """Filter schema for payment reports."""

    user = fields.List(ObjectIdField)
    location = fields.List(fields.String)
    device = fields.List(fields.String)
    startDate = fields.DateTime()
    endDate = fields.DateTime()

    @post_load
    def handle_tenant_id(self, data, **kwargs):
        if 'tenant_id' in self.context:
            data['tenant_id'] = {'$in': [self.context['tenant_id']]}
        return data

    @post_load
    def to_db_fields(self, data, **kwargs):
        """Convert schema fields to the corresponding ones in the database."""
        mappings = [
            ('user', 'created.user._id'),
            ('location', 'shop.name'),
            ('device', 'device.name'),
        ]
        for key, mapped_key in mappings:
            if key in data:
                data[mapped_key] = {'$in': data.pop(key, None)}
        return data

    @post_load
    def handle_date_range(self, data, **kwargs):
        created = {}

        for field, operator in [('startDate', '$gte'), ('endDate', '$lte')]:
            if field in data:
                created[operator] = data.pop(field)

        if created:
            data['created.date'] = created

        return data

    class Meta:
        unknown = EXCLUDE


class PaymentsReportSchema(Schema):
    """Schema for request to get payment reports."""

    fields_ = fields.List(
        fields.String,
        load_default=lambda: AGGREGATED,
        validate=[validate.ContainsOnly(AGGREGATED), validate.Length(min=1)],
        data_key='fields',
    )
    filter = Nested(PaymentReportFilterSchema, load_default=dict)
    groups = fields.List(
        fields.String, load_default=list, validate=validate.ContainsOnly(GROUPS)
    )
    sort = Nested(SortSchema, many=True, load_default=list)

    @validates_schema
    def validate_sort(self, data, **kwargs):
        if 'sort' in data:
            if not all(
                [s['field'] in data['groups'] + data['fields_'] for s in data['sort']]
            ):
                raise ValidationError(
                    'Cannot sort by fields that are not '
                    'requested in "fields" or "groups".',
                    'sort',
                )

    limit = fields.Integer(validate=validate.Range(min=0))
    skip = fields.Integer(validate=validate.Range(min=0))

    @staticmethod
    def build_groupby_id(data):
        date_formats = {
            'dow': '%w',
            'day': '%Y-%m-%d',
            'week': '%U',
            'month': '%m',
            'year': '%Y',
        }

        db_fields = {
            'user': 'created.user._id',
            'location': 'shop.name',
            'device': 'device.name',
        }
        _id = {}

        for group in data['groups']:
            if group in date_formats:
                _id[group] = {
                    '$dateToString': {
                        'date': '$created.date',
                        'format': date_formats[group],
                    }
                }
            else:
                _id[group] = '$' + db_fields[group]
        return _id

    @post_load
    def build_pipeline(self, data, **kwargs):
        # initial pipeline skeleton
        pipeline = [
            {'$match': data['filter']},
            {'$group': {'_id': {}}},
            {'$group': {'_id': {}}},
        ]

        group_1 = pipeline[1]['$group']
        group_2 = pipeline[2]['$group']

        # request aggregations
        for k in data['fields_']:
            group_1[k] = {'$sum': '$payments.' + k}
            group_2[k] = {'$sum': '$' + k}

            if k == 'pin':
                group_1['_id']['cardType'] = '$cardType'
                group_2[k] = {
                    '$push': {
                        'v': '$pin',
                        'k': {'$ifNull': ['$_id.cardType', UNKNOWN_CARDTYPE]},
                    }
                }

        # set group by
        _id = self.build_groupby_id({'groups': data['groups']})
        group_1['_id'].update(_id)
        group_2['_id'].update({k: '$_id.' + k for k in _id})

        if data.get('sort'):
            pipeline.append(
                {'$sort': {'_id.' + s['field']: s['direction'] for s in data['sort']}}
            )

        for key in ('limit', 'skip'):
            if data.get(key):
                pipeline.append({'$' + key: data[key]})

        pipeline.extend(
            [
                {
                    '$addFields': {
                        'pin-total': {
                            '$reduce': {
                                'input': '$pin',
                                'initialValue': 0,
                                'in': {'$sum': ['$$value', '$$this.v']},
                            }
                        },
                        'pin': {'$arrayToObject': '$pin'},
                        **{k: {'$ifNull': ['$_id.' + k, '']} for k in _id},
                    }
                },
                {'$project': {'_id': 0}},
            ]
        )

        return pipeline


def format_result(data):
    def _build_row(payment_type, value, row):
        return {
            **{k: row[k] for k in GROUPS if k in row},
            'paymentType': payment_type,
            'value': value,
        }

    output = []
    for row in data:
        for k, v in row.items():
            if k == 'pin' and isinstance(row[k], dict):
                for k_, v_ in row[k].items():
                    output.append(_build_row('pin-' + k_, v_, row))
            elif k not in GROUPS:
                output.append(_build_row(k, v, row))
            else:
                continue
    return output


def payment_report(ctx, request):
    schema = PaymentsReportSchema(context={'tenant_id': request.requested_tenant_id})
    pipeline = schema.load(request.json_payload)
    result = request.db.transactions.aggregate(pipeline)
    return format_result(result)


def payment_report_json(ctx, request):
    """
    Get the payment report

    ---
    post:
      description: >
        Get the payment report

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------
        filter    | object | | See table below for possible filter parameters.\n
        limit     | int    | | Limit the results to N items.\n
        skip      | int    | | Skip the first N items.\n
        groups    | array of strings | | A list of fields to group by
        sort      | object  | | An object with the fieldnames as keys, direction as
        value.\n

        ### # Filter

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n

        user | array | | list of user _ids.
        location | array | | list of shop names
        device | array | | list of device names
        startDate | string | | Filter transactions from a given date (created date)\n
        endDate   | string | | Filter transactions till a given date (created date)\n


        ### Response

        JSON output of report

      tags:
        - data
    """
    return {'data': payment_report(ctx, request)}


def payment_report_csv(ctx, request):
    """
    Get the payment report

    ---
    post:
      description: >
        Get the payment report

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        filter    | object | | See table below for possible filter parameters.\n
        limit     | int    | | Limit the results to N items.\n
        skip      | int    | | Skip the first N items.\n
        groups    | array of strings | | A list of fields to group by\n
        sort      | object  | | An object with the fieldnames as keys, direction as
        value.\n

        ### # Filter

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        user | array | | list of user _ids.\n
        location | array | | list of shop names\n
        device | array | | list of device names\n
        startDate | string | | Filter transactions from a given date (created date)\n
        endDate   | string | | Filter transactions till a given date (created date)\n


        ### Response

        CSV output of report

      tags:
        - data
    """
    data, header = prepare_for_export(payment_report(ctx, request))
    temp_file = export_csv(header, data)
    return serve_csv_response(request.response, temp_file)


def payment_report_excel(ctx, request):
    """
    Get the payment report

    ---
    post:
      description: >
        Get the payment report

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        filter    | object | | See table below for possible filter parameters.\n
        limit     | int    | | Limit the results to N items.\n
        skip      | int    | | Skip the first N items.\n
        groups    | array of strings | | A list of fields to group by\n
        sort      | object  | | An object with the fieldnames as keys, direction as
        value.\n

        ### # Filter

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        user | array | | list of user _ids.\n
        location | array | | list of shop names\n
        device | array | | list of device names\n
        startDate | string | | Filter transactions from a given date (created date)\n
        endDate   | string | | Filter transactions till a given date (created date)\n


        ### Response

        Excel output of report

      tags:
        - data
    """
    data, header = prepare_for_export(payment_report(ctx, request))
    temp_file = export_excel(header, data)
    return serve_excel_response(request.response, temp_file, 'payments.xlsx')


def get_payment_filters(ctx, request):
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
    """
    pipeline = [
        {'$match': {'tenant_id': {'$in': [request.requested_tenant_id]}}},
        {
            '$group': {
                '_id': 0,
                'location': {'$addToSet': '$shop.name'},
                'device': {'$addToSet': '$device.name'},
                'user': {'$addToSet': '$created.user._id'},
            }
        },
        {'$project': dict(_id=0)},
    ]

    result = {'fields': AGGREGATED, 'groups': list(GROUPS), 'filter': {}}

    try:
        filter = next(request.db.transactions.aggregate(pipeline))
        for k, v in filter.items():
            result['filter'][k] = sorted(v)
    except StopIteration:
        pass

    return dict(status='ok', data=result)
