import pytest
from marshmallow import ValidationError

from spynl_schemas.cashier import Cashier

CASHIER = {
    'name': '123',
    'fullname': 'a cashier',
    'password': 'password',
    'tenant_id': ['12345'],
}


def test_set_acls():
    cashier = Cashier().load(CASHIER)
    assert not cashier['acls']['pos_menu_acl']
    cashier = Cashier().load({**CASHIER, 'type': 'admin'})
    assert cashier['acls']['pos_menu_acl']


def test_set_acls_unkowns_type():
    with pytest.raises(ValidationError):
        Cashier().load({**CASHIER, 'type': 'bla'})
