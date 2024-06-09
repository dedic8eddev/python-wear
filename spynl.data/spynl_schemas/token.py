from marshmallow import fields, post_dump

from spynl_schemas.fields import ObjectIdField
from spynl_schemas.shared_schemas import Schema


class TokenSchema(Schema):
    """
    This token schema is used to dump out a response. It is not used to
    validate incoming data.
    """

    _id = fields.UUID(required=True)
    tenant_id = fields.String(required=True)
    token = fields.UUID(required=True)
    created = fields.Dict(required=True)
    modified = fields.Dict(required=True)
    revoked = fields.Boolean(required=True)
    description = fields.String()
    user_id = ObjectIdField(
        metadata={'description': 'Refers to the user the token is created for'}
    )

    @post_dump
    def obfuscate(self, data, **kwargs):
        if self.context.get('obfuscate'):
            data['token'] = '********%s' % data['token'][-10:]
        return data
