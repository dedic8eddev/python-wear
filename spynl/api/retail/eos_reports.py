"""EOS(end of shift) endpoints."""

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
from spynl.api.retail.exceptions import NoDataToExport
from spynl.api.retail.utils import SortSchema, flatten_result

# should be list, so if defaulted fields are always in the same order
AGGREGATED = [
    'cash',
    'change',
    'couponin',
    'couponout',
    'creditreceiptin',
    'creditcard',
    'deposit',
    'pin',
    'consignment',
    'storecredit',
    'storecreditin',
    'withdrawel',
    'creditreceipt',
    'difference',
    'bankDeposit',
    'endBalance',
    'openingBalance',
    'turnover',
]

GROUPS = {
    'cashier',
    'location',
    'device',
    'dow',
    'day',
    'week',
    'month',
    'year',
    'shift',
    'periodStart',
    'periodEnd',
}


class EOSReportsFilterSchema(Schema):
    """Filter schema for eos reports."""

    cashier = fields.List(
        fields.String, metadata={'description': 'list of cashier names (fullname)'}
    )
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
            ('cashier', 'cashier.fullname'),
            ('location', 'shop.name'),
            ('device', 'device.name'),
        ]
        for key, mapped_key in mappings:
            if key in data:
                data[mapped_key] = {'$in': data.pop(key, None)}
        return data

    @post_load
    def handle_date_range(self, data, **kwargs):
        daterange = {}
        for field, operator in ('startDate', '$gte'), ('endDate', '$lte'):
            if field in data:
                daterange[operator] = data.pop(field)
        if daterange:
            data['periodEnd'] = daterange
        return data


class EOSReportsAggSchema(Schema):
    """Schema for request to get eos reports."""

    fields_ = fields.List(
        fields.String,
        load_default=lambda: AGGREGATED,
        validate=[validate.ContainsOnly(AGGREGATED), validate.Length(min=1)],
        data_key='fields',
        metadata={
            'description': format_documentation_possibilities('fields', AGGREGATED)
        },
    )
    filter = Nested(EOSReportsFilterSchema, load_default=dict)
    groups = fields.List(
        fields.String,
        load_default=list,
        validate=validate.ContainsOnly(GROUPS),
        metadata={'description': format_documentation_possibilities('groups', GROUPS)},
    )
    sort = Nested(SortSchema, many=True, load_default=lambda: [])

    columnMetadata = fields.Dict(
        keys=fields.Str(),
        values=Nested(ColumnMetadata),
        load_default=dict,
        metadata={'description': METADATA_DESCRIPTION},
    )

    @validates_schema
    def validate_sort(self, data, **kwargs):
        if 'sort' in data:
            if not all(
                [s['field'] in data['groups'] + data['fields_'] for s in data['sort']]
            ):
                raise ValidationError(
                    'Can not sort by fields that are not '
                    'requested in "fields" or "groups".',
                    'sort',
                )

    limit = fields.Integer(validate=validate.Range(min=0))
    skip = fields.Integer(validate=validate.Range(min=0))

    @staticmethod
    def make_groupby_id(data):
        date_formats = {
            'dow': '%w',
            'day': '%Y-%m-%d',
            'week': '%U',
            'month': '%m',
            'year': '%Y',
        }

        db_fields = {
            'cashier': 'cashier.fullname',
            'location': 'shop.name',
            'device': 'device.name',
            'shift': 'cycleID',
        }
        db_fields_reversed = {v: k for k, v in db_fields.items()}

        _id = {}

        for group in data['groups']:
            if group in date_formats:
                _id[group] = {
                    '$dateToString': {
                        'date': '$periodEnd',
                        'format': date_formats[group],
                    }
                }
            else:
                _id[group] = '$' + db_fields.get(group, group)

        # group by what is filtered by.
        for fieldname in data['filter']:
            try:
                _id[db_fields_reversed[fieldname]] = '$' + fieldname
                # add to groups for excel and csv header:
                data['groups'].append(db_fields_reversed[fieldname])
            except KeyError:
                continue

        return _id

    @staticmethod
    def build_query(data):
        pipeline = [{'$match': data['filter']}]

        for key in ('limit', 'skip'):
            if data.get(key):
                pipeline.append({'$' + key: data[key]})

        sums = dict(
            cash={'$sum': '$final.cash'},
            change={'$sum': '$final.change'},
            couponin={'$sum': '$final.couponin'},
            couponout={'$sum': '$final.couponout'},
            creditreceiptin={'$sum': '$final.creditreceiptin'},
            creditcard={'$sum': '$final.creditcard'},
            deposit={'$sum': '$final.deposit'},
            pin={'$sum': '$final.pin'},
            consignment={'$sum': '$final.consignment'},
            storecredit={'$sum': '$final.storecredit'},
            storecreditin={'$sum': '$final.storecreditin'},
            withdrawel={'$sum': '$final.withdrawel'},
            creditreceipt={'$sum': '$final.creditreceipt'},
            difference={'$sum': '$difference'},
            bankDeposit={'$sum': '$deposit'},
            endBalance={'$sum': '$endBalance'},
            openingBalance={'$sum': '$openingBalance'},
            turnover={'$sum': '$turnover'},
        )
        sums = {k: v for k, v in sums.items() if k in data['fields_']}

        group_by = EOSReportsAggSchema.make_groupby_id(data)

        pipeline.append({'$group': {'_id': group_by, **sums}})

        if data.get('sort'):

            def sort_key(key):
                return '_id.' + key if key not in AGGREGATED else key

            pipeline.append(
                {'$sort': {sort_key(s['field']): s['direction'] for s in data['sort']}}
            )

        projection = {}
        # if specific group by behavior is requested, then we also calculate
        # global sums.
        if group_by:
            pipeline.append(
                {
                    '$group': {
                        '_id': 0,
                        'data': {
                            '$push': {
                                **{key: '$_id.' + key for key in group_by},
                                **{key: '$' + key for key in sums.keys()},
                            }
                        },
                        **{key: {'$sum': '$' + key} for key in sums.keys()},
                    }
                }
            )

            projection.update(data='$data')
        else:
            projection.update(data=[{key: '$' + key for key in sums.keys()}])

        # along with grouped results, sum all of them under the key totals
        projection.update(
            {
                '_id': 0,
                'totals': {
                    **{key: "" for key in group_by},
                    **{key: '$' + key for key in sums.keys()},
                },
            }
        )
        pipeline.append({'$project': projection})

        return pipeline


def aggregate_eos(ctx, request, format):
    schema = EOSReportsAggSchema(context=dict(tenant_id=request.requested_tenant_id))
    data = schema.load(request.json_payload)
    query = schema.build_query(data)

    try:
        result = next(request.db.eos.aggregate(query))
    except StopIteration:
        result = {}

    if format == 'json':
        return result

    if not result:
        raise NoDataToExport

    result = result.get('data', {})
    result = flatten_result(result)
    header = export_header(result, data.get('groups', []) + data.get('fields_', []))

    if format == 'excel':
        temp_file = export_excel(
            header, result, data['columnMetadata'], request=request
        )
        return serve_excel_response(request.response, temp_file, 'eos.xlsx')
    elif format == 'csv':
        temp_file = export_csv(header, result)
        return serve_csv_response(request.response, temp_file)


def get_eos_filters(ctx, request):
    """
    Return all unique cashiers, devices and locations from tenant's shifts.

    ---
    post:
      tags:
        - reporting
      description: >
        In order to know with what data to populate the front-end UI for filtering
        the tenant's shifts, return all unique values for cashiers, devices and
        locations from each tenant's shift.
      responses:
        200:
          description: The article status report
          schema:
            type: object
            properties:
              fields:
                type: array
                items:
                  type: object
                description: possible fields
              groups:
                type: object
                description: possible groups
              filter:
                type: object
                description: possible filter values
    """
    pipeline = [
        {'$match': {'tenant_id': {'$in': [request.requested_tenant_id]}}},
        {
            '$group': dict(
                _id=None,
                device={'$addToSet': '$device.name'},
                cashier={'$addToSet': '$cashier.fullname'},
                location={'$addToSet': '$shop.name'},
            )
        },
        {'$project': dict(_id=0)},
    ]

    result = {'fields': AGGREGATED, 'groups': GROUPS, 'filter': {}}

    try:
        filter = next(request.db.eos.aggregate(pipeline))
        for k, v in filter.items():
            result['filter'][k] = sorted(v)
    except StopIteration:
        pass

    return dict(status='ok', data=result)


def aggregate_eos_json(ctx, request):
    """
    Return aggregated data for end of shifts.

    ---
    post:
      tags:
        - reporting
      description: >
        Calculate totals and group by the result for end of shifts.
        Totals object is added in the response in the key 'data' as 'totals'.
        If grouping by any of the allowed groups was requested, these results are added
        to the response inside the 'data' object with the name 'grouped' which is a list
        of objects. Results can be narrowed by start and end period. The default start
        period is the start of today and the end period is the time of the request.
        Results also can be filtered.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'aggregate_eos.json#/definitions/EOSReportsAggSchema'
      produces:
        - application/json
      responses:
        200:
          description: EOS report
          schema:
            type: object
            properties:
              data:
                type: array
                items:
                  type: object
                description: array of objects that contain the rows of the report
              totals:
                type: object
                description: object that contains the totals row.
    """
    return aggregate_eos(ctx, request, 'json')


def aggregate_eos_csv(ctx, request):
    """
    Return aggregated data for end of shifts.

    ---
    post:
      tags:
        - reporting
      description: >
        Calculate totals and group by the result for end of shifts.
        Totals object is added in the response in the key 'data' as 'totals'.
        If grouping by any of the allowed groups was requested, these results are added
        to the response inside the 'data' object with the name 'grouped' which is a list
        of objects. Results can be narrowed by start and end period. The default start
        period is the start of today and the end period is the time of the request.
        Results also can be filtered.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'aggregate_eos.json#/definitions/EOSReportsAggSchema'
      produces:
        - text/csv
      responses:
        200:
          description: The report in csv format.
    """
    return aggregate_eos(ctx, request, 'csv')


def aggregate_eos_excel(ctx, request):
    """
    Return aggregated data for end of shifts.

    ---
    post:
      tags:
        - reporting
      description: >
        Calculate totals and group by the result for end of shifts.
        Totals object is added in the response in the key 'data' as 'totals'.
        If grouping by any of the allowed groups was requested, these results are added
        to the response inside the 'data' object with the name 'grouped' which is a list
        of objects. Results can be narrowed by start and end period. The default start
        period is the start of today and the end period is the time of the request.
        Results also can be filtered.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'aggregate_eos.json#/definitions/EOSReportsAggSchema'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The report as an excel file.
          schema:
            type: file
    """
    return aggregate_eos(ctx, request, 'excel')
