import uuid

from marshmallow import fields, validate, validates

from spynl_schemas.fields import BleachedHTMLField
from spynl_schemas.shared_schemas import BaseSchema
from spynl_schemas.utils import BAD_CHOICE_MSG, COUNTRIES

country_options = [*COUNTRIES.keys(), 'default']


class OrderTermsSchema(BaseSchema):
    """This stores the terms of conditions for an order."""

    _id = fields.UUID(load_default=uuid.uuid4)
    orderPreviewText1 = BleachedHTMLField(
        load_default='', metadata={'description': 'Sender address or logo in HTML.'}
    )
    orderPreviewText2 = BleachedHTMLField(
        load_default='', metadata={'description': 'Footer text 2.'}
    )
    orderPreviewText3 = BleachedHTMLField(
        load_default='', metadata={'description': 'Footer text 3.'}
    )
    orderPreviewText4 = BleachedHTMLField(
        load_default='', metadata={'description': 'Footer text 4.'}
    )
    orderPreviewText5 = BleachedHTMLField(
        load_default='', metadata={'description': 'Terms and conditions document.'}
    )
    language = fields.String(load_default='default')
    country = fields.String(
        load_default='default',
        validate=validate.OneOf(country_options, error=BAD_CHOICE_MSG),
        metadata={'description': 'The country to which these terms apply.'},
    )

    active = fields.Constant(
        constant=True,
        metadata={
            'description': 'Order terms have active to be in line with all the other '
            'documents. However because order terms are actually deleted, active '
            'should always be True.',
            '_jsonschema_type_mapping': {
                'type': 'boolean',
                'default': True,
                'enum': [True],
            },
        },
    )

    @validates('language')
    def validate_language(self, value):
        if value != 'default':
            validate.Length(min=2)(value)
