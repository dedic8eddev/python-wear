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

from spynl.api.retail.exceptions import NoDataToExport

from spynl.services.reports.article_status import (
    ALIAS_TO_COLUMN,
    COLUMN_TO_ALIAS,
    CUSTOMER_REPORT_COLUMNS,
    CUSTOMER_REPORT_GROUPS,
    LOWER_TO_CAMEL,
    ArticleStatusQuery,
    SortSchema,
    serve_report,
)
from spynl.services.reports.article_status_query_builder import build
from spynl.services.reports.utils import (
    CollectionSchema,
    build_filter_values,
    debug_query,
    default_filter_values,
    prepare_filter_response,
)


class FilterSchema(Schema):
    article = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['article'],
        metadata={'include_filter_values': False},
    )
    descript = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['descript'],
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
    collection = Nested(CollectionSchema, many=True, validate=validate.Length(min=1))
    scolor = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['scolor'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    color = fields.List(
        fields.String,
        validate=validate.Length(min=1),
        data_key=COLUMN_TO_ALIAS['color'],
    )
    sizename = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['sizename'],
        validate=validate.Length(min=1),
    )
    caddress = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['caddress'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    chouseno = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['chouseno'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    ccity = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['ccity'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    ccountry = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['ccountry'],
        validate=validate.Length(min=1),
    )
    cemail = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['cemail'],
        validate=validate.Length(min=1),
    )
    ctitle = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['ctitle'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    cname = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['cname'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    cfullname = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['cfullname'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    cbirth = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['cbirth'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    czip = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['czip'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    custnr = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['custnr'],
        validate=validate.Length(min=1),
        metadata={'include_filter_values': False},
    )
    reference = fields.List(
        fields.String,
        data_key=COLUMN_TO_ALIAS['reference'],
        validate=validate.Length(min=1),
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

    trtype = fields.Constant([2, 95], metadata={'column': False})
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


class RetailCustomerSalesQuery(ArticleStatusQuery):
    filter = Nested(FilterSchema, load_default=dict)

    @post_load
    def set_report_name(self, data, **kwargs):
        data['report_name'] = _('customer-sales-report-heading').translate()
        return data

    @staticmethod
    def to_query(data, totals=False):
        if totals:
            data = {**data, 'sort': [], 'groups': []}

        fields_ = {ALIAS_TO_COLUMN[f] for f in data['fields_'] + data['groups']}

        sort = SortSchema.build_implicit_sort(data['sort'], data['groups'])
        t1, t2 = data['filter'].get('startDate'), data['filter'].get('endDate')
        return build(fields_, data['filter'], sort, t1, t2, COLUMN_TO_ALIAS)

    class Meta:
        exclude = ('sales_only',)


class RetailCustomerFilterQuery(Schema):
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


def retail_customer_sales_excel(ctx, request):
    """
    Return the retail customer sales report as a Microsoft Excel document
    compatible with versions of Microsoft Excel 2007 and above.

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate a retail customer sales report as a Microsoft Excel document.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'retail_customer_sales.json#/definitions/RetailCustomerSalesQuery'
      produces:
        - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
      responses:
        200:
          description: The report as an excel file.
          schema:
            type: file
    """
    return serve_report(ctx, request, 'excel', RetailCustomerSalesQuery)


def retail_customer_sales_csv(ctx, request):
    """
    Return the retail customer sales report as Comma Separated Value (CSV) document.

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate the retail customer sales report as Comma Separated Value (CSV)
        document.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'retail_customer_sales.json#/definitions/RetailCustomerSalesQuery'
      produces:
        - text/csv
      responses:
        200:
          description: The report in csv format.
    """
    return serve_report(ctx, request, 'csv', RetailCustomerSalesQuery)


def retail_customer_sales_json(ctx, request):
    """
    Returns the retail customer sales report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Generate a retail customer sales report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'retail_customer_sales.json#/definitions/RetailCustomerSalesQuery'
      produces:
        - application/json
      responses:
        200:
          description:
          schema:
            type: array
            items:
              type: object
      responses:
        200:
          description: The retail customer sales report
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
        return serve_report(ctx, request, 'json', RetailCustomerSalesQuery)
    except NoDataToExport:
        return {'data': [], 'totals': []}


def retail_customer_sales_pdf(ctx, request):
    """
    Returns a pdf of the retail customer sales report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Download a pdf of a retail customer sales report.
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'retail_customer_sales.json#/definitions/RetailCustomerSalesQuery'
      produces:
        - application/pdf
      responses:
        200:
          description: A pdf file of the retail customer sales report
          schema:
            type: file
    """
    return serve_report(ctx, request, 'pdf', RetailCustomerSalesQuery)


def retail_customer_sales_filter(ctx, request):
    """
    Possible filter values for the retail customer report

    ---
    post:
      tags:
        - services
        - reporting
      description: >
        Possible filter values for the retail customer report
        \n
        Located in spynl-services.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            $ref: 'retail_customer_sales_filter.json#/definitions/\
RetailCustomerFilterQuery'
      produces:
        - application/json
      responses:
        200:
          description: Possible filter values for the retail customer report
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
    schema = RetailCustomerFilterQuery(
        context={'tenant_id': request.requested_tenant_id}
    )
    data = schema.load(request.json_payload)
    query = schema.to_query(data)

    with request.redshift.cursor() as cursor:
        debug_query(cursor, query)
        cursor.execute(query)
        result = cursor.fetchall()

    result = prepare_filter_response(result, LOWER_TO_CAMEL)
    groups = CUSTOMER_REPORT_GROUPS
    columns = CUSTOMER_REPORT_COLUMNS

    default_filter_values(result, FilterSchema)

    return {'data': {'groups': groups, 'fields': columns, 'filter': result}}
