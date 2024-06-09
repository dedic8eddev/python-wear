"""Implements MongoDB Session to use instead of the standard pyramid session"""
import binascii
import logging
import os
import time
from uuid import uuid4

from bson.codec_options import CodecOptions
from pymongo.read_preferences import ReadPreference
from pyramid.interfaces import ISession
from pyramid.util import text_
from zope.interface import implementer

from spynl.main.utils import get_settings
from spynl.main.version import __version__ as spynl_version

from spynl.api.auth.authorization import Principals
from spynl.api.auth.utils import MASTER_TENANT_ID, get_tenant_roles


def _mkid():
    """make a new id"""
    return uuid4().hex


@implementer(ISession)
class MongoDBSession:
    """
    A session that stores information in a Mongo database.

    This class maintains a dict called _session which is mirrored in
    a dedicated collection in the database.

    We at least require a session ID (for identification), nothing else.
    Changes made to the dict are reflected in the DB autmoatically.
    However, if you change a value in a deeper level (e.g. a contained dict),
    call session.changed() to notify it to save itself.

    Note that MongoDB doesn't deal well with dots in keys,
    so we replace them with '___'.
    In the database, we store as meta data _id and creation
    date (_created) and _remember_me, which is False per default.
    Also, we maybe store flash queue (_f_) and csrft token (_csrft_).
    """

    # TODO: should _session be lazy, such that it's data is always fresh, no
    #       matter which server instance is asked for it?

    collname = 'spynl_sessions'
    log = logging.getLogger(__name__)

    def __init__(self, id=None):
        """init session"""
        self._session = None
        # lookup existing session:
        if id is not None:
            self._session = self._collection().find_one({'_id': id})
        # start new session:
        if self._session is None:
            sid = _mkid()
            self._session = {
                '_id': sid,
                '_created': time.time(),
                '_remember_me': False,
                'spynl_version': spynl_version,
            }
            self.log.debug('New session initialized: %s', sid)
            self.new = True
        else:
            self.log.debug('Looked up existing session with id %s', id)
            self.new = False

    @property
    def id(self):  # pylint: disable=C0103
        """get id"""
        return self._session['_id']

    @property
    def remember_me(self):
        """get remember_me value"""
        return self._session['_remember_me']

    @remember_me.setter
    def remember_me(self, value):
        """set remember me"""
        self._session['_remember_me'] = value
        self.changed()

    @property
    def expire(self):
        """get expire value"""
        return self._session['_expire']

    @expire.setter
    def expire(self, value):
        """set expire"""
        self._session['_expire'] = value
        self.changed()

    def __repr__(self):
        """readable representation"""
        return '<MongoDB Session ID: {}>'.format(self.id)

    def _collection(self):
        """return db object"""
        settings = get_settings()
        db = settings['spynl.mongo.db']
        rpreference = ReadPreference.PRIMARY
        return db.get_collection(
            self.collname,
            read_preference=rpreference,
            codec_options=CodecOptions(tz_aware=True, uuid_representation=4),
        )

    # -- dict - like methods --

    def get(self, key):
        """lookup a value"""
        return self._session.get(key.replace('.', '___'))

    def __getitem__(self, key):
        """lookup a value"""
        return self._session[key.replace('.', '___')]

    def __setitem__(self, key, value):
        """set a value"""
        self._session[key.replace('.', '___')] = value
        self.changed()

    def __delitem__(self, key):
        """remove a value"""
        self._session.__delitem__(key.replace('.', '___'))
        self.changed()

    def __iter__(self):
        """Only works for proxying to a dict."""
        return iter([k.replace('.', '___') for k in self._session.keys()])

    def __contains__(self, key):
        """contains check"""
        return key.replace('.', '___') in self._session

    # -- ISession methods --

    @property
    def created(self):
        """return created property"""
        return self._session['_created']

    def changed(self):
        """mark that this sesssion was changed"""
        self.new = False
        self.save()

    def save(self):
        """Only save when an _id (sid) and userid is present."""
        if '_id' in self and 'auth.userid' in self:
            self._collection().replace_one({'_id': self.id}, self._session, upsert=True)

    def invalidate(self):
        """Clear the contents and remove a session."""
        self.log.info('Session removed: %s', self.id)
        if self.new is False:
            self._collection().delete_one({'_id': self.id})
        self._session.clear()

    # flash API methods, adapted from Pyramid's default session
    def flash(self, msg, queue='', allow_duplicate=True):
        """flash"""
        storage = self._session.setdefault('_f_' + queue, [])
        if allow_duplicate or (msg not in storage):
            storage.append(msg)
        self.changed()

    def pop_flash(self, queue=''):
        """pop flash"""
        storage = self._session.pop('_f_' + queue, [])
        self.changed()
        return storage

    def peek_flash(self, queue=''):
        """peek flash"""
        storage = self._session.get('_f_' + queue, [])
        return storage

    # CSRF API methods, adapted from Pyramid's default session
    def new_csrf_token(self):
        """new CSRF token"""
        token = text_(binascii.hexlify(os.urandom(20)))
        self._session['_csrft_'] = token
        self.changed()
        return token

    def get_csrf_token(self):
        """get CSRF token"""
        token = self._session.get('_csrft_', None)
        if token is None:
            token = self.new_csrf_token()
        return token


def rolefinder(userid, request):
    """
    Return authorization roles and our tenant principals for the authenticated
    user. This is called by request.authenticated_userid, so be careful when
    using that function.
    """
    user = request.db.users.find_one({'_id': userid, 'active': True})

    # By returning None here we will not set the Authenticated principal.
    if not user:
        return

    roles = []
    if request.current_tenant_id == MASTER_TENANT_ID:
        roles = get_tenant_roles(request.db, user, MASTER_TENANT_ID, restrict=False)

    elif request.current_tenant_id:
        roles = get_tenant_roles(
            request.db, user, request.current_tenant_id, restrict=True
        )

    roles = ['role:%s' % role for role in roles]
    principals = get_custom_principals(user, request)
    return roles + principals


def get_custom_principals(user, request):
    """
    Return a list of principals in addition to the principals pyramid defines.
    """
    principals = []
    if request.current_tenant_id in user.get('tenant_id', []):
        principals.append(Principals.BelongsToTenant)

    if request.requested_tenant_id != request.current_tenant_id:
        # TODO: implement:
        # connection = find({'provider': request.requested_tenant_id,
        #                    'consumer': request.current_tenant_id})
        # if connection:
        #     principals.append(Principals.HasAccessToRequestedTenant)
        pass
    # TODO: if we add connection types to the B2B resources, we can also do a
    # a check to see if the corresponding connection type is active.

    return principals
