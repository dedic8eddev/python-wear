import string

import pytest
from bson.objectid import ObjectId
from marshmallow import Schema, ValidationError, fields

from spynl_schemas.fields import SAFE_CHARACTERS, LabelField, Nested, ObjectIdField


def test_nested_field():
    class A(Schema):
        x = fields.String(load_default='x', dump_default='x')
        y = fields.String(load_default='y', dump_default='z')
        z = fields.String()

    class B(Schema):
        a = Nested(A, load_default=dict, dump_default=dict)
        b = Nested(
            A,
            load_default=lambda: {'y': 'not y'},
            dump_default=lambda: {'y': 'not y'},
        )

        c = Nested(A)

    assert B().load({}) == {'a': {'x': 'x', 'y': 'y'}, 'b': {'x': 'x', 'y': 'not y'}}
    assert B().dump({}) == {'a': {'x': 'x', 'y': 'z'}, 'b': {'x': 'x', 'y': 'not y'}}


def test_object_id_serialize():
    oid = ObjectId()
    value = ObjectIdField().serialize('oid', {'oid': oid})
    assert value == str(oid)


def test_object_id_deserialize():
    oid = ObjectId()
    value = ObjectIdField().deserialize(str(oid))
    assert value == oid


def test_object_id_deserialize_error():
    with pytest.raises(ValidationError):
        ObjectIdField().deserialize('1')


@pytest.mark.parametrize(
    'label', [s for s in string.printable if s not in SAFE_CHARACTERS]
)
def test_label_field(label):
    class S(Schema):
        label = LabelField()

    schema = S()
    with pytest.raises(ValidationError):
        schema.load({'label': label})
