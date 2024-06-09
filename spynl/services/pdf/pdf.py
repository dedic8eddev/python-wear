"""
Functions for generating pdf's
"""

import datetime
import io
import os
from collections import OrderedDict

from pyramid.renderers import render
from weasyprint import CSS, HTML

from spynl_schemas import (
    EOSSchema,
    PackingListSchema,
    ReceivingSchema,
    SalesOrderSchema,
)

from spynl.main.utils import get_settings

from spynl.api.auth.utils import lookup_tenant

from spynl.services.pdf.utils import get_pdf_template_absolute_path


def generate_pdf(html, css=None):
    """
    Make a PDF from HTML (and CSS if provided).

    This function returns a StringIO object, and strings that contain
    any errors/warnings that were given by weasyprint or insert_barcodes.
    css can be a CSS string or a list of CSS strings
    """
    default_css = CSS(
        string='body { font-family: DejaVuSans, sans-serif; font-size: 8pt }'
    )

    css_sheets = [default_css]
    if isinstance(css, str):
        css_sheets.append(CSS(string=css))
    elif isinstance(css, list):
        [css_sheets.append(CSS(string=i)) for i in css]

    result = io.BytesIO()
    HTML(string=html).write_pdf(
        result, stylesheets=css_sheets, presentational_hints=True
    )
    result.seek(0)

    if os.getenv('DEBUG'):
        filename = 'test.pdf'
        HTML(string=html).write_pdf(
            filename, stylesheets=css_sheets, presentational_hints=True
        )

    return result


def generate_sales_order_pdf(request, order, settings, image_location, load_order=True):
    """
    generate a pdf for a sales order.
    """
    # Do not prepare for pdf if it was done already
    if load_order:
        order = SalesOrderSchema.prepare_for_pdf(
            order, request.db, request.requested_tenant_id
        )

    replacements = {
        'order': order,
        'article_image_location': image_location,
        'settings': settings,
    }

    html = render('sales_order.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('order.css')) as f:
        css = f.read()

    return generate_pdf(html, css=css)


def generate_packing_list_pdf(request, order, image_location):
    """
    generate a pdf for a packing list
    """
    order = PackingListSchema.prepare_for_pdf(
        order, request.db, request.requested_tenant_id
    )
    replacements = {'order': order, 'article_image_location': image_location}

    html = render('packing_list.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('packing_list.css')) as f:
        css = f.read()

    return generate_pdf(html, css=css)


def generate_receiving_pdf(request, receiving, image_location):
    """
    generate a pdf for a receivings order
    """
    tz = request.cached_user.get('tz', 'Europe/Amsterdam')
    locale = request.cached_user.get('language', 'nl-nl')[0:2]
    receiving = ReceivingSchema.prepare_for_pdf(
        receiving, db=request.db, tenant_id=request.requested_tenant_id
    )

    replacements = {
        'document': receiving,
        'article_image_location': image_location,
        'request': request,
        'tz': tz,
        'locale': locale,
    }

    html = render('receivings.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('receivings.css')) as f:
        css = f.read()

    return generate_pdf(html, css=css)


def generate_article_status_html_css(request, parameters, tenant, data):
    """
    generate an article status pdf
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    for address in tenant.get('addresses', []):
        if address.get('primary'):
            tenant['address'] = address
            break

    # Sort alphabetically for displaying what fields were requested in the
    # report header.
    parameters['filter'] = OrderedDict(
        (key, value)
        for key, value in sorted(
            parameters['filter'].items(),
            key=lambda x: parameters.get('columnMetadata', {})
            .get(x[0], {})
            .get('label', x[0]),
        )
    )
    replacements = {
        'data': data,
        'parameters': parameters,
        'tenant': tenant,
        'now': now,
        'user': request.cached_user,
    }
    html = render('reports/article_status.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('reports/report.css')) as f:
        css = f.read()

    return html, css


def generate_stock_html_css(request, parameters, tenant, data):
    """
    generate a stock report pdf
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    for address in tenant.get('addresses', []):
        if address.get('primary'):
            tenant['address'] = address
            break

    # Sort alphabetically for displaying what fields were requested in the
    # report header.
    parameters['filter'] = OrderedDict(
        (key, value)
        for key, value in sorted(
            parameters['filter'].items(),
            key=lambda x: parameters.get('columnMetadata', {})
            .get(x[0], {})
            .get('label', x[0]),
        )
    )

    replacements = {
        'data': data,
        'parameters': parameters,
        'tenant': tenant,
        'user': request.cached_user,
        'now': now,
        'ignore_start_date': True,
        'article_image_location': get_image_location(tenant.get('settings', {})),
    }
    html = render('reports/stock.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('reports/report.css')) as f:
        css = f.read()

    return html, css


def generate_eos_pdf(request, eos):
    """
    generate a pdf for an End of Shift document
    """
    tz = request.cached_user.get('tz', 'Europe/Amsterdam')
    locale = request.cached_user.get('language', 'nl-nl')[0:2]
    currency = (
        lookup_tenant(request.db, request.current_tenant_id)
        .get('settings', {})
        .get('currency', '')
    )

    eos = EOSSchema.prepare_for_pdf(eos)

    html = generate_eos_pdf_html(eos, request, locale, currency, tz)

    with open(get_pdf_template_absolute_path('base.css')) as f:
        base_css = f.read()
    with open(get_pdf_template_absolute_path('eos.css')) as f:
        css = f.read()

    return generate_pdf(html, css=[base_css, css])


def generate_eos_pdf_html(eos, request, locale, currency, tz):
    replacements = {'document': eos, 'locale': locale, 'currency': currency, 'tz': tz}
    return render('eos.jinja2', replacements, request=request)


def get_image_location(settings, sales=False):
    """get the image location from the tenant settings or generate the default"""
    image_root = settings.get('sales', {}).get('imageRoot')
    # If it's not a sales endpoint, don't use the sales setting:
    if not sales or not image_root:
        image_root = os.path.join(
            'https://cdn.{}/'.format(get_settings('spynl.domain')),
            settings.get('uploadDirectory'),
        )
    return os.path.join(image_root, 'images', 'size0/')


def generate_receipt_html_css(request, sale, parameters, user, tenant):
    """generatate the html and css for a sales receipt"""
    tz = user.get('tz', 'Europe/Amsterdam')
    locale = user.get('language', 'nl-nl')[0:2]
    currency = tenant.get('settings', {}).get('currency', 'EUR')
    replacements = {
        'sale': sale,
        'locale': locale,
        'currency': currency,
        'tz': tz,
        'parameters': parameters,
        'user': user,
    }
    html = render('receipt.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('base.css')) as f:
        base_css = f.read()

    with open(get_pdf_template_absolute_path('receipt.css')) as f:
        css = f.read()

    return html, [base_css, css]


def generate_transit_html_css(
    request, transit, from_warehouse, to_warehouse, user, tenant
):
    """generatate the html and css for a transit pdf"""
    tz = user.get('tz', 'Europe/Amsterdam')
    locale = user.get('language', 'nl-nl')[0:2]
    replacements = {
        'transit': transit,
        'locale': locale,
        'tz': tz,
        'from_warehouse': from_warehouse,
        'to_warehouse': to_warehouse,
    }
    html = render('transit.jinja2', replacements, request=request)

    with open(get_pdf_template_absolute_path('base.css')) as f:
        base_css = f.read()

    with open(get_pdf_template_absolute_path('transit.css')) as f:
        css = f.read()

    return html, [base_css, css]
