"""Define functions to send emails."""

import re

import html2text
from jinja2 import Template, TemplateNotFound
from pyramid.renderers import render
from pyramid_mailer import get_mailer
from pyramid_mailer.message import Attachment, Message

from spynl.main.exceptions import EmailRecipientNotGiven, EmailTemplateNotFound
from spynl.main.utils import get_logger, get_settings

DEFAULT_HTML_TEMPLATE = '''
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
                        "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
      <head>
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
        <title>{{subject}}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      </head>
      <body style="margin: 0; padding: 0;">
        <!-- Spynl Default Email Template -->
        <table align="center" cellpadding="0" cellspacing="0" width="400">
        <tr>
          <td align="center" bgcolor="#fff" style="padding: 40px 0 30px 0;"
              style="color: #153643; font-family: Arial, sans-serif;
                     font-size: 16px; line-height: 20px;">
            {{content_string}}
          </td>
        </tr>
        </table>
      </body>
    </html>'''


def _sendmail(
    request,
    recipients,
    subject,
    plain_body,
    html_body=None,
    sender=None,
    cc=None,
    bcc=None,
    attachments=None,
    fail_silently=True,
    mailer=None,
    reply_to=None,
    sender_name=None,
):
    """
    Send a mail using the pyramid mailer. This function also makes sure
    that if Spynl is not in a production environment, mail is sent to a dummy
    email address.

    :param Request request: the original request
    :param string recipients: addressees
    :param string subject: subject of mail
    :param string plain_body: content of mail
    :param string html_body: html content of mail
    :param string sender: senders address (optional,
                          default: no_reply@<spynl.domain>)
    :param string sender_name: sender name)
    :param [Attachment] attachments: attachments (optional)
    :param bool fail_silently: keep quiet when connection errors happen
    :param pyramid_mailer.Mailer mailer: mailer object (optional)
    """
    settings = get_settings()
    logger = get_logger()

    if mailer is None:
        mailer = get_mailer(request)

    if not sender:
        sender = settings.get('mail.sender')
        if not sender:
            domain = settings.get('spynl.domain', 'example.com')
            sender = 'no_reply@{}'.format(domain)

    sender = str(sender)
    if not recipients:
        if not fail_silently:
            raise EmailRecipientNotGiven()
        elif settings.get('mail.dummy_recipient'):
            recipients = [settings.get('mail.dummy_recipient')]
            logger.info(
                "I will send this email to %s instead of %s.",
                settings.get('mail.dummy_recipient'),
                recipients,
            )
        else:
            return False

    if isinstance(recipients, str):
        recipients = [recipients]

    subject = str(subject).rstrip()

    # set Reply-To header if needed:
    extra_headers = {}
    if reply_to:
        extra_headers['Reply-To'] = reply_to
    if sender_name:
        # sanitize sender name to make sure we do not get bad headers or
        # unverified email errors.
        sender_name = re.sub('[\n<>@]', ' ', sender_name).strip()
        extra_headers['From'] = '{} <{}>'.format(sender_name, sender)
    message = Message(
        sender=sender,
        recipients=recipients,
        subject=subject,
        body=plain_body,
        html=html_body,
        cc=cc,
        bcc=bcc,
        extra_headers=extra_headers,
    )
    if attachments:
        for attachment in attachments:
            message.attach(attachment)

    try:
        message.validate()
        logger.info(
            'Sending email titled "%s" to %s from %s', subject, recipients, sender
        )
        # Always set fail_silently to false, so we can log the
        # exception
        mailer.send_immediately(message, fail_silently=False)
    except Exception as e:
        if fail_silently:
            logger.exception(e)
            return False
        else:
            raise e

    return True


def send_template_email(
    request,
    recipient,
    template_string=None,
    template_file=None,
    replacements=None,
    subject='',
    fail_silently=True,
    mailer=None,
    cc=None,
    bcc=None,
    attachments=None,
    sender=None,
    reply_to=None,
    sender_name=None,
    extension='.jinja2',
):
    """
    Send email using a html template.

    The email's content (which can contain HTML code) is defined by a Jinja
    template. This content template can be given either by filename
    <template_file> (absolute path, without jinja2 extension) or directly in
    string form <template_string>. In both cases, the email content gets
    wrapped by a base
    template which defines a consistent layout. The base template to use is
    defined by a string type setting:
        `base_email_template: absolute path of template
    If the "base template" cannot be loaded the <DEFAULT_HTML_TEMPLATE> is
    used.
    Replacements can be send in to customise the email content.
    If no html or plain text was constructed in the end, replacements are being
    used to construct a basic text to be send as an email.

    If a template file is given, we assume that the file ends with .jinja2, and
    that there is a companion file .subject.jinja2 that defines the subject.
    You can specify a different extension if needed (including the dot).
    """
    if (template_string is None and template_file is None) or (
        template_string is not None and template_file is not None
    ):
        raise Exception('One of <template_string> or <template_file> must be given.')
    text_body = ''
    if not replacements:
        replacements = {}

    if template_file is not None:
        try:
            html_body = render(template_file + extension, replacements, request=request)
            if not subject:
                subject = render(
                    template_file + '.subject' + extension,
                    replacements,
                    request=request,
                )
                subject = subject.replace('\n', '')
        except TemplateNotFound:
            raise EmailTemplateNotFound(template_file)
    else:
        replacements['content_string'] = Template(template_string).render(
            **replacements
        )
        # Render the base template with the content of the given template
        base_template = get_settings().get('base_email_template')
        if base_template is not None:
            html_body = render(base_template, replacements, request=request)
        else:
            html_body = Template(DEFAULT_HTML_TEMPLATE).render(**replacements)

    html_body = html_body.replace('\n', '')

    text_maker = html2text.HTML2Text()
    text_maker.ignore_images = True
    text_maker.ignore_tables = True
    text_maker.wrap_links = False
    text_maker.use_automatic_links = False
    text_maker.body_width = 0
    text_body = text_maker.handle(html_body)

    text_body = Attachment(
        data=text_body,
        transfer_encoding="base64",
        content_type="text/plain; charset=UTF-8",
        disposition='inline',
    )
    html_body = Attachment(
        data=html_body,
        transfer_encoding="base64",
        content_type="text/html; charset=UTF-8",
        disposition='inline',
    )

    if not text_body and not html_body:
        str_replacements = '\n'.join(
            ['{}: {}'.format(key, value) for key, value in replacements.items()]
        )
        text_body = 'Your account has been changed.\n' + str_replacements
        template = Template(DEFAULT_HTML_TEMPLATE)
        replacements.update(subject=subject, content=text_body)
        html_body = template.render(**replacements)
        get_logger(__name__).error(
            'Body was not found in body_string or email template: %s', template
        )

    return _sendmail(
        request,
        recipient,
        subject,
        text_body,
        html_body,
        fail_silently=fail_silently,
        mailer=mailer,
        cc=cc,
        bcc=bcc,
        attachments=attachments,
        sender=sender,
        reply_to=reply_to,
        sender_name=sender_name,
    )
