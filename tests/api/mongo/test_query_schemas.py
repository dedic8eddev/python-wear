import datetime

import pytest
from bson import ObjectId
from marshmallow import ValidationError, validates_schema

from spynl.main.dateutils import date_format_str

from spynl.api.mongo.query_schemas import (
    FilterSchema,
    MongoQueryParamsSchema,
    SortSchema,
)


def test_old_style_sort():
    schema = SortSchema(many=True)
    assert schema.load([['a', 1], ['b', -1]]) == [('a', 1), ('b', -1)]


@pytest.mark.parametrize(
    'value',
    [
        [{'field': 'x', 'direction': -1}, {'field': 'y', 'direction': 1}],
        [{'field': 'x', 'direction': -1}],
        [{'field': 'x', 'direction': 1}],
        [{'field': 'x', 'direction': '1'}],
    ],
)
def test_sort(value):
    class SortSchema(MongoQueryParamsSchema):
        """overwrite tenant_id check"""

        @validates_schema
        def validate_tenant_id(self, data, **kwargs):
            pass

    try:
        SortSchema(only=('sort',)).load({'sort': value})
    except ValidationError as e:
        pytest.fail(e)


# Testing the filterschema
# ========================


def test_filter_without_active_or_id():
    # active defaults to "not False"
    assert FilterSchema(context={'tenant_id': '1'}).load({}) == {
        'tenant_id': {'$in': ['1']},
        'active': True,
    }


def test_filter_without_id():
    assert FilterSchema(context={'tenant_id': '1'}).load({'active': False}) == {
        'tenant_id': {'$in': ['1']},
        'active': False,
    }


def test_filter_with_id():
    # no check for active if requesting a specific document
    _id = ObjectId()
    assert FilterSchema(context={'tenant_id': '1'}).load({'_id': str(_id)}) == {
        'tenant_id': {'$in': ['1']},
        '_id': _id,
    }


# def test_filter_tenant_id_missing():
#     with pytest.raises(KeyError):
#         FilterSchema().load({})


# def test_filter_tenant_id_provided_but_ignored():
#     with pytest.raises(KeyError):
#         FilterSchema().load({'filter': {'tenant_id': '1'}})


def test_filter_tenant_id_provided_but_overridden_by_context():
    data = FilterSchema(context={'tenant_id': '1'}).load({'filter': {'tenant_id': '2'}})
    assert data['tenant_id'] == {'$in': ['1']}


def test_filter_tenant_id():
    data = FilterSchema(context=dict(tenant_id='1')).load({})
    assert data['tenant_id'] == {'$in': ['1']}


def test_daterange():
    input = {
        'startDate': '2017-01-01T23:00:00+0000',
        'endDate': '2017-01-02T23:00:00+0000',
        'startModifiedDate': '2018-01-01T23:00:00+0000',
        'endModifiedDate': '2018-01-02T23:00:00+0000',
    }
    data = FilterSchema(context=dict(tenant_id='1')).load(input)
    assert data['created.date'] == {
        '$gte': datetime.datetime.strptime(input['startDate'], date_format_str()),
        '$lte': datetime.datetime.strptime(input['endDate'], date_format_str()),
    }
    assert data['modified.date'] == {
        '$gte': datetime.datetime.strptime(
            input['startModifiedDate'], date_format_str()
        ),
        '$lte': datetime.datetime.strptime(input['endModifiedDate'], date_format_str()),
    }
    assert all(
        f not in data
        for f in ['startDate', 'endDate', 'startModifiedDate', 'endModifiedDate']
    )
