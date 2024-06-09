"""Tests for the verify_email endpoint."""

import pytest
from bson import ObjectId
from pyramid.testing import DummyRequest

from spynl.main.exceptions import MissingParameter

from spynl.api.auth.authentication import scramble_password
from spynl.api.auth.exceptions import Forbidden
from spynl.api.auth.keys import store_key
from spynl.api.hr.user_endpoints import verify_email

UID = ObjectId()


@pytest.fixture
def set_db(db):
    """Populate database with data."""
    db.users.insert_one(
        {
            '_id': UID,
            'email': 'maddoxx.aveen@softwear.nl',
            'fullname': 'Maddoxx Aveen',
            'email_verify_pending': True,
            'tenant_id': ['91537'],
            'password_hash': scramble_password('aveen', 'aveen', '2'),
            'password_salt': 'aveen',
            'hash_type': '2',
            'active': True,
        }
    )


@pytest.fixture()
def dummy_request(spynl_data_db):
    drequest = DummyRequest(
        remote_addr='dummy_ip',
        current_tenant_id='_',
        requested_tenant_id='_',
        db=spynl_data_db,
    )
    drequest.args = {}
    return drequest


def test_by_not_passing_any_argument_to_the_request(config, dummy_request):
    """Dont pass any argument and request verify email address."""
    with pytest.raises(MissingParameter) as excinfo:
        verify_email(dummy_request)
    assert excinfo.value.args[0] == 'email'


def test_by_not_passing_email_argument(config, dummy_request):
    """Dont pass email argument."""
    dummy_request.args = {'key': '$3fj87'}
    with pytest.raises(MissingParameter) as excinfo:
        verify_email(dummy_request)
    assert excinfo.value.args[0] == 'email'


def test_by_not_passing_key_argument(config, dummy_request):
    """Dont pass key argument."""
    dummy_request.args = {'email': 'test@test.com'}
    with pytest.raises(MissingParameter) as excinfo:
        verify_email(dummy_request)
    assert excinfo.value.args[0] == 'key'


@pytest.mark.parametrize(
    'email,exc_msg',
    [('', 'The email address does not seem to be valid.'), (None, 'missing-parameter')],
)
def test_by_passing_empty_string_as_email(config, dummy_request, email, exc_msg):
    """Email should be validated before proceeding."""
    dummy_request.args = {'email': email, 'key': '123'}
    with pytest.raises(Exception, match=exc_msg) as excinfo:
        verify_email(dummy_request)
    assert str(excinfo.value) == exc_msg


def test_when_passed_email_doesnt_belong_to_existing_user(config, dummy_request):
    """When requesting verifying email, this email has to belong to a user."""
    dummy_request.args = {'email': 'test@test.com', 'key': '$12*345'}
    with pytest.raises(Forbidden):
        verify_email(dummy_request)


def test_when_user_has_pending_false(config, set_db, db, dummy_request, spynl_data_db):
    """Trying to verify a verified email should be forbidden."""
    key = store_key(spynl_data_db, UID, 'change-email', 3600)
    db.users.update_one({'_id': UID}, {'$set': {'email_verify_pending': False}})
    dummy_request.args = {'email': 'maddoxx.aveen@softwear.nl', 'key': key}
    with pytest.raises(Forbidden):
        verify_email(dummy_request)


def test_when_key_is_not_valid(config, set_db, dummy_request):
    """When a key is expired/not valid it should complain."""
    dummy_request.args = {'email': 'maddoxx.aveen@softwear.nl', 'key': '$12*345'}
    with pytest.raises(Forbidden):
        verify_email(dummy_request)


def test_after_verification_pending_becomes_False(
    config, set_db, db, dummy_request, spynl_data_db
):
    """After successful verification, pending verifaction becomes False."""
    key = store_key(spynl_data_db, UID, 'email-verification', 3600)
    user = db.users.find_one({'_id': UID})
    assert user['email_verify_pending'] is True
    dummy_request.args = {'email': 'maddoxx.aveen@softwear.nl', 'key': key}
    verify_email(dummy_request)
    user = db.users.find_one({'_id': UID})
    assert user['email_verify_pending'] is False
