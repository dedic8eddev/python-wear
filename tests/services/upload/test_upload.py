"""
Tests upload procedure through API.

Tests for different conditions such as missing parameters or passing wrong
type files.
"""

import base64
import os
import re
from collections import namedtuple
from uuid import UUID, uuid4

import pytest

from spynl.api.auth.testutils import login

from spynl.services.upload.exceptions import S3ConnectionError
from spynl.services.upload.image import BaseImage, SpynlImage, SpynlLogo
from spynl.services.upload.utils import make_filename_unique

TenantFactory = namedtuple('TenantFactory', ['id'])
UserFactory = namedtuple('UserFactory', ['email', 'password'])

TENANT = TenantFactory('unittest_tenant')
USER = UserFactory('user1@email.com', '1234')
PATH = os.path.dirname(os.path.abspath(__file__))


def img():
    """Return the image in base64.encodestring format."""
    with open(f'{PATH}/data/test.jpg', 'rb') as fob:
        data = fob.read()
    return base64.b64encode(data).decode('utf-8')


def pdf_not_img():
    """Return pdf file in base64.encodestring format."""
    with open(f'{PATH}/data/its_pdf_not_img.img', 'rb') as fob:
        data = fob.read()
    return base64.b64encode(data).decode('utf-8')


def broken_img():
    """Return the broken image in base64.encodestring format."""
    with open(f'{PATH}/data/broken_image.png', 'rb') as fob:
        data = fob.read()
    return base64.b64encode(data).decode('utf-8')


def _filename_without_uuid(f):
    # every filename will get a unique id. strip it out to test filenames.
    value = f.rsplit('.')
    filename = value[0].rsplit('-', 5)[0]
    try:
        filename += '.' + value[1]
    except IndexError:
        pass

    return filename


@pytest.fixture
def mock_aws(monkeypatch):
    """Avoid accessing external service by mocking uploading/removing."""

    def mocked_upload(self, file_path=''):
        return self.s3_domain() + '/' + file_path

    def mocked_removal(*a, **kw):
        pass

    monkeypatch.setattr('spynl.services.upload.image.BaseImage._upload', mocked_upload)
    monkeypatch.setattr('spynl.services.upload.image.BaseImage._remove', mocked_removal)


@pytest.fixture(autouse=True)
def set_db(db):
    """Fill db with data for tests."""
    db.tenants.insert_one(
        {
            '_id': TENANT.id,
            'name': 'tenant 1',
            'settings': {'uploadDirectory': '12345'},
            'applications': ['account'],
        }
    )
    db.users.insert_one(
        {
            'name': 'user 1',
            'username': 'user1',
            'email': USER.email,
            'hash_type': '1',
            'password_hash': '81dc9bdb52d04dc20036dbd8313ed055',
            'password_salt': '',
            'active': True,
            'tz': 'Europe/Amsterdam',
            'tenant_id': [TENANT.id],
            'roles': {TENANT.id: {'tenant': ['account-admin']}},
        }
    )
    db.warehouses.insert_one({'tenant_id': [TENANT.id], 'datafeed': '1234'})


@pytest.fixture
def login1(app, set_db):
    """Create the test Pyramid app and login."""
    login(app, USER.email, USER.password, TENANT.id)


def test_not_passing_filename_when_adding_logo(app, login1, db, mock_aws):
    """A unique uuid4 should replace the not given filename arg."""
    app.post_json('/logos/add', dict(file=img()), status=200)
    tenant = db.tenants.find_one(dict(_id=TENANT.id))
    saved_urls = tenant['settings']['logoUrl']
    for url in saved_urls.values():
        filename = os.path.basename(url)
        without_extension = os.path.splitext(filename)[0]
        without_size_suffix = without_extension.split('_')[0]
        assert UUID(without_size_suffix)


def test_filename_unique():
    filename1 = 'blah.jpg'
    filename2 = 'blah.jpg'
    assert make_filename_unique(filename1) != make_filename_unique(filename2)


def test_filename_not_overwritten():
    filename1 = 'blah.jpg'
    unique_fn = make_filename_unique(filename1)
    assert all([part in unique_fn for part in filename1.split('.')])


@pytest.mark.parametrize("occurances", [1, 2, 3])
def test_filename_unique_replaces_any_uuid_part_when_it_exists_with_one_new_uuid(
    occurances,
):
    uuids_before = '-'.join([str(uuid4()) for _ in range(occurances)])
    filename = 'blah-{!s}.jpg'.format(uuids_before)
    filename_prefix, old_uuid_part, file_ext = filename.partition(uuids_before)

    result = make_filename_unique(filename)
    uuid_pattern = (
        r'[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
    )
    uuids_after = ''.join(re.findall(uuid_pattern, result))
    assert (
        old_uuid_part != uuids_after
        and result == filename_prefix + uuids_after + file_ext
    )


def test_filename_unique_prepend_extension():
    filename1 = 'blah.jpg'
    assert make_filename_unique(filename1).endswith('.jpg')


def test_filename_unique_insert_uuid():
    filename1 = 'blah.jpg'
    id_ = make_filename_unique(filename1).replace('blah', '').replace('.jpg', '')
    try:
        UUID(id_)
    except ValueError:
        pytest.fail("image did not get a uuid")


@pytest.mark.parametrize(
    'resource,name_in,name_out',
    [
        ('images', 'safe-name.png', 'safe-name.png'),
        ('images', ' with&and.jpeg', 'withand.jpeg'),
        ('images', 'foo/bar/baz', 'foobarbaz'),
        ('logos', 'foo/bar/baz.gif', 'foobarbaz.gif'),
        ('images', '../../goodies', 'goodies'),
        ('logos', '../../goodies', 'goodies'),
        ('images', '.', None),
        ('logos', '.', None),
        ('images', 'aö€', 'aö'),
        ('logos', 'b€ö', 'bö'),
    ],
)
def test_secure_filename(app, login1, db, resource, name_in, name_out, mock_aws):
    """Evil names are handled and no exception is raised."""
    payload = dict(file=img(), filename=name_in)
    r = app.post_json('/' + resource + '/add', payload, status=200)

    if name_out is None and resource == 'images':
        assert UUID(os.path.basename(r.json['url']), version=4)
    elif name_out is None and resource == 'logos':
        assert UUID(os.path.basename(r.json['urls']['fullsize']), version=4)
    elif resource == 'images':
        assert _filename_without_uuid(os.path.basename(r.json['url'])) == name_out
    elif resource == 'logos':
        assert (
            _filename_without_uuid(os.path.basename(r.json['urls']['fullsize']))
            == name_out
        )


def test_tenant_settings_have_correct_urls_when_add_logo(
    db, app, login1, monkeypatch, mock_aws
):
    """Ensure tenant's settings were updated with the urls."""
    # Monkey patch class sizes because img() has 256x256 size
    sizes = {'fullsize': (64, 64), 'medium': (32, 32), 'thumbnail': (16, 16)}
    monkeypatch.setattr(SpynlLogo, 'size_limits', sizes)

    img_name = uuid4().hex + '.png'
    payload = dict(filename=img_name, file=img())
    app.post_json('/logos/add', payload)

    tenant = db.tenants.find_one({'_id': TENANT.id})
    upload_dir = tenant['settings']['uploadDirectory'] + '/logos'
    domain = 'https://cdn.' + app.app.registry.settings['spynl.domain']
    url = domain + '/' + upload_dir
    expected_urls = {
        key: url + '/{}_{}x{}.jpeg'.format(img_name, *size)
        for key, size in sizes.items()
    }
    assert tenant['settings']['logoUrl'] == expected_urls


def test_replace_logo(db, app, login1, monkeypatch, mock_aws):
    # Monkey patch class sizes because img() has 256x56 size
    sizes = {'fullsize': (64, 64), 'medium': (32, 32), 'thumbnail': (16, 16)}
    monkeypatch.setattr(SpynlLogo, 'size_limits', sizes)
    # add first logo:
    app.post_json('/logos/add', dict(filename='foo.png', file=img()))
    tenant = db.tenants.find_one({'_id': TENANT.id})
    logo_urls_before = tenant['settings']['logoUrl'].values()
    # add different logo:
    app.post_json('/logos/add', dict(filename='bar.png', file=img()))
    tenant = db.tenants.find_one({'_id': TENANT.id})
    logo_urls_after = tenant['settings']['logoUrl'].values()

    assert logo_urls_before != logo_urls_after


def test_remove_logo(db, app, login1, monkeypatch, mock_aws):
    """Ensure the urls in the settings are empty."""
    # Monkey patch class sizes because img() has 256x256 size
    sizes = {'fullsize': (64, 64), 'medium': (32, 32), 'thumbnail': (16, 16)}
    monkeypatch.setattr(SpynlLogo, 'size_limits', sizes)

    app.post_json('/logos/add', dict(filename='foo.png', file=img()))
    app.post_json('/logos/remove', status=200)

    tenant = db.tenants.find_one({'_id': TENANT.id})
    assert tenant['settings']['logoUrl'] == {size: None for size in sizes}


@pytest.mark.parametrize(
    "image,message,needs_shrinking",
    [
        (pdf_not_img(), 'image-error', False),
        (broken_img(), 'image-error', True),
        ('non base64$encoded', 'image-error', False),
    ],
    ids=["a", "b", "c"],
)
def test_upload_bad_images(image, message, needs_shrinking):
    """Only valid images should be uploaded."""
    with pytest.raises(Exception, match=message):
        image = BaseImage(image, filename='random_name.jpeg')
        if needs_shrinking:
            image.shrink_by_quality()


def test_uploading_unsupported_image_format(monkeypatch):
    """Remove img's format from supported ones before testing."""
    monkeypatch.setattr(BaseImage, 'supported_formats', {'PNG', 'GIF'})
    with pytest.raises(Exception, match='unsupported-image'):
        BaseImage(img(), filename='foo.jpg')


@pytest.mark.parametrize(
    'cls,monkey_size', [(SpynlImage, (255, 255)), (SpynlLogo, (254, 254))]
)
def test_shrinking_by_size_sets_new_size_correctly(cls, monkey_size, monkeypatch):
    """Ensure new size dimensions are set(img size is 256x256)."""
    image = cls(img(), 'bigger_image.jpg')
    image.shrink_by_size(monkey_size)
    assert image.img.size == monkey_size


def test_uploading_bigger_image_than_max_file_size(config, monkeypatch):
    """Exception should be raised."""
    monkeypatch.setattr('spynl.services.upload.image.MAX_FILE_SIZE', 1)
    # Patch also the size_limits cause img size is 256,256
    monkeypatch.setattr(SpynlImage, 'size_limits', (16, 16))
    image = SpynlImage(img(), filename='random.jpeg')
    with pytest.raises(Exception) as excinfo:
        image.save('softwear-test')
    assert 'image-error' in str(excinfo.value)


@pytest.mark.parametrize(
    't_settings', [('uploadDirectory',), ('uploadDirectory', 'logoURL')]
)
def test_tenant_settings_without_upload_directory(db, app, login1, t_settings):
    """Test when different settings dont exist in tenant's settings."""
    db.tenants.update_one(
        {'_id': TENANT.id},
        {'$unset': {'settings.' + setting: 1 for setting in t_settings}},
    )
    for resource in ('images', 'logos'):
        r = app.post_json(
            '/' + resource + '/add',
            dict(filename=uuid4().hex, file=img()),
            expect_errors=True,
        )
        assert r.json['message'] == 'Upload directory is not set.'


@pytest.mark.parametrize("bucket_name", ['', 'random_bucket'])
def test_when_bucket_is_empty_or_does_not_exist(app, login1, monkeypatch, bucket_name):
    """Exception should be raised."""

    def mocked_upload(self, file_path=''):
        raise S3ConnectionError('')

    monkeypatch.setattr('spynl.services.upload.image.BaseImage._upload', mocked_upload)
    app.post_json('/logos/add', dict(filename=uuid4().hex, file=img()), status=400)


@pytest.mark.parametrize('resource', ['images', 'logos'])
def test_when_img_string_contains_metadata(app, login1, resource, mock_aws):
    """Make sure metadata gets removed from the string."""
    metadata = 'data:image/jpeg;base64,'
    payload = dict(filename=uuid4().hex + '.jpeg', file=metadata + img())
    app.post_json('/' + resource + '/add', payload, status=200)


def test_img_keeps_aspect_ratio_when_resized(app, login1):
    """Make sure at least one of width or height is less than."""
    with open(f'{PATH}/data/base64_img_str_scaled.txt', 'r') as fob:
        # strip the newline
        string = fob.read().strip()
    image = SpynlLogo(string, filename='company_logo.png')
    width_before, height_before = image.img.size
    assert width_before > image.size_limits['fullsize'][0]
    # Only width is bigger
    assert height_before < image.size_limits['fullsize'][1]

    image.shrink_by_size(image.size_limits['fullsize'])
    width_after, height_after = image.img.size
    assert width_after < width_before
    assert height_after < height_before

    width_ratio = width_before / width_after
    height_ratio = height_before / height_after
    assert round(width_ratio, 1) == round(height_ratio, 1)


@pytest.mark.parametrize('resource', ['images', 'logos'])
def test_returns_the_correct_urls(app, login1, db, resource, settings, mock_aws):
    """Response should contain the urls of uploaded image(s)."""
    img_name = uuid4().hex
    payload = dict(filename=img_name + '.jpeg', file=img())
    r = app.post_json('/' + resource + '/add', payload)
    upload_dir = db.tenants.find_one({'_id': TENANT.id})['settings']['uploadDirectory']
    url = 'https://cdn.' + settings['spynl.domain'] + '/' + upload_dir + '/'
    if resource == 'logos':
        assert r.json['urls'] == {
            'fullsize': url + 'logos/' + payload['filename'],
            'medium': url + 'logos/' + payload['filename'],
            'thumbnail': url + 'logos/' + img_name + '_64x64.jpeg',
        }
    elif resource == 'images':
        assert r.json['url'] == url + payload['filename']
