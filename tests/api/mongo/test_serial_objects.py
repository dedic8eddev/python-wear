""" Tests for serialization as defined in spynl.mongo """

import datetime
import uuid

import pytest
from bson import ObjectId
from pyramid.testing import DummyRequest, setUp, tearDown

from spynl.main import serial
from spynl.main.dateutils import date_from_str, date_to_str
from spynl.main.exceptions import SpynlException
from spynl.main.serial.objects import add_decode_function

from spynl.api.mongo import MongoResource
from spynl.api.mongo.serial_objects import decode_date, decode_id


@pytest.fixture(scope="module", autouse=True)
def setup():
    """Add some settings to work outside of a request context."""
    config = setUp()
    add_decode_function(
        config,
        decode_id,
        ['_id', '_uuid', 'created.user_id', 'modified.user_id', 'userid'],
    )
    add_decode_function(
        config,
        decode_date,
        ['date', 'created.date', 'modified.date', 'periodStart', 'periodEnd'],
    )
    yield
    tearDown()


class MyResource(MongoResource):
    """A resource class we use for testing deserialisations"""

    id_class = [uuid.UUID, ObjectId]


def test_json_loads_ids():
    """Test incoming ObjectIDs and UUIDs."""
    uuid_a, uuid_b = (uuid.uuid4(), uuid.uuid4())
    objid_a, objid_b = ObjectId(), ObjectId()
    data_in = '{"myID": "%s", "_uuid": "%s", "_id": "%s", "_idd": "%s"}' % (
        uuid_a,
        uuid_b,
        objid_a,
        objid_b,
    )
    assert serial.json.loads(data_in, context=MyResource(DummyRequest())) == {
        'myID': str(uuid_a),
        '_uuid': uuid_b,
        '_id': objid_a,
        '_idd': str(objid_b),
    }


def test_json_loads_objectids_with_operators():
    """Test objectid with operators (json loads)."""
    oid1 = ObjectId()
    strid = 'IAMJUSTASTRING_1212_DEALWITHIT'
    oid2 = ObjectId()
    in_string = (
        '{"_id": {"$in": ["'
        + str(oid1)
        + '", "'
        + strid
        + '", "'
        + str(oid2)
        + '"], "$nin": ["'
        + str(oid1)
        + '"]}}'
    )
    # MongoResource will fallback to str, so strid will cause no trouble
    assert serial.json.loads(in_string, context=MongoResource(DummyRequest())) == dict(
        _id={'$in': [oid1, strid, oid2], '$nin': [oid1]}
    )
    # MyResource does not accept strid
    with pytest.raises(SpynlException) as se:
        serial.json.loads(in_string, context=MyResource(DummyRequest()))
    assert 'parse-value-exception-any-class' in str(se.value)


def test_json_loads_uuids_with_operators():
    """Test uuid with operators (we use type 4, but type1 is no problem)."""
    uuid_a, uuid_b, uuid_c = uuid.uuid4(), uuid.uuid1(), uuid.uuid4()
    in_string = (
        '{"_uuid": {"$in": ["'
        + str(uuid_a)
        + '", "'
        + str(uuid_b)
        + '", "'
        + str(uuid_c)
        + '"], "$nin": ["'
        + str(uuid_a)
        + '"]}}'
    )
    assert serial.json.loads(in_string, context=MyResource(DummyRequest())) == dict(
        _uuid={'$in': [uuid_a, uuid_b, uuid_c], '$nin': [uuid_a]}
    )


def test_json_loads_invalid_id():
    """Test some invalid id field values."""
    with pytest.raises(serial.MalformedRequestException) as mre:
        serial.json.loads('{"_uuid": 123}')
    assert 'malformed-field-not-string' in repr(mre.value)
    with pytest.raises(serial.MalformedRequestException) as mre:
        serial.json.loads('{"_id": {"$in": "%s"}}' % uuid.uuid4())
    assert 'malformed-field-not-list' in repr(mre.value)


def test_json_loads_operator_date():
    """Test operator date (json loads)."""
    day1 = datetime.datetime(2014, 9, 16)
    day2 = datetime.datetime(2014, 9, 18)
    d1str = date_to_str(day1)
    d2str = date_to_str(day2)
    data_in = '{"created.date": {"$gt": "' + d1str + '", "$lt": "' + d2str + '"}}'
    assert serial.json.loads(data_in) == {
        'created.date': {'$gt': date_from_str(d1str), '$lt': date_from_str(d2str)}
    }


def test_json_loads_mongofield_date():
    """Test if a field which starts with "$" gets ingored."""
    data_in = '{"date": "$_id.period"}'
    assert serial.json.loads(data_in) == {'date': '$_id.period'}
    data_in = '{"date": "_id.period"}'
    with pytest.raises(serial.MalformedRequestException):
        serial.json.loads(data_in)


def test_json_loads_operator_exists_date():
    """Test if json loads sees operator exists."""
    data_in = '{"created.date": {"$exists": true}}'
    assert serial.json.loads(data_in) == {'created.date': {'$exists': True}}


def test_json_loads_operator_sort_date():
    """Test operator sort date (json loads)."""
    data_in = '{"sort": [["created.date", 1]]}'
    assert serial.json.loads(data_in) == {"sort": [["created.date", 1]]}


def test_json_dumps_id():
    """Test serialising UUIDs and ObjectIds."""
    uuid_a = uuid.uuid4()
    assert serial.json.dumps(uuid_a) == '"' + str(uuid_a) + '"'
    uuid_b = uuid.uuid1()
    assert serial.json.dumps(uuid_b) == '"' + str(uuid_b) + '"'
    oid = ObjectId()
    assert serial.json.dumps({'_id': oid}) == '{"_id": "' + str(oid) + '"}'
    assert (
        serial.json.dumps({'created.userid': oid})
        == '{"created.userid": "' + str(oid) + '"}'
    )


def test_json_dumps_id_with_operator():
    """Test id dumping with operator (json.dumps)."""
    uuid_a = uuid.uuid4()
    oid_a = ObjectId()
    assert (
        serial.json.dumps({'_id': {'$in': [uuid_a, oid_a]}})
        == '{"_id": {"$in": ["' + str(uuid_a) + '", "' + str(oid_a) + '"]}}'
    )


def test_csv_dumps_objectid():
    """Test objecid (csv dumps)."""
    oid = ObjectId()
    response = serial.csv.dumps({'data': [{'_id': oid}]})
    assert response.split("\n")[1].strip('"\r') == str(oid)
