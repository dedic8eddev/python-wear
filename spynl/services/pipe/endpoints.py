import requests

from spynl_schemas import lookup

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException
from spynl.main.utils import get_settings, required_args


@required_args('url')
def url_shortener(request):
    """
    Shorten a url

    ---
    post:
      description: >
        Set your current tenant on spynl on FoxPro.

        ### Parameters

        Parameter | Type         | Req.     | Description\n
        --------- | ------------ | -------- | -----------\n
        url       | string       | &#10004; | url that needs to be shortened\n

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status    | string | 'ok' or 'error'\n
        short_url | string | the shortened url

      tags:
        - pipe
    """
    bitly_token = get_settings().get('spynl.pipe.bitly_access_token')

    response = requests.post(
        'https://api-ssl.bitly.com/v4/shorten',
        json={'long_url': request.args['url']},
        headers={'Authorization': 'Bearer {}'.format(bitly_token)},
    )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        raise SpynlException(
            _('validation-error'), developer_message=response.json().get('description')
        )

    bitly_response = response.json()
    return {'short_url': bitly_response['link'], 'long_url': bitly_response['long_url']}


@required_args('payNLPayload')
def pay_nl(request):
    """
    send a pay.nl request

    ---
    post:
      description: >
        Looks up the tenant payNLToken to send in a pay.nl request. Can only be used by
        users that have all the pay.nl settings configured (pinProvide, payNLDeviceId
        and payNLstoreId) if their tenant has the payNLToken setting.

        The response is the pay.nl response.
      parameters:
        - name: body
          in: body
          required: true
          schema:
            type: object
            properties:
              payNLPayload:
                type: object
                description: The payload for the pay.nl request.
            required:
              - payNLPayload
      tags:
        - pipe
    """
    user_settings = request.cached_user.get('settings')
    pay_nl_token = user_settings.get('payNLToken')
    if not pay_nl_token:
        pay_nl_token = lookup(
            request.db.tenants.find_one(
                {'_id': request.current_tenant_id}, {'settings': 1}
            ),
            'settings.payNLToken',
        )

    # settings cannot be removed, so we check if they are truthy:
    if not (
        user_settings.get('pinProvider') == 'payNL'
        and user_settings.get('payNLDeviceId')
        and user_settings.get('payNLStoreId')
        and pay_nl_token
    ):
        # TODO: add translation
        raise SpynlException('Pay.nl is not configured for this user')

    return pay_nl_request(pay_nl_token, request.args['payNLPayload'])


def pay_nl_request(token, payload):
    """send request to pay.nl"""
    response = requests.post(
        'https://rest-api.pay.nl/v13/Transaction/start/json',
        data=payload,
        headers={'Authorization': 'Basic {}'.format(token)},
    )
    try:
        response.raise_for_status()
    except requests.HTTPError:
        # TODO: add translation
        raise SpynlException(
            'Something went wrong with pay.nl',
            developer_message=response.json().get('description'),
        )
    return response.json()
