"""
Schemas used for handling request parameters.
"""

from marshmallow import (
    ValidationError,
    fields,
    post_load,
    pre_load,
    validate,
    validates_schema,
)
from marshmallow.validate import Range

from spynl_schemas import Schema
from spynl_schemas.fields import Nested, ObjectIdField


class FilterSchema(Schema):
    """Schema for the filter in the request params."""

    _id = ObjectIdField()
    active = fields.Boolean()
    startDate = fields.DateTime()
    endDate = fields.DateTime()
    startModifiedDate = fields.DateTime()
    endModifiedDate = fields.DateTime()

    @post_load
    def handle_tenant_id(self, data, **kwargs):
        # NOTE our callbacks should take care of this.
        if 'tenant_id' in self.context:
            tenant_id = self.context['tenant_id']
            data.update({'tenant_id': {'$in': [tenant_id]}})
        return data

    @post_load
    def handle_date_range(self, data, **kwargs):
        created = {}
        modified = {}

        for daterange, field, operator in [
            (created, 'startDate', '$gte'),
            (created, 'endDate', '$lte'),
            (modified, 'startModifiedDate', '$gte'),
            (modified, 'endModifiedDate', '$lte'),
        ]:
            if field in data:
                daterange[operator] = data.pop(field)

        if created:
            data['created.date'] = created

        if modified:
            data['modified.date'] = modified

        return data

    @post_load
    def handle_active(self, data, **kwargs):
        """
        A lot of collections use the convention that if active is not present,
        the document is considered active.
        """
        if '_id' in data:
            return data
        data.setdefault('active', True)
        return data


class SortSchema(Schema):
    field = fields.String(required=True)
    direction = fields.Integer(
        validate=validate.OneOf([1, -1]),
        metadata={
            'description': 'The direction in which to order. \n1 -> ASCENDING\n'
            '-1 -> DESCENDING\n'
        },
    )

    @pre_load
    def preprocess(self, data, **kwargs):
        if isinstance(data, (list, tuple)):
            data = {'field': data[0], 'direction': data[1]}
        return data

    @post_load
    def postprocess(self, data, **kwargs):
        # Mongo expects 2-tuples (field, direction)
        return (data['field'], data['direction'])


class MongoQueryParamsSchema(Schema):
    """Generic schema to handle request parameters."""

    limit = fields.Integer(validate=[Range(min=0)])
    skip = fields.Integer(validate=[Range(min=0)])
    projection = fields.List(fields.String, data_key='fields')
    sort = Nested(
        SortSchema, many=True, metadata={'description': 'A list of fields to sort by.'}
    )

    @validates_schema
    def validate_tenant_id(self, data, **kwargs):
        """
        This is not a proper security check. This is a check to make sure all
        subclassed schemas have their filter properly configured to add the
        tenant id
        """
        if not data.get('filter', {}).get('tenant_id'):
            # cryptic error, we do not want to expose security information
            raise ValidationError('Wrong schema configuration')

    @post_load
    def set_projection(self, data, **kwargs):
        """
        Added as a post load instead of load_default so it can be overwritten by child
        classes.
        """
        if 'projection' not in data:
            data['projection'] = {'modified_history': 0}
        return data


def format_documentation_possibilities(label, possibilities):
    """Helper function for listing fields/groups in documentation."""
    return 'The following {} are allowed: {}'.format(
        label, ', '.join('`{}`'.format(field) for field in possibilities)
    )
