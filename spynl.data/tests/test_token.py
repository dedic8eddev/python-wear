import uuid

from spynl_schemas.token import TokenSchema


def test_obfuscation():
    token = dict(token=uuid.uuid4())
    schema = TokenSchema(only='token'.split(), context={'obfuscate': True})
    assert schema.dump(token)['token'].replace('*', '') == str(token['token'])[-10:]
