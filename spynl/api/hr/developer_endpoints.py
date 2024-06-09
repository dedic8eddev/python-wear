"""
Endpoints for making a developer's life easier
"""
from spynl.main.mail import send_template_email
from spynl.main.utils import required_args

from spynl.api.auth.apps_and_roles import APPLICATIONS
from spynl.api.auth.utils import app_url


@required_args('email')
def send_all_templates(request):
    """
    Endpoint for checking templates.

    ---

    post:
      description: >
        This endpoint can be used for checking all the existing email templates
        by developers. It sends mails with dummy replacements to the specified
        email address. (this means reset links will not work!)


        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        email     | string       | &#10004; | email to send the emails to\n
        templates | string       |          | if templates is given, we will
        send the templates specified (name without extension, comma separated)\n

        ### Response

        JSON keys    | Type   | Description\n
        ------------ | ------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors or success\n

      tags:
        - developer tools
    """
    # TODO: add a check to see if this actually sends all templates?

    # a dict of all templates and necessary replacements:
    templates = {
        'account_status_notification': [
            {
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Lastname',
                'activated': True,
            },
            {
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Lastname',
                'activated': False,
            },
        ],
        'application_access_change_notification': [
            {
                'application': APPLICATIONS['pos'],
                'tenant_name': 'Tenant A',
                'was_given': True,
                'recipient_fullname': 'Owner Lastname',
                'auth_user_username': 'owner_username',
            },
            {
                'application': APPLICATIONS['pos'],
                'tenant_name': 'Tenant A',
                'was_given': False,
                'recipient_fullname': 'Owner Lastname',
                'auth_user_username': 'owner_username',
            },
        ],
        'email_change_confirmation': [
            {
                'new_email_address': 'new@email.nl',
                'key': '123ABC8374873094',
                'app_url': app_url(request, 'www'),
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Fullname',
                'first': True,
            },
            {
                'new_email_address': 'new@email.nl',
                'key': '123ABC8374873094',
                'app_url': app_url(request, 'www'),
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Fullname',
                'first': False,
            },
        ],
        'email_change_notification': [
            {
                'new_email_address': 'new@email.nl',
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Fullname',
            },
            {
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Fullname',
                'tenant_name': 'Dummy Company',
                'email_removed': True,
            },
        ],
        'email_removal_notification_owners': [
            {
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Fullname',
                'tenant_name': 'Dummy Company',
                'removed_email': 'old@email.nl',
                'multiple_owners': False,
            },
            {
                'user_username': 'dummy_user',
                'user_fullname': 'Dummy Fullname',
                'tenant_name': 'Dummy Company',
                'removed_email': 'old@email.nl',
                'multiple_owners': True,
            },
        ],
        'invitation_to_connect': [
            {
                'user': 'Dummy Fullname',
                'user_message': 'Beste X\n, ik wil graag info met je delen.\n'
                '(message composed by user)',
                'id': '54646846543454',
                'key': 'fuheuhugah;uberuig',
                'app_url': app_url(request, 'www'),
            }
        ],
        'ownership_notification': [
            {
                'user_username': 'dummy_user',
                'tenant': 'Dummy Tenant',
                'recipient_fullname': 'Dummy Lastname',
                'was_given': True,
            },
            {
                'user_username': 'dummy_user',
                'tenant': 'Dummy Tenant',
                'recipient_fullname': 'Dummy Lastname',
                'was_given': False,
            },
        ],
        'password_change_notification': [
            {'user_username': 'dummy_username', 'user_greeting': 'Dummy Fullname'}
        ],
        'password_reset': [
            {
                'key': 'ifjeh45632154jhfdihiefsljf',
                'app_url': app_url(request, 'www'),
                'username': 'dummy_username',
                'user_greeting': 'Dummy Fullname',
                'first_reset': True,
            },
            {
                'key': 'ifjeh45632154jhfdihiefsljf',
                'app_url': app_url(request, 'www'),
                'username': 'dummy_username',
                'user_greeting': 'Dummy Fullname',
                'first_reset': False,
            },
        ],
        'username_change_notification': [
            {
                'fullname': 'fullname',
                'old_username': 'old_username',
                'new_username': 'new_username',
            }
        ],
        'tenant_document_updated': [
            {'tenant': 'foo tenant', 'fields': ['field1', 'field2']}
        ],
    }

    selected_templates = request.args.get('templates', templates.keys())
    email = request.args['email']
    for template, replacement_list in templates.items():
        if template in selected_templates:
            for replacements in replacement_list:
                send_template_email(
                    request,
                    email,
                    template_file=template,
                    replacements=replacements,
                    fail_silently=False,
                )

    return {'status': 'ok'}
