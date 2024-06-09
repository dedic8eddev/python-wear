from collections import namedtuple

from marshmallow import (
    EXCLUDE,
    Schema,
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)

from spynl_schemas import Nested

from spynl.locale import SpynlTranslationString as _

from spynl.main.serial.file_responses import (
    METADATA_DESCRIPTION,
    ColumnMetadata,
    export_csv,
    export_header,
    make_pdf_file_response,
    serve_csv_response,
    serve_excel_response,
)

from spynl.api.retail.exceptions import NoDataToExport
from spynl.api.retail.utils import round_results

from spynl.services.pdf.pdf import generate_article_status_html_css, generate_pdf
from spynl.services.reports.utils import (
    CollectionSchema,
    debug_query,
    default_filter_values,
    generate_excel_report,
    prepare_filter_response,
    revert_back_to_camelcase,
)
from spynl.services.reports.wholesale_customer_query_builder import (
    build,
    build_filter_values,
)

Column = namedtuple('Column', ['column_name', 'alias', 'aggregated'])


COLUMNS = [
    # NON AGGREGATED COLUMNS
    Column('agent', 'agent', False),
    Column('ccountry', 'customerCountry', False),
    Column('article', 'articleCode', False),
    Column('brand', 'brand', False),
    Column('ccity', 'customerCity', False),
    Column('cname', 'customerNameWholesale', False),
    Column('czip', 'customerPostalCode', False),
    Column('mcolordesc', 'color', False),
    Column('mcolor', 'colorCode', False),
    Column('supplier', 'supplier', False),
    Column('klcode_lev', 'colorCodeSupplier', False),
    Column('kl_lev', 'colorDescSupplier', False),
    Column('collection', 'collection', False),
    Column('sizename', 'size', False),
    Column('aatr1', 'articleGroup1', False),
    Column('aatr2', 'articleGroup2', False),
    Column('aatr3', 'articleGroup3', False),
    Column('aatr4', 'articleGroup4', False),
    Column('aatr5', 'articleGroup5', False),
    Column('aatr6', 'articleGroup6', False),
    Column('aatr7', 'articleGroup7', False),
    Column('aatr8', 'articleGroup8', False),
    Column('aatr9', 'articleGroup9', False),
    Column('cbscode', 'cbs', False),
    Column('catr1', 'customerGroup1', False),
    Column('catr2', 'customerGroup2', False),
    Column('catr3', 'customerGroup3', False),
    # AGGREGATED COLUMNS
    Column('qty', 'qty', True),
    Column('value', 'value', True),
    Column('qty_ex_cancelled', 'qtyOrderExcludingCancelled', True),
    Column('value_ex_cancelled', 'valueOrderExcludingCancelled', True),
    Column('n_presold', 'qtyDelivered', True),
    Column('qty_del_per', 'qtyDeliveredPercentage', True),
    Column('a_presold', 'valueDelivered', True),
    Column('value_del_per', 'valueDeliveredPercentage', True),
    Column('n_sold', 'qtyPostDelivery', True),
    Column('qty_post_del_per', 'qtyPostDeliveryPercentage', True),
    Column('a_sold', 'valuePostDelivery', True),
    Column('value_post_del_per', 'valuePostDeliveryPercentage', True),
    Column('n_return', 'qtyReturned', True),
    Column('qty_returned_per', 'qtyReturnedPercentage', True),
    Column('a_return', 'valueReturned', True),
    Column('value_returned_per', 'valueReturnedPercentage', True),
    Column('qty_picklist', 'qtyPicklist', True),
    Column('value_picklist', 'valuePicklist', True),
    Column('qty_picklist_per', 'qtyPicklistPer', True),
    Column('value_picklist_per', 'valuePicklistPer', True),
]

COLUMN_TO_ALIAS = {c.column_name: c.alias for c in COLUMNS}
ALIAS_TO_COLUMN = {c.alias: c.column_name for c in COLUMNS}
AGGREGATED_FIELDS = [c.alias for c in COLUMNS if c.aggregated]
GROUPS = [c.alias for c in COLUMNS if not c.aggregated]

# Needed to revert Redshift identifiers to their camelcase forms.
LOWER_TO_CAMEL = {c.alias.lower(): c.alias for c in COLUMNS}


class FilterSchema(Schema):
    article = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['article'],
        metadata={'include_filter_values': False},
    )
    supplier = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['supplier'],
    )
    aatr1 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr1'],
    )
    aatr2 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr2'],
    )
    aatr3 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr3'],
    )
    aatr4 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr4'],
    )
    aatr5 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr5'],
    )
    aatr6 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr6'],
    )
    aatr7 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr7'],
    )
    aatr8 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr8'],
    )
    aatr9 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['aatr9'],
    )
    agent = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['agent'],
    )
    brand = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['brand'],
    )
    catr1 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['catr1'],
    )
    catr2 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['catr2'],
    )
    catr3 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['catr3'],
    )
    cbscode = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['cbscode'],
    )
    ccity = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['ccity'],
    )
    ccountry = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['ccountry'],
    )
    cname = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['cname'],
    )
    czip = fields.List(
        fields.String, validate=validate.Length(min=1), data_key=COLUMN_TO_ALIAS['czip']
    )
    kl_lev = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['kl_lev'],
        metadata={'include_filter_values': False},
    )
    klcode_lev = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['klcode_lev'],
        metadata={'include_filter_values': False},
    )
    mcolor = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['mcolor'],
    )
    mcolordesc = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['mcolordesc'],
    )
    sizename = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['sizename'],
    )
    collection = Nested(
        CollectionSchema,
        validate=validate.Length(min=1),
        many=True,
        data_key=COLUMN_TO_ALIAS['collection'],
    )

    tenant = fields.List(
        fields.Int, validate=validate.Length(min=1), metadata={'column': False}
    )
    endDate = fields.DateTime(required=True, metadata={'column': False})
    startDate = fields.DateTime(required=True, metadata={'column': False})

    @pre_load
    def handle_tenant_id(self, data, **kwargs):
        tenant_id = self.context['tenant_id']
        data.update({'tenant': [int(tenant_id)]})
        return data

    @validates_schema
    def validate_daterange(self, data, **kwargs):
        try:
            if data['startDate'] >= data['endDate']:
                raise ValidationError('startDate must be before endDate', 'startDate')
        except KeyError:
            pass

    class Meta:
        unknown = EXCLUDE
        ordered = True


class SortSchema(Schema):
    field = fields.String(
        required=True, validate=validate.OneOf(COLUMN_TO_ALIAS.values())
    )
    direction = fields.Int(validate=validate.OneOf([-1, 1]), load_default=1)

    @post_load
    def post_load(self, data, **kwargs):
        return (data['field'], {1: 'ASC', -1: 'DESC'}[data['direction']])

    @staticmethod
    def build_implicit_sort(sort, groups):
        implicit_sort = sorted(
            [(f, 'ASC') for f in set(groups) - {s[0] for s in sort}],
            key=lambda i: GROUPS.index(i[0]),
        )
        return sort + implicit_sort

    class Meta:
        unknown = EXCLUDE


class ParamSchema(Schema):
    filter = Nested(FilterSchema, required=True)
    sort = Nested(SortSchema, many=True, load_default=list)
    fields_ = fields.List(
        fields.String,
        data_key='fields',
        required=True,
        validate=[
            validate.ContainsOnly(
                AGGREGATED_FIELDS,
                error='Only the following fields are allowed: {choices}',
            ),
            validate.Length(min=1),
        ],
    )

    groups = fields.List(
        fields.String,
        load_default=list,
        validate=[
            validate.ContainsOnly(
                GROUPS, error='Only the following groups are allowed: {choices}'
            )
        ],
    )

    columnMetadata = fields.Dict(
        keys=fields.Str(),
        values=Nested(ColumnMetadata),
        load_default=dict,
        metadata={'description': METADATA_DESCRIPTION},
    )

    @post_load
    def set_report_name(self, data, **kwargs):
        data['report_name'] = _('customer-sales-report-heading').translate()
        return data

    @validates_schema
    def validate_sort(self, data, **kwargs):
        if 'sort' in data and not all(
            s[0] in data['fields_'] + data['groups'] for s in data['sort']
        ):
            raise ValidationError(
                'Can not sort by fields that are not requested in "fields".', 'sort'
            )

    @staticmethod
    def to_query(data, totals=False):
        if totals:
            data = {**data, 'sort': [], 'groups': []}

        t1, t2 = data['filter'].get('startDate'), data['filter'].get('endDate')

        filter_ = {
            k: v for k, v in data['filter'].items() if k not in {'startDate', 'endDate'}
        }

        fields_ = {ALIAS_TO_COLUMN[f] for f in data['fields_'] + data['groups']}
        sort = SortSchema.build_implicit_sort(data['sort'], data['groups'])

        return build(fields_, filter_, sort, t1, t2, COLUMN_TO_ALIAS)

    class Meta:
        unknown = EXCLUDE


def report(ctx, request, format='json'):
    """
    Wholesale customer sales report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Wholesale customer sales report
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'wholesale_customer_sales.json#/definitions/ParamSchema'
      produces:
        - application/json
      responses:
        200:
          description: The whosale customer sales report
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
    schema = ParamSchema(context={'tenant_id': request.requested_tenant_id})
    data = schema.load(request.json_payload)
    query = schema.to_query(data)

    with request.redshift.cursor() as cursor:
        debug_query(cursor, query)
        cursor.execute(query)
        result = cursor.fetchall()

    if not result:
        if format == 'json':
            return {'data': [], 'totals': []}
        raise NoDataToExport()

    result = revert_back_to_camelcase(result, LOWER_TO_CAMEL)
    round_results(result, 2)

    reference_order = [
        i for i in data['groups'] + data['fields_'] if i in COLUMN_TO_ALIAS.values()
    ]
    header = export_header(result, reference_order)

    if format == 'csv':
        temp_file = export_csv(header, result)
        return serve_csv_response(request.response, temp_file)

    totals_query = schema.to_query(data, totals=True)
    with request.redshift.cursor() as cursor:
        debug_query(cursor, totals_query)
        cursor.execute(totals_query)
        totals = cursor.fetchall()

    totals = revert_back_to_camelcase(totals, LOWER_TO_CAMEL)
    totals = totals[0]
    # assign an empty string to the columns in the report which are not numeric
    for k in result[0]:
        totals.setdefault(k, '')

    if format == 'json':
        return {'data': result, 'totals': totals}

    elif format == 'pdf':
        html, css = generate_article_status_html_css(
            request,
            data,
            request.db.tenants.find_one({'_id': request.requested_tenant_id}),
            {'data': result, 'totals': totals},
        )

        result = generate_pdf(html, css=css)
        filename = data['report_name'].replace(' ', '_')
        return make_pdf_file_response(request, result, filename)

    elif format == 'excel':
        temp_file = generate_excel_report(data, result, totals)
        filename = data['report_name'].replace(' ', '_') + '.xlsx'
        return serve_excel_response(request.response, temp_file, filename)


def report_csv(ctx, request):
    """
    Wholesale customer sales report csv file

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Wholesale customer sales report csv file
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'wholesale_customer_sales.json#/definitions/ParamSchema'
      produces:
        - text/csv
      responses:
        200:
          description: A csv file of the article status report
          schema:
            type: file
    """
    return report(ctx, request, format='csv')


def report_excel(ctx, request):
    """
    Wholesale customer sales report excel file

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Wholesale customer sales report excel file
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'wholesale_customer_sales.json#/definitions/ParamSchema'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: An excel file of the wholesale customer report
          schema:
            type: file
    """
    return report(ctx, request, format='excel')


def report_pdf(ctx, request):
    """
    Wholesale customer sales report pdf file

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Wholesale customer sales report pdf file
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'wholesale_customer_sales.json#/definitions/ParamSchema'
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the wholesale customer report
          schema:
            type: file
    """
    return report(ctx, request, format='pdf')


class WholesaleCustomerFilterQuery(Schema):
    filter = Nested(FilterSchema, exclude=('startDate', 'endDate'), load_default=dict)

    @staticmethod
    def to_query(data):
        fields_ = {
            key
            for key, value in FilterSchema._declared_fields.items()
            if value.metadata.get('include_filter_values', True)
            and value.metadata.get('column', True)
        }

        q = build_filter_values(fields_, data['filter'], COLUMN_TO_ALIAS)
        return q

    class Meta:
        unknown = EXCLUDE


def report_filters(ctx, request):
    """
    Possible filter values for the wholesale customer sales report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Possible filter values for the wholesale customer sales report
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'wholesale_customer_sales_filter.json#/definitions/\
WholesaleCustomerFilterQuery'
      produces:
        - application/json
      responses:
        200:
          description: Possible filter values for wholesale customer report
          schema:
            type: object
            properties:
              groups:
                type: array
                items:
                  type: string
                description: possible groups
              fields:
                type: array
                items:
                  type: string
                description: possible filters
              filter:
                type: object
                description: >
                  each key is a filter, the value is an array of possible values for
                  that filter
    """
    data = WholesaleCustomerFilterQuery(
        context={'tenant_id': request.requested_tenant_id}
    ).load(request.json_payload)
    query = WholesaleCustomerFilterQuery.to_query(data)

    with request.redshift.cursor() as cursor:
        debug_query(cursor, query)
        cursor.execute(query)
        result = cursor.fetchall()

    result = prepare_filter_response(result, LOWER_TO_CAMEL)

    data = {
        'groups': [c.alias for c in COLUMNS if not c.aggregated],
        'fields': [c.alias for c in COLUMNS if c.aggregated],
        'filter': result,
    }

    default_filter_values(result, FilterSchema)

    return {'data': data}
