from collections import namedtuple
from copy import deepcopy
from datetime import datetime, timezone

from marshmallow import (
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)

from spynl_schemas import Schema
from spynl_schemas.fields import Nested

from spynl.locale import SpynlTranslationString as _

from spynl.main.serial.file_responses import (
    METADATA_DESCRIPTION,
    ColumnMetadata,
    make_pdf_file_response,
)
from spynl.main.utils import get_logger

from spynl.services.pdf.pdf import generate_pdf, generate_stock_html_css
from spynl.services.reports.stock_query_builder import (
    add_limit_offset,
    build,
    build_filter_values,
    build_stock_return_value,
)
from spynl.services.reports.utils import (
    CollectionSchema,
    debug_query,
    default_filter_values,
    prepare_filter_response,
)

Column = namedtuple('Column', ['column_name', 'alias', 'internal'])


logger = get_logger('spynl.services.reports.stock')


# NOTE The order of this list is significant
COLUMNS = [
    Column('brand', 'brand', False),
    Column('aatr1', 'articleGroup1', False),
    Column('aatr2', 'articleGroup2', False),
    Column('aatr3', 'articleGroup3', False),
    Column('aatr4', 'articleGroup4', False),
    Column('aatr5', 'articleGroup5', False),
    Column('aatr6', 'articleGroup6', False),
    Column('aatr7', 'articleGroup7', False),
    Column('aatr8', 'articleGroup8', False),
    Column('aatr9', 'articleGroup9', False),
    Column('barcode', 'barcode', False),
    Column('descript', 'articleDescription', True),
    Column('warehouse', 'warehouse', True),
    Column('collection', 'collection', False),
    Column('scolor', 'customGroupBy', True),
    Column('tenantname', 'company', False),
    Column('supplier', 'supplier', False),
    Column('article', 'articleCode', True),
    Column('artnr_lev', 'articleCodeSupplier', True),
    Column('n_stock', 'stock', True),
]

COLUMNS_TO_ALIAS = {c.column_name: c.alias for c in COLUMNS}
ALIAS_TO_COLUMN = {v: k for k, v in COLUMNS_TO_ALIAS.items()}
GROUPS = [c.column_name for c in COLUMNS if not c.internal]
ALIASES = [c.alias for c in COLUMNS if not c.internal]
LOWER_TO_CAMEL = {c.alias.lower(): c.alias for c in COLUMNS}


class FilterSchema(Schema):
    descript = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['descript'],
    )
    barcode = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['barcode'],
        metadata={'include_filter_values': False},
    )
    article = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['article'],
    )
    artnr_lev = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['artnr_lev'],
    )
    supplier = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['supplier'],
    )
    brand = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['brand'],
    )
    warehouse = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['warehouse'],
    )
    scolor = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['scolor'],
    )
    aatr1 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr1'],
    )
    aatr2 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr2'],
    )
    aatr3 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr3'],
    )
    aatr4 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr4'],
    )
    aatr5 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr5'],
    )
    aatr6 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr6'],
    )
    aatr7 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr7'],
    )
    aatr8 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr8'],
    )
    aatr9 = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMNS_TO_ALIAS['aatr9'],
    )
    collection = Nested(
        CollectionSchema,
        validate=validate.Length(min=1),
        many=True,
        data_key=COLUMNS_TO_ALIAS['collection'],
    )
    tenant = fields.List(
        fields.Int, validate=validate.Length(min=1), metadata={'column': False}
    )
    # The beginning of redshift data
    startDate = fields.Constant(
        datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc), metadata={'column': False}
    )
    endDate = fields.DateTime(
        # load_default=datetime(2030, 1, 1, 0, 0, tzinfo=timezone.utc),
        required=True,
        metadata={'column': False},
    )

    @pre_load
    def handle_tenant_id(self, data, **kwargs):
        tenant_id = self.context['tenant_id']
        data.update({'tenant': [int(tenant_id)]})
        return data

    @post_load
    def convert_datetimes(self, data, **kwargs):
        for k in ('startDate', 'endDate'):
            try:
                data[k] = int(data[k].timestamp())
            except KeyError:
                # field was excluded
                pass
        return data

    @validates_schema
    def validate_daterange(self, data, **kwargs):
        try:
            if data['startDate'] >= data['endDate']:
                raise ValidationError('startDate must be before endDate', 'startDate')
        except KeyError:
            pass


class SortSchema(Schema):
    field = fields.String(required=True, validate=validate.OneOf(ALIASES))
    direction = fields.Int(validate=validate.OneOf([-1, 1]), load_default=1)

    @post_load
    def post_load(self, data, **kwargs):
        return (data['field'], {1: 'ASC', -1: 'DESC'}[data['direction']])


class StockQuery(Schema):
    filter = Nested(FilterSchema, required=True)
    sort = Nested(SortSchema, many=True, load_default=list)
    groups = fields.List(
        fields.String, validate=validate.ContainsOnly(ALIASES), load_default=list
    )
    keep_zero_lines = fields.Boolean(load_default=False, data_key='keepZeroLines')
    calculate_totals = fields.Boolean(
        load_default=False,
        data_key='calculateTotals',
        metadata={
            'description': 'changes the matrices to include row and column totals.'
        },
    )
    history = fields.Boolean(
        load_default=False, metadata={'description': 'Show the history of each sku'}
    )

    @validates_schema
    def validate_sort(self, data, **kwargs):
        if 'sort' in data and not all(s[0] in data['groups'] for s in data['sort']):
            raise ValidationError(
                'Cannot sort by columns that are not requested in "groups".', 'sort'
            )

    @post_load
    def postprocess(self, data, **kwargs):
        data = self.set_defaults(data)
        data = self.revert_alias_to_column(data)
        return data

    def revert_alias_to_column(self, data):
        data['groups'] = [ALIAS_TO_COLUMN.get(g, g) for g in data['groups']]
        data['sort'] = [(ALIAS_TO_COLUMN.get(f, f), d) for f, d in data['sort']]
        return data

    def set_defaults(self, data):
        default_sort = sorted(
            [
                (ALIAS_TO_COLUMN[g], 'ASC')
                for g in data['groups']
                if g not in [s[0] for s in data['sort']]
            ],
            key=lambda i: GROUPS.index(i[0]),
        )

        data['sort'] = (
            data['sort']
            + default_sort
            + [('article', 'ASC'), ('sizeidx', 'ASC'), ('label', 'ASC')]
        )
        data['groups'].extend(
            [
                'article',
                'articleCodeSupplier',
                'articleDescription',
                'sizename',
                'label',
                'sizeidx',
                'n_stock',
            ]
        )
        return data

    @staticmethod
    def to_query(data):
        t1, t2 = data['filter'].pop('startDate'), data['filter'].pop('endDate')

        return build(
            data['groups'],
            data['filter'],
            data['sort'],
            t1,
            t2,
            history=data['history'],
        )


class StockFilter(Schema):
    filter = Nested(FilterSchema, exclude=('startDate', 'endDate'), load_default=dict)

    @staticmethod
    def to_query(data):
        fields_ = {
            key
            for key, value in FilterSchema._declared_fields.items()
            if value.metadata.get('include_filter_values', True)
            and value.metadata.get('column', True)
        }

        return build_filter_values(fields_, data['filter'], COLUMNS_TO_ALIAS)


def generate_report_data(request, schema, **kwargs):
    parameters = schema(context={'tenant_id': request.requested_tenant_id}).load(
        request.json_payload
    )
    query = schema.to_query(deepcopy(parameters))
    result = []
    with request.redshift.cursor() as c:
        limit = 5000
        offset = 0

        while True:
            debug_query(c, query)
            c.execute(add_limit_offset(query, limit, offset))
            rows = c.fetchall()
            if not rows:
                break

            result.extend(rows)
            offset += limit

    if result:
        matrices = build_stock_return_value(
            result,
            parameters['groups'],
            keep_zero_lines=parameters.get('keep_zero_lines'),
            calculate_totals=parameters['calculate_totals'],
            history=parameters['history'],
            **kwargs,
        )
        data = [{COLUMNS_TO_ALIAS.get(k, k): v for k, v in m.items()} for m in matrices]
    else:
        data = []
    return parameters, data


def stock_report(ctx, request):
    """
    Returns the stock report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate a stock report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'stock.json#/definitions/StockQuery'
      produces:
        - application/json
      responses:
        200:
          description: The stock report
          schema:
            type: object
            properties:
              data:
                type: array
                items:
                  type: object
                description: >
                  A series of skus and header items to separate the groups.
                  Each sku object contains 'articleCode' (string), any groups
                  selected (e.g. brand), 'stock' (float), and 'skuStockMatrix'.
                  The skuStockMatrix is a list of lists, with the headings in
                  the first list, and in each subsequent list the colorcode is
                  the first item, with stock information the the next items. \n
                  Example:\n
                  \n
                      {
                        "articleCode": "z9-10f-42140",
                        "brand": "10 Feet",
                        # + any other groups selected
                        "skuStockMatrix": [
                            [
                                "-",
                                "M"
                            ],
                            [
                                "blac",
                                -1.0
                            ]
                        ],
                        "stock": -1.0
                      }
                  Headers have the following format {'header': 'G-Star, Amsterdam'}

    """
    parameters, data = generate_report_data(request, StockQuery)
    return {'data': data}


class StockPDFQuery(StockQuery):
    columnMetadata = fields.Dict(
        keys=fields.Str(),
        values=Nested(ColumnMetadata),
        load_default=dict,
        metadata={'description': METADATA_DESCRIPTION},
    )
    productPhotos = fields.Boolean(
        load_default=False,
        metadata={'description': 'Print photos of articles in the pdf.'},
    )
    pageSize = fields.String(
        load_default='A4 portrait',
        validate=validate.OneOf(['A4 landscape', 'A4 portrait']),
        metadata={'description': 'Page size and orientation of the pdf.'},
    )

    @post_load
    def set_report_name(self, data, **kwargs):
        data['report_name'] = _('stock-report-heading').translate()
        return data

    @post_load
    def set_calculate_totals(self, data, **kwargs):
        # calculate totals should always be True for PDF's
        data['calculate_totals'] = True
        return data

    class Meta(StockQuery.Meta):
        exclude = ['calculate_totals']


def stock_pdf(ctx, request):
    """
    Returns a pdf of the article status report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Download a pdf of a stock report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'stock_pdf.json#/definitions/StockPDFQuery'
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the article status report
          schema:
            type: file
    """
    parameters, data = generate_report_data(
        request,
        StockPDFQuery,
        headers_in_separate_row=False,
        empty_group_tag='-',
        group_separator=' - ',
    )
    html, css = generate_stock_html_css(
        request,
        parameters,
        request.db.tenants.find_one({'_id': request.requested_tenant_id}),
        data,
    )
    result = generate_pdf(html, css=css)
    filename = parameters['report_name'].replace(' ', '_')
    return make_pdf_file_response(request, result, filename)


def stock_filter(ctx, request):
    """
    Possible filter values for the stock report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Possible filter values for the stock report
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'stock_filter.json#/definitions/StockFilter'
      produces:
        - application/json
      responses:
        200:
          description: Possible filter values for the stock report
          schema:
            type: object
            properties:
              groups:
                type: array
                items:
                  type: string
                description: possible groups
              filter:
                type: object
                description: >
                  each key is a filter, the value is an array of possible values for
                  that filter
    """
    data = StockFilter(context={'tenant_id': request.requested_tenant_id}).load(
        request.json_payload
    )
    query = StockFilter.to_query(data)

    with request.redshift.cursor() as c:
        debug_query(c, query)
        c.execute(query)
        result = c.fetchall()

    result = prepare_filter_response(result, LOWER_TO_CAMEL)

    default_filter_values(result, FilterSchema)

    return {'data': {'groups': ALIASES, 'filter': result}}
