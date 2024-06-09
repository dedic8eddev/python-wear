"""
plugger.py is used by spynl Plugins to say
which endpoints and resources it will use.
"""
import logging

from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from spynl.api.retail.resources import Reports

from spynl.services.reports import (
    article_status,
    retail_customer_sales,
    stock,
    wholesale_customer_sales,
)
from spynl.services.reports.utils import (
    BadRedshiftURI,
    RedshiftConnectionError,
    parse_connection_string,
)


def includeme(config):
    """Update the configurator with the endpoints."""
    log = logging.getLogger(__name__)

    config.add_endpoint(
        article_status.article_status_excel,
        'article-status-excel',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        article_status.article_status_csv,
        'article-status-csv',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        article_status.article_status_json,
        'article-status',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        article_status.article_status_pdf,
        'article-status-pdf',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        article_status.article_status_email,
        'article-status-email',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        article_status.article_status_filter,
        'article-status-filter',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        retail_customer_sales.retail_customer_sales_excel,
        'retail-customer-sales-excel',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        retail_customer_sales.retail_customer_sales_csv,
        'retail-customer-sales-csv',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        retail_customer_sales.retail_customer_sales_json,
        'retail-customer-sales',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        retail_customer_sales.retail_customer_sales_pdf,
        'retail-customer-sales-pdf',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        retail_customer_sales.retail_customer_sales_filter,
        'retail-customer-sales-filter',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        stock.stock_report,
        'stock-report',
        context=Reports,
        permission='read',
        redshift=True,
    )
    config.add_endpoint(
        stock.stock_pdf,
        'stock-report-pdf',
        context=Reports,
        permission='read',
        redshift=True,
    )
    config.add_endpoint(
        stock.stock_filter,
        'stock-report-filter',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        article_status.latest_data,
        'latest-data',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        wholesale_customer_sales.report,
        'wholesale-customer-sales',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        wholesale_customer_sales.report_csv,
        'wholesale-customer-sales-csv',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        wholesale_customer_sales.report_excel,
        'wholesale-customer-sales-excel',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        wholesale_customer_sales.report_pdf,
        'wholesale-customer-sales-pdf',
        context=Reports,
        permission='read',
        redshift=True,
    )

    config.add_endpoint(
        wholesale_customer_sales.report_filters,
        'wholesale-customer-sales-filter',
        context=Reports,
        permission='read',
        redshift=True,
    )

    redshift_uri = config.get_settings().get('spynl.redshift.url')
    redshift_max_connections = config.get_settings().get(
        'spynl.redshift.max_connections'
    )
    connection_pool = None

    def add_redshift_connection(view, info):
        if not info.options.get('redshift'):
            return view

        def wrapper(ctx, request):
            nonlocal connection_pool

            if not connection_pool:
                try:
                    dsn = parse_connection_string(redshift_uri)
                    connection_pool = ThreadedConnectionPool(
                        1,
                        int(redshift_max_connections),
                        cursor_factory=RealDictCursor,
                        connect_timeout=10,
                        **dsn
                    )
                except BadRedshiftURI as e:
                    log.exception(
                        'Could not parse connection string: %s' % redshift_uri
                    )
                    raise RedshiftConnectionError from e
                except OperationalError as e:
                    log.exception('Could not connect to: %s' % redshift_uri)
                    raise RedshiftConnectionError from e

            conn = connection_pool.getconn()
            request.redshift = conn

            try:
                resp = view(ctx, request)
            except Exception:
                connection_pool.putconn(conn)
                raise
            else:
                connection_pool.putconn(conn)

            return resp

        return wrapper

    add_redshift_connection.options = ('redshift',)
    config.add_view_deriver(add_redshift_connection)

    config.add_jinja2_search_path('spynl.services.reports:email-templates')
