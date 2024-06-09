import datetime
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
from psycopg2 import sql
from pyramid_mailer.message import Attachment

from spynl_schemas import BleachedHTMLField, Nested

from spynl.locale import SpynlTranslationString as _

from spynl.main.mail import send_template_email
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
from spynl.services.pdf.utils import format_datetime
from spynl.services.reports.article_status_query_builder import (
    T0,
    build,
    build_filter_values,
)
from spynl.services.reports.utils import (
    CollectionSchema,
    debug_query,
    default_filter_values,
    generate_excel_report,
    prepare_filter_response,
    revert_back_to_camelcase,
)

# Report types
CUSTOMER = 'customer'
ARTICLE = 'article'

# When only showing articles with sales in the asked for period, not all totals make
# sense, so we only show these:
SALES_ONLY_TOTAL_COLUMNS = [
    'soldItems',
    'amountSold',
    'amountSoldExVAT',
    'costPrice',
    'margin',
    'netProfit',
    'amountVAT',
]

Column = namedtuple('Column', ['column_name', 'alias', 'aggregated', 'report_type'])

# For documentation about the columns see:
# https://softwearconnect.atlassian.net/l/c/jfu2fXAm

# NOTE The order of this list is significant
COLUMNS = [
    # NON AGGREGATED COLUMNS
    Column('brand', 'brand', False, {CUSTOMER, ARTICLE}),
    Column('aatr1', 'articleGroup1', False, {ARTICLE, CUSTOMER}),
    Column('article', 'articleCode', False, {CUSTOMER, ARTICLE}),
    Column('barcode', 'barcode', False, {ARTICLE}),
    Column('supplier', 'supplier', False, {ARTICLE}),
    Column('agent', 'agent', False, {ARTICLE}),
    Column('mcolordesc', 'color', False, {CUSTOMER, ARTICLE}),
    Column('mcolor', 'colorCode', False, {CUSTOMER, ARTICLE}),
    Column('klcode_lev', 'colorCodeSupplier', False, {ARTICLE}),
    Column('kl_lev', 'colorDescSupplier', False, {CUSTOMER, ARTICLE}),
    Column('aatr2', 'articleGroup2', False, {ARTICLE, CUSTOMER}),
    Column('aatr3', 'articleGroup3', False, {ARTICLE, CUSTOMER}),
    Column('aatr4', 'articleGroup4', False, {ARTICLE, CUSTOMER}),
    Column('aatr5', 'articleGroup5', False, {ARTICLE, CUSTOMER}),
    Column('aatr6', 'articleGroup6', False, {ARTICLE, CUSTOMER}),
    Column('aatr7', 'articleGroup7', False, {ARTICLE, CUSTOMER}),
    Column('aatr8', 'articleGroup8', False, {ARTICLE, CUSTOMER}),
    Column('aatr9', 'articleGroup9', False, {ARTICLE, CUSTOMER}),
    Column('artset', 'set', False, {ARTICLE}),
    Column('artnr_lev', 'articleCodeSupplier', False, {CUSTOMER, ARTICLE}),
    Column('color', 'colorFamily', False, {CUSTOMER, ARTICLE}),
    Column('warehouse', 'warehouse', False, {CUSTOMER, ARTICLE}),
    Column('collection', 'collection', False, {CUSTOMER, ARTICLE}),
    Column('descript', 'articleDescription', False, {ARTICLE, CUSTOMER}),
    Column('scolor', 'customGroupBy', False, {CUSTOMER, ARTICLE}),
    Column('sizename', 'size', False, {CUSTOMER, ARTICLE}),
    Column('tenantname', 'company', False, {ARTICLE}),
    Column('ccity', 'customerCity', False, {CUSTOMER}),
    # address only contains street:
    Column('caddress', 'customerStreet', False, {CUSTOMER}),
    Column('chouseno', 'customerHouseNumber', False, {CUSTOMER}),
    Column('ccountry', 'customerCountry', False, {CUSTOMER}),
    Column('cemail', 'customerEmail', False, {CUSTOMER}),
    Column('custnr', 'customerNumber', False, {CUSTOMER}),
    Column('cfullname', 'customerFullName', False, {CUSTOMER}),
    Column('ctitle', 'customerTitle', False, {CUSTOMER}),
    Column('cname', 'customerName', False, {CUSTOMER}),
    Column('cbirth', 'customerBirthday', False, {CUSTOMER}),
    Column('czip', 'customerPostalCode', False, {CUSTOMER}),
    Column('reference', 'Reference', False, {CUSTOMER}),
    Column('catr1', 'customerGroup1', False, {CUSTOMER}),
    Column('catr2', 'customerGroup2', False, {CUSTOMER}),
    Column('catr3', 'customerGroup3', False, {CUSTOMER}),
    # AGGREGATED COLUMNS
    Column('n_recieved', 'receivings', True, {ARTICLE}),
    Column('a_recieved', 'receivingsAmount', True, {ARTICLE}),
    Column('n_sold', 'soldItems', True, {CUSTOMER, ARTICLE}),
    Column('a_sold', 'amountSold', True, {CUSTOMER, ARTICLE}),
    Column('a_sold_ex', 'amountSoldExVAT', True, {CUSTOMER, ARTICLE}),
    Column('end_stock', 'endingStock', True, {ARTICLE}),
    Column('a_end_stock', 'endingStockAmount', True, {ARTICLE}),
    Column('c_sold', 'costPrice', True, {CUSTOMER, ARTICLE}),
    Column('n_change', 'mutation', True, {ARTICLE}),
    Column('a_change', 'mutationAmount', True, {ARTICLE}),
    Column('a_prepick', 'prepickAmount', True, {ARTICLE}),
    Column('n_prepick', 'prepickItems', True, {ARTICLE}),
    # The retail prepick columns are the exact same as those without retail, but we need
    # to return them separately so the frontend can translate them differently.
    Column('a_prepick_retail', 'consignmentAmount', True, {CUSTOMER, ARTICLE}),
    Column('n_prepick_retail', 'consignmentItems', True, {CUSTOMER, ARTICLE}),
    Column('a_stock', 'stockAmount', True, {ARTICLE}),
    Column('n_stock', 'startingStock', True, {ARTICLE}),
    Column('a_transit', 'transitsAmount', True, {ARTICLE}),
    Column('n_transit', 'transits', True, {ARTICLE}),
    Column('a_avg_stockX', 'averageStockAmount', True, {ARTICLE}),
    Column('avg_stockX', 'averageStock', True, {ARTICLE}),
    # Column('n_presold', 'presold', True, {ARTICLE}),
    # Column('a_presold', 'presoldAmount', True, {ARTICLE}),
    Column('n_turnover_velocity', 'turnOverVelocityCount', True, {ARTICLE}),
    Column('a_turnover_velocity', 'turnOverVelocityAmount', True, {ARTICLE}),
    Column('sellout_percentage', 'selloutPercentage', True, {ARTICLE}),
    Column('margin', 'margin', True, {ARTICLE}),
    Column('start_margin', 'startMargin', True, {ARTICLE}),
    Column('profitability', 'profitability', True, {ARTICLE}),
    Column('net_profit', 'netProfit', True, {CUSTOMER, ARTICLE}),
    Column('roi', 'returnOnInvestment', True, {ARTICLE}),
    Column('max_turnover', 'maxTurnover', True, {ARTICLE}),
    Column('leakage', 'leakage', True, {ARTICLE}),
    Column('discount', 'discount', True, {CUSTOMER, ARTICLE}),
    Column('n_bought', 'bought', True, {ARTICLE}),
    Column('a_bought', 'boughtAmount', True, {ARTICLE}),
    Column('a_revalue', 'revalue', True, {ARTICLE}),
    Column('last_received', 'lastReceived', True, {ARTICLE}),
    Column('amount_vat', 'amountVAT', True, {CUSTOMER}),
]


AGGREGATED_FIELDS = []
GROUPS = []
CUSTOMER_REPORT_GROUPS = []
ARTICLE_STATUS_REPORT_GROUPS = []
ALIAS_TO_COLUMN = {}
COLUMN_TO_ALIAS = {}

CUSTOMER_REPORT_COLUMNS = []
ARTICLE_STATUS_REPORT_COLUMNS = []

# Needed to revert Redshift identifiers to their camelcase forms.
LOWER_TO_CAMEL = {c.alias.lower(): c.alias for c in COLUMNS}

for c in COLUMNS:
    ALIAS_TO_COLUMN.update({c.alias: c.column_name})
    COLUMN_TO_ALIAS.update({c.column_name: c.alias})
    if c.aggregated:

        AGGREGATED_FIELDS.append(c.alias)

        if CUSTOMER in c.report_type:
            CUSTOMER_REPORT_COLUMNS.append(c.alias)

        if ARTICLE in c.report_type:
            ARTICLE_STATUS_REPORT_COLUMNS.append(c.alias)

    else:
        GROUPS.append(c.alias)

        if CUSTOMER in c.report_type:
            CUSTOMER_REPORT_GROUPS.append(c.alias)

        if ARTICLE in c.report_type:
            ARTICLE_STATUS_REPORT_GROUPS.append(c.alias)


class FilterSchema(Schema):
    article = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['article'],
    )
    descript = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['descript'],
    )
    barcode = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['barcode'],
        metadata={'include_filter_values': False},
    )
    supplier = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['supplier'],
    )
    agent = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['agent'],
    )
    mcolordesc = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['mcolordesc'],
    )
    mcolor = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['mcolor'],
    )
    color = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['color'],
    )
    brand = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['brand'],
    )
    warehouse = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['warehouse'],
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
    collection = Nested(CollectionSchema, many=True, validate=validate.Length(min=1))
    scolor = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['scolor'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    sizename = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['sizename'],
        validate=validate.Length(min=1),
    )
    artset = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['artset'],
        validate=validate.Length(min=1),
    )
    klcode_lev = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['klcode_lev'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    kl_lev = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['kl_lev'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    artnr_lev = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['artnr_lev'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    tenantname = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['tenantname'],
        validate=validate.Length(min=1),
    )

    tenant = fields.List(
        fields.Int, validate=validate.Length(min=1), metadata={'column': False}
    )
    startDate = fields.DateTime(required=True, metadata={'column': False})
    endDate = fields.DateTime(required=True, metadata={'column': False})

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


class ArticleStatusQuery(Schema):
    sales_only = fields.Boolean(
        data_key='salesOnly',
        load_default=False,
        metadata={'description': 'Filters lines for which there were no sales'},
    )
    filter = Nested(FilterSchema, load_default=dict)
    sort = Nested(SortSchema, many=True, load_default=list)
    fields_ = fields.List(
        fields.String(),
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
    pageSize = fields.String(
        load_default='A4 landscape',
        validate=validate.OneOf(['A4 landscape', 'A3 landscape']),
        metadata={'description': 'Page size and orientation of the pdf.'},
    )

    columnMetadata = fields.Dict(
        keys=fields.Str(),
        values=Nested(ColumnMetadata),
        load_default=dict,
        metadata={'description': METADATA_DESCRIPTION},
    )

    @post_load
    def set_report_name(self, data, **kwargs):
        data['report_name'] = _('article-status-report-heading').translate()
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
        fields_ = {ALIAS_TO_COLUMN[f] for f in data['fields_'] + data['groups']}

        filter_ = {
            k: v for k, v in data['filter'].items() if k not in {'startDate', 'endDate'}
        }

        sort = SortSchema.build_implicit_sort(data['sort'], data['groups'])
        t1, t2 = data['filter'].get('startDate'), data['filter'].get('endDate')
        return build(
            fields_,
            filter_,
            sort,
            t1,
            t2,
            COLUMN_TO_ALIAS,
            filter_sales=data['sales_only'],
        )

    class Meta:
        unknown = EXCLUDE


class ArticleStatusFilterQuery(Schema):
    filter = Nested(FilterSchema, exclude=['startDate', 'endDate'], load_default=dict)

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


def article_status_excel(ctx, request):
    """
    Return the article status report as a Microsoft Excel document compatible
    with versions of Microsoft Excel 2007 and above.

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate an article status report as a Microsoft Excel document.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'article_status.json#/definitions/ArticleStatusQuery'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The report as an excel file.
          schema:
            type: file
    """
    return serve_report(ctx, request, 'excel', ArticleStatusQuery)


def article_status_csv(ctx, request):
    """
    Return the article status report as Comma Separated Value (CSV) document.

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate the article status report as Comma Separated Value (CSV)
        document.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'article_status.json#/definitions/ArticleStatusQuery'
      produces:
        - text/csv
      responses:
        200:
          description: The report in csv format.
    """
    return serve_report(ctx, request, 'csv', ArticleStatusQuery)


def article_status_json(ctx, request):
    """
    Returns the article status report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate an article status report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'article_status.json#/definitions/ArticleStatusQuery'
      produces:
        - application/json
      responses:
        200:
          description: The article status report
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
    try:
        return serve_report(ctx, request, 'json', ArticleStatusQuery)
    except NoDataToExport:
        return {'data': [], 'totals': []}


def article_status_pdf(ctx, request):
    """
    Returns a pdf of the article status report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Download a pdf of an article status report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'article_status.json#/definitions/ArticleStatusQuery'
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the article status report
          schema:
            type: file
    """
    return serve_report(ctx, request, 'pdf', ArticleStatusQuery)


def generate_report_data(ctx, request, schema):
    schema = schema(context={'tenant_id': request.requested_tenant_id})
    parameters = schema.load(request.json_payload)
    query = schema.to_query(parameters)

    with request.redshift.cursor() as cursor:
        debug_query(cursor, query)
        cursor.execute(query)
        result = cursor.fetchall()

    if not result:
        raise NoDataToExport()

    result = revert_back_to_camelcase(result, LOWER_TO_CAMEL)
    round_results(result, 2)

    # NOTE totals are not always sums. So execute the query without
    # grouping by anything to get the total for each aggregate field.
    totals_query = schema.to_query(parameters, totals=True)
    with request.redshift.cursor() as cursor:
        debug_query(cursor, totals_query)
        cursor.execute(totals_query)
        totals = cursor.fetchall()

    totals = revert_back_to_camelcase(totals, LOWER_TO_CAMEL)
    totals = totals[0]
    for key in result[0]:
        totals.setdefault(key, '')
        if parameters.get('sales_only'):
            if key not in SALES_ONLY_TOTAL_COLUMNS:
                totals[key] = ''

    reference_order = [
        i
        for i in parameters['groups'] + parameters['fields_']
        if i in COLUMN_TO_ALIAS.values()
    ]

    header = export_header(result, reference_order)

    return parameters, result, totals, header


def serve_report(ctx, request, format, schema):
    """format the data for file responses"""
    parameters, result, totals, header = generate_report_data(ctx, request, schema)

    if format == 'json':
        return {'data': result, 'totals': totals}

    elif format == 'pdf':
        html, css = generate_article_status_html_css(
            request,
            parameters,
            request.db.tenants.find_one({'_id': request.requested_tenant_id}),
            {'data': result, 'totals': totals},
        )
        result = generate_pdf(html, css=css)
        filename = parameters['report_name'].replace(' ', '_')
        return make_pdf_file_response(request, result, filename)

    elif format == 'excel':
        temp_file = generate_excel_report(parameters, result, totals)
        filename = parameters['report_name'].replace(' ', '_') + '.xlsx'
        return serve_excel_response(request.response, temp_file, filename)

    elif format == 'csv':
        temp_file = export_csv(header, result)
        return serve_csv_response(request.response, temp_file)


def generate_report_attachment(request, parameters, result, totals, header):
    """format the data for email attachments"""
    if parameters['format'] == 'pdf':
        html, css = generate_article_status_html_css(
            request,
            parameters,
            request.db.tenants.find_one({'_id': request.requested_tenant_id}),
            {'data': result, 'totals': totals},
        )
        result = generate_pdf(html, css=css)
        filename = parameters['report_name'].replace(' ', '_') + '.pdf'
        return Attachment(filename, 'application/pdf', result.getvalue())

    elif parameters['format'] == 'excel':
        temp_file = generate_excel_report(parameters, result, totals)
        filename = parameters['report_name'].replace(' ', '_') + '.xlsx'
        return Attachment(
            filename,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            temp_file,
        )

    elif parameters['format'] == 'csv':
        temp_file = export_csv(header, result)
        filename = parameters['report_name'].replace(' ', '_') + '.csv'
        return Attachment(filename, 'text/csv', temp_file)


class ArticleStatusEmailQuery(ArticleStatusQuery):
    recipients = fields.List(
        fields.Email,
        validate=validate.Length(min=1, max=20),
        metadata={'description': 'The recipients of the email.'},
    )
    format = fields.String(
        validate=validate.OneOf(
            ('pdf', 'excel', 'csv'), error='Must be one of {choices}, got {input}.'
        ),
        metadata={'description': 'The format of the file the email should send.'},
    )
    message = BleachedHTMLField(
        metadata={
            'description': 'A message that will be added to the body of the email.'
        },
        load_default=None,
    )


def article_status_email(ctx, request):
    """
    Email the article status report.

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Email an article status report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'article_status_email.json#/definitions/ArticleStatusEmailQuery'
      produces:
        - application/json
      responses:
        200:
          description: The article status report
          schema:
            type: object
            properties:
              status:
                type: string
    """
    parameters, result, totals, header = generate_report_data(
        ctx, request, ArticleStatusEmailQuery
    )
    attachment = generate_report_attachment(request, parameters, result, totals, header)

    tz = request.cached_user.get('tz', 'Europe/Amsterdam')
    locale = request.cached_user.get('language', 'nl-nl')[0:2]
    user = request.cached_user
    replacements = {
        'tz': tz,
        'locale': locale,
        'parameters': parameters,
        'username': user['username'],
        'now': format_datetime(
            datetime.datetime.now(datetime.timezone.utc), locale=locale, tzinfo=tz
        ),
    }

    send_template_email(
        request,
        parameters['recipients'],
        template_file='article_status',
        replacements=replacements,
        attachments=[attachment],
        fail_silently=False,
    )

    return {}


def article_status_filter(ctx, request):
    """
    Possible filter values for the article status report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Possible filter values for the article status report
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'article_status_filter.json#/definitions/\
ArticleStatusFilterQuery'
      produces:
        - application/json
      responses:
        200:
          description: Possible filter values for the article status report
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
    data = ArticleStatusFilterQuery(
        context={'tenant_id': request.requested_tenant_id}
    ).load(request.json_payload)
    query = ArticleStatusFilterQuery.to_query(data)

    with request.redshift.cursor() as cursor:
        debug_query(cursor, query)
        cursor.execute(query)
        result = cursor.fetchall()

    result = prepare_filter_response(result, LOWER_TO_CAMEL)
    groups = ARTICLE_STATUS_REPORT_GROUPS
    columns = ARTICLE_STATUS_REPORT_COLUMNS
    tenant = request.db.tenants.find_one({'_id': request.requested_tenant_id})
    # remove retail specific columns:
    if not tenant.get('retail'):
        columns = [
            column
            for column in columns
            if column not in ('consignmentAmount', 'consignmentItems')
        ]
    # remove wholesale specific columns:
    if not tenant.get('wholesale'):
        columns = [
            column
            for column in columns
            if column not in ('prepickAmount', 'prepickItems')
        ]

    default_filter_values(result, FilterSchema)

    return {'data': {'groups': groups, 'fields': columns, 'filter': result}}


def latest_data(ctx, request):
    """
    Return the date of the latest data available for your tenant

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Return the date of the latest data available for your tenant

        ### Response

        JSON keys | Type   | Description\n
        --------- | ------ | -----------\n
        status    | string | ok or error\n
        data      | object | {"date": DATETIME, "has_date": True}

    """
    query = sql.SQL(
        'SELECT "timestamp" from "transactions" WHERE "tenant" = {tenant_id} '
        'ORDER BY "timestamp" DESC LIMIT 1'
    ).format(tenant_id=sql.Literal(int(request.requested_tenant_id)))

    with request.redshift.cursor() as cursor:
        debug_query(cursor, query)
        cursor.execute(query)
        result = cursor.fetchall()

    if result:
        latest_date = result[0]['timestamp']
        has_data = True
    else:
        latest_date = T0
        has_data = False
    return {
        'data': {
            'latestDate': datetime.datetime.utcfromtimestamp(latest_date),
            'hasData': has_data,
        }
    }
