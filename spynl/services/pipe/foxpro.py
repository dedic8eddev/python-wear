"""Provide proxy functionality from Spynl to Softwear Foxpro legacy."""

from spynl_schemas import lookup

from spynl.locale import SpynlTranslationString as _

from spynl.main.exceptions import SpynlException
from spynl.main.utils import get_settings, get_user_info, required_args

from spynl.services.pipe.utils import piping


@piping
@required_args('query', 'function')
def get(request):
    """
    Get Foxpro url for user session.

    Ensure that Foxpro knows about this user session and
    assemble the complete URL.

    ---
    post:
      description: >
        Ensure that Foxpro knows about this user session and
        assemble the complete URL. No post data is needed.

        ### Parameters

        Parameter | Type   | Req.     | Description\n
        --------- | ------ | -------- | -----------\n
        function  | string | &#10004; | FoxPro function to call\n
        query     | object | &#10004; | The query for the foxpro function.

        ### Response

        JSON keys | Type | Description\n
        --------- | ------------ | -----------\n
        status       | string | 'ok' or 'error'\n
        message      | string | description of errors\n
        data         | object | The data reponse from FoxPro, \
                       serialized to JSON.

      tags:
        - pipe
    """
    # get settings
    fp_url = get_settings().get('spynl.pipe.fp_web_url')
    if not fp_url:
        raise SpynlException(_('no-foxpro-url'))

    if not isinstance(request.args['query'], dict):
        raise SpynlException('"query" should be an object')
    # check if we need to fetch the barcode from latest collection
    fetchBarcodeFromLatestCollection = lookup(
        request.db.tenants.find_one(
            {'_id': request.current_tenant_id}, {'settings': 1}
        ),
        'settings.fetchBarcodeFromLatestCollection',
    )
    if fetchBarcodeFromLatestCollection and request.args.get('function') == 'raptorsku':
        barcode = request.args.get('query')['barcode']
        # get user data from session
        sid = request.session.id
        # get tenant id
        tenant_id = request.session.get("tenant_id")
        if not barcode:
            raise SpynlException(
                _('validation-error'), developer_message='barcode is not provided'
            )
        url = (
            'https://latestcollection.fashion/data/'
            + '{}/sku?sid={}&id={}&transformer=getRaptorSku'.format(
                tenant_id, sid, barcode
            )
        )
        return url, None

    # Set up a list of key, value pairs to be parsed into a query string.
    payload = [
        ('function', request.args.get('function')),
        ('token', request.session.id),
        ('username', get_user_info(request)['username']),
        ('tenant_id', request.session.get('tenant_id')),
    ] + list(request.args.get('query', {}).items())

    query_string = '?' + '&'.join(['%s=%s' % (k, v) for k, v in payload])
    query_string += '&format=json'

    url = fp_url + query_string
    return url, None
