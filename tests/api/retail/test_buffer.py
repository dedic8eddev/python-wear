import pytest
from bson import ObjectId

from spynl.api.auth.testutils import mkuser

TENANT_ID = '1'
USERNAME = 'test_buffer_user'
PASSWORD = '00000000'
USER_ID = ObjectId()


@pytest.fixture(autouse=True, scope='function')
def database_setup(app, spynl_data_db, monkeypatch):
    db = spynl_data_db
    db.tenants.insert_one({'_id': TENANT_ID, 'applications': ['pos'], 'settings': {}})
    mkuser(
        db.pymongo_db,
        USERNAME,
        PASSWORD,
        [TENANT_ID],
        tenant_roles={TENANT_ID: 'pos-device'},
        custom_id=USER_ID,
    )
    app.get('/login?username=%s&password=%s' % (USERNAME, PASSWORD))
    yield db
    app.get('/logout')


def test_save_empty_buffer(app):
    app.post_json('/buffer/add', {'data': {}}, status=400)


def test_save_buffer(app, spynl_data_db):
    resp = app.post_json('/buffer/add', {'data': BUFFER})
    db_content = list(spynl_data_db.buffer.find())
    assert len(db_content) == 1 and str(db_content[0]['_id']) == resp.json['data'][0]


def test_save_bad_buffer(app):
    bad_buffer = {**BUFFER, 'receipt': None}
    app.post_json('/buffer/add', {'data': bad_buffer}, status=400)


BUFFER = {
    "cashier": {
        "fullname": "Bobby Drake",
        "id": "54dcb4e8c8d4b6002ad6353c",
        "name": "Bobby",
    },
    "customer": {"firstname": "Mohammed", "lastname": "Kareem"},
    "receipt": [
        {
            "articleCode": "B.Drake Coat",
            "articleDescription": "Drake Coat",
            "barcode": "10",
            "brand": "My God",
            "category": "barcode",
            "changeDisc": False,
            "color": "antelopeaged washed",
            "found": True,
            "group": None,
            "nettPrice": 250.5,
            "price": 250.5,
            "qty": 1,
            "sizeLabel": "-",
            "vat": 21,
        },
        {
            "articleCode": "vermaak30",
            "articleDescription": "Leer Jack Mouwen Korter",
            "barcode": "30",
            "brand": "Maddox",
            "category": "barcode",
            "changeDisc": False,
            "color": "niet van toepassing",
            "found": True,
            "group": None,
            "nettPrice": 30,
            "price": 30,
            "qty": 1,
            "sizeLabel": "-",
            "vat": 21,
        },
    ],
    "overallReceiptDiscount": 0.0,
    "shop": {"id": "51"},
}
