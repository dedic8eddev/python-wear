from marshmallow import Schema, fields

from spynl.services.reports.utils import default_filter_values


def test_default_filter_values():
    class Filter(Schema):
        not_a_column = fields.String(metadata={'column': False})
        a_column = fields.String()
        b_column = fields.String()
        no_filter_values = fields.String(metadata={'include_filter_values': False})

    data = {'a_column': ['a', 'b', 'c']}
    default_filter_values(data, Filter)
    assert data == {
        'a_column': ['a', 'b', 'c'],
        'b_column': [],
        'no_filter_values': None,
    }
