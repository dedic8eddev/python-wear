""" Our custom fields """

import string

from bson.objectid import InvalidId, ObjectId
from marshmallow import fields, validate
from marshmallow.utils import missing as missing_

from spynl_schemas.utils import bleach_html

SAFE_CHARACTERS = string.ascii_letters + string.digits + '- '


class LabelField(fields.String):
    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data)
        validator = validate.ContainsOnly(SAFE_CHARACTERS)
        return validator(value)


class ObjectIdField(fields.Field):
    """ObjectId field that can dump and load objectids."""

    default_error_messages = {
        **fields.Field.default_error_messages,
        'type': 'Must be a valid ObjectId object.',
    }

    def _serialize(self, value, attr, obj, **kwargs):
        if value:
            return str(value)

    def _deserialize(self, value, attr, obj, **kwargs):
        try:
            return ObjectId(value)
        except (InvalidId, TypeError):
            raise self.make_error('type')

    def _jsonschema_type_mapping(self):
        return {'type': 'string', 'format': 'ObjectID'}


class BleachedHTMLField(fields.String):
    """bleach html fields"""

    # TODO: should also bleach on serialize?
    def _deserialize(self, value, attr, obj, **kwargs):
        value = super()._deserialize(value, attr, obj, **kwargs)
        return bleach_html(value)

    def _jsonschema_type_mapping(self):
        return {
            'type': 'string',
            'format': 'html',
            'field_description': 'Provided html will be bleached.',
        }


class LenientDateTimeField(fields.DateTime):
    """Datetime fields that allows none and treats empty string as such."""

    def __init__(self, *args, **kwargs):
        kwargs['allow_none'] = True
        super().__init__(*args, **kwargs)

    def _deserialize(self, value, attr, obj, **kwargs):
        if not value:
            return None
        return super()._deserialize(value, attr, obj, **kwargs)

    def _serialize(self, value, attr, obj, **kwargs):
        if not value:
            return None
        return super()._serialize(value, attr, obj, **kwargs)

    def _jsonschema_type_mapping(self):
        return {'type': 'string', 'format': 'date-time'}


class Nested(fields.Nested):
    """
    Field that will fill in nested before loading so nested missing fields will
    be initialized.

    This is needed because marshmallow changed how missing is treated in 3.0.0b9
    """

    def deserialize(self, value, attr=None, data=None, **kwargs):
        self._validate_missing(value)
        if value is missing_:
            _miss = self.load_default
            value = _miss() if callable(_miss) else _miss
        return super().deserialize(value, attr, data, **kwargs)

    def _jsonschema_type_mapping(self):
        return '_from_nested_schema'
