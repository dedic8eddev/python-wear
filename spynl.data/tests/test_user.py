import pytest
from marshmallow import ValidationError

from spynl_schemas import User


def test_inventory_user_should_be_allowed_to_have_no_email():
    data = {'roles': {'a': {'tenant': ['inventory-user']}}, 'type': 'standard'}
    User(only=['email', 'roles', 'type', 'tenant_id'], context={'tenant_id': 'a'}).load(
        data
    )


def test_non_inventory_user_should_not_be_allowed_to_have_no_email():
    data = {
        'roles': {'a': {'tenant': ['inventory-user', 'account-admin']}},
        'type': 'standard',
    }
    with pytest.raises(
        ValidationError, match='An email is required for standard users'
    ):
        User(
            only=['email', 'roles', 'type', 'tenant_id'], context={'tenant_id': 'a'}
        ).load(data)
