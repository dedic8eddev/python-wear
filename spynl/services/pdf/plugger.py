"""
plugger.py is used by spynl Plugins to say
which endspoints and resources it will use.
"""

from spynl.main.utils import add_jinja2_filters

from spynl.api.logistics.resources import PackingLists, SalesOrders
from spynl.api.retail.resources import EOS, Receiving, Sales, Transit

from spynl.services.pdf.endpoints import (
    download_eos_pdf,
    download_packing_list_pdf,
    download_receivings_pdf,
    download_sales_order_receipt,
    download_sales_receipt,
    email_eos_document,
    email_sales_order_receipt,
    email_sales_receipt,
    email_transit_pdf,
    preview_sales_order_receipt,
)


def includeme(config):
    """Add the function add as endpoint."""

    config.add_endpoint(email_sales_receipt, 'email', context=Sales, permission='read')
    config.add_endpoint(
        download_sales_receipt, 'download', context=Sales, permission='read'
    )
    config.add_endpoint(email_transit_pdf, 'email', context=Transit, permission='read')
    config.add_endpoint(
        email_sales_order_receipt, 'email', context=SalesOrders, permission='read'
    )
    config.add_endpoint(
        download_sales_order_receipt, 'download', context=SalesOrders, permission='read'
    )
    config.add_endpoint(
        preview_sales_order_receipt, 'preview', context=SalesOrders, permission='read'
    )
    config.add_endpoint(
        download_packing_list_pdf, 'download', context=PackingLists, permission='read'
    )

    config.add_endpoint(
        download_receivings_pdf, 'download', context=Receiving, permission='read'
    )

    config.add_endpoint(download_eos_pdf, 'download', context=EOS, permission='read')
    config.add_endpoint(email_eos_document, 'email', context=EOS, permission='read')

    config.add_jinja2_search_path('spynl.services.pdf:email-templates')
    config.add_jinja2_search_path('spynl.services.pdf:pdf-templates')

    add_jinja2_filters(
        config,
        {
            'translate': 'spynl.services.pdf.utils.non_babel_translate',
            'format_datetime': 'spynl.services.pdf.utils.format_datetime',
            'format_date': 'spynl.services.pdf.utils.format_date',
            'format_country': 'spynl.services.pdf.utils.format_country',
            'format_currency': 'spynl.services.pdf.utils.format_currency',
            'format_decimal': 'spynl.services.pdf.utils.format_decimal',
            'change_case': 'spynl.services.pdf.utils.change_case',
        },
    )
