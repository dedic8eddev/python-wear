import json
import os

from bson import ObjectId

from spynl.api.auth.testutils import make_auth_header, mkuser

PATH = os.path.dirname(os.path.abspath(__file__))


def test_sales_add(app, spynl_data_db, monkeypatch):
    """test getting adding a sale with a token."""
    with open(f'{PATH}/data/transaction.json', 'r') as fob:
        sample_sale = json.loads(fob.read())

    monkeypatch.setattr('spynl.api.retail.resources.Sales.is_large_collection', False)
    userid = ObjectId()
    spynl_data_db.pymongo_db.tenants.insert_one(
        {'_id': '1', 'name': 'I. Tenant', 'active': True, 'settings': {}}
    )
    mkuser(spynl_data_db.pymongo_db, 'user', '00000000', ['1'], custom_id=userid)
    headers = make_auth_header(
        spynl_data_db, userid, '1', payload={'roles': ['pos-device']}
    )
    app.post_json('/sales/add', {'data': sample_sale}, headers=headers, status=200)
