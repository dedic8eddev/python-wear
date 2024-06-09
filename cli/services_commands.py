import glob
import os
import shutil

import click
from marshmallow_jsonschema import JSONSchema

from cli.api_commands import dump_file, folder_option
from cli.cli import cli
from cli.utils import fail, run_command

import spynl.services.pdf
from spynl.services.pdf.endpoints import (
    DownloadOrderSchema,
    EmailOrderSchema,
    EOSDocumentEmailSchema,
    SalesReceiptDownloadSchema,
    SalesReceiptEmailSchema,
    TransitEmailSchema,
)
from spynl.services.reports.article_status import (
    ArticleStatusEmailQuery,
    ArticleStatusFilterQuery,
    ArticleStatusQuery,
)
from spynl.services.reports.retail_customer_sales import (
    RetailCustomerFilterQuery,
    RetailCustomerSalesQuery,
)
from spynl.services.reports.stock import StockFilter, StockPDFQuery, StockQuery
from spynl.services.reports.wholesale_customer_sales import (
    ParamSchema,
    WholesaleCustomerFilterQuery,
)


@cli.group()
def services():
    """Entrypoint for spynl services commands."""


@services.command(name='install-fonts')
def install_fonts():
    """Install fonts."""
    path = os.path.join(os.path.dirname(spynl.services.pdf.__file__), 'fonts', '*')
    install_path = os.path.join(os.path.expanduser('~'), '.fonts')
    try:
        os.mkdir(install_path)
    except FileExistsError:
        pass

    pattern = glob.glob(path)
    for font in pattern:
        shutil.copy(font, install_path)

    run_command('fc-cache -f -v')
    click.echo('Installed fonts successfully')


@services.command(name='install-gi')
@click.option(
    '-f',
    '--folder',
    default='/usr/lib/python3/dist-packages/gi',
    help=('The location of the system gi library'),
)
def install_gi(folder):
    """Install gi."""
    venv = os.environ.get('VIRTUAL_ENV')
    if not venv:
        fail('Command must be ran inside of a virtual environment.')
    site_packages = glob.glob('%s/lib/python*/site-packages/' % venv)[0]
    run_command('ln -sf %s %s' % (folder, site_packages), check=True)
    click.echo('Installed gi successfully to %s' % site_packages)


@folder_option
@services.command()
def generate_json_schemas(folder=None):
    # article status
    schema = JSONSchema().dump(ArticleStatusFilterQuery())
    dump_file('article_status_filter', schema, folder)
    schema = JSONSchema().dump(ArticleStatusQuery())
    dump_file('article_status', schema, folder)
    schema = JSONSchema().dump(ArticleStatusEmailQuery())
    dump_file('article_status_email', schema, folder)
    # retail customer
    schema = JSONSchema().dump(RetailCustomerFilterQuery())
    dump_file('retail_customer_sales_filter', schema, folder)
    schema = JSONSchema().dump(RetailCustomerSalesQuery())
    dump_file('retail_customer_sales', schema, folder)
    # wholesale customer
    schema = JSONSchema().dump(ParamSchema())
    dump_file('wholesale_customer_sales', schema, folder)
    schema = JSONSchema().dump(WholesaleCustomerFilterQuery())
    dump_file('wholesale_customer_sales_filter', schema, folder)
    # stock report
    schema = JSONSchema().dump(StockQuery(exclude=('filter.startDate',)))
    dump_file('stock', schema, folder)
    schema = JSONSchema().dump(StockPDFQuery(exclude=('filter.startDate',)))
    dump_file('stock_pdf', schema, folder)
    schema = JSONSchema().dump(StockFilter())
    dump_file('stock_filter', schema, folder)
    # non-report pdf endpoints:
    schema = JSONSchema().dump(SalesReceiptEmailSchema())
    dump_file('email_sales_receipt', schema, folder)
    schema = JSONSchema().dump(SalesReceiptDownloadSchema())
    dump_file('download_sales_receipt', schema, folder)
    schema = JSONSchema().dump(EmailOrderSchema())
    dump_file('email_sales_order_receipt', schema, folder)
    schema = JSONSchema().dump(DownloadOrderSchema())
    dump_file('download_sales_order_receipt', schema, folder)
    schema = JSONSchema().dump(EOSDocumentEmailSchema())
    dump_file('email_eos_document', schema, folder)
    schema = JSONSchema().dump(TransitEmailSchema())
    dump_file('email_transit_pdf', schema, folder)
