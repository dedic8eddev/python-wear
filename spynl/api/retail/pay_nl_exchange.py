from marshmallow import ValidationError


# https://docs.pay.nl/developers#exchange-parameters
def exchange(request):
    """
    This endpoint is called by pay.nl.

    It will save whatever it provided through query params. The authentication
    is based on an IP whitelist.

    ---
    post:
      description: >
        It will save whatever is passed in the json body.
      responses:
        200:
          description: success
          examples:
            text/plain:
                TRUE
    get:
      description: >
        It will save whatever is passed in the query params
      responses:
        200:
          description: success
          examples:
            text/plain:
                TRUE
    tags:
      - pipe
    """

    # if request.remote_addr not in get_settings('spynl.pay_nl.ip_whitelist'):
    if request.method == 'GET':
        request.db.pay_nl_exchange.insert_one(request.GET.mixed())
    elif request.json_payload:
        request.db.pay_nl_exchange.insert_one(request.json_payload)
    else:
        raise ValidationError('No payload')

    response = request.response
    response.content_type = 'text/plain'
    response.text = 'TRUE'
    return response
