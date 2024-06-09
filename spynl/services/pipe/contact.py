"""
Endpoint for contacting marketing
"""

import textwrap

from spynl.main.mail import send_template_email
from spynl.main.utils import get_settings, required_args


@required_args('email', 'name', 'subject', 'message')
def contact_us(request):
    """
    Endpoint for a contact us form.

    ---
    post:
      tags:
        - services
      description: >
        This endpoint will send an email to the marketing email address.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        email     | string       | &#10004; | email of contacter\n
        name      | string       | &#10004; | name of contacter\n
        subject   | string       | &#10004; | subject \n
        message   | string       | &#10004; | message or question\n
        phone     | string       |          | phone number of contacter\n
        category  | string       |          | type of company\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
    """
    args = request.args

    subject = 'SoftwearConnect contact form: {}'.format(args['subject'])

    body = '''\
    E-mail: {email}
    Name: {name}
    Phonenumber: {phone}
    Category: {category}

    Message:
    {message}\
    '''.format(
        email=args['email'],
        name=args['name'],
        phone=args.get('phone', '-'),
        category=args.get('category', '-'),
        message=args['message'],
    )

    send_template_email(
        request,
        get_settings().get('spynl.pipe.marketing_email', 'marketing@softwear.nl'),
        template_string=textwrap.dedent(body),
        subject=subject,
        reply_to=args['email'],
        fail_silently=False,
    )

    return {'status': 'ok'}
