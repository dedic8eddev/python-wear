import pytest
from marshmallow import ValidationError, fields

from spynl_schemas.fields import Nested
from spynl_schemas.shared_schemas import DeleteSettings, ProductSchema, Schema


class BaseTestSettings(Schema):
    one = fields.String()
    two = fields.String(metadata={'roles': {'role1'}})
    three = fields.String(metadata={'roles': {'role2'}})
    four = fields.String(metadata={'can_delete': False})


class ExampleSettings(BaseTestSettings):
    five = Nested(BaseTestSettings)
    six = Nested(BaseTestSettings, metadata={'roles': {'role1'}})
    seven = Nested(BaseTestSettings, metadata={'roles': {'role2'}})
    eight = Nested(BaseTestSettings, metadata={'can_delete': False})


@pytest.mark.parametrize(
    'settings,roles,valid,message',
    [
        (
            [
                'one',
                'two',
                'five',
                'six',
                'five.one',
                'five.two',
                'six.one',
                'six.two',
                'eight.one',
                'eight.two',
                'doesnotexist',
            ],
            {'role1'},
            True,
            None,
        ),
        (
            ['three', 'five.three', 'seven'],
            {'role1'},
            False,  # fail because of roles
            'You do not have rights to edit this setting',
        ),
        (
            ['four', 'eight', 'five.four'],
            {'role1'},
            False,  # fail because of 'can_delete'
            'This setting cannot be deleted',
        ),
    ],
)
def test_delete_settings(settings, roles, valid, message):
    if valid:
        DeleteSettings(context={'roles': {'role1'}, 'schema': ExampleSettings}).load(
            {'settings': settings}
        )
    else:
        with pytest.raises(ValidationError) as e:
            DeleteSettings(
                context={'roles': {'role1'}, 'schema': ExampleSettings}
            ).load({'settings': settings})
        assert all(message == e.value.messages[s] for s in settings)


def test_convert_properties_to_dict():
    product = {
        'properties': [
            {'name': 'bla', 'value': 'bla'},
            {'name': 'bla2', 'value': 'bla2'},
        ]
    }
    ProductSchema.convert_properties_to_dict(product)
    assert product['properties'] == {'bla': 'bla', 'bla2': 'bla2'}
