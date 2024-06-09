import os
import uuid

import pytest

from spynl_dbaccess import Database

MONGO_URL = os.environ.get(
    'MONGODB_URL', 'mongodb://mongo-user:password@localhost:27020'
)


@pytest.fixture()
def database():
    db_name = uuid.uuid4().hex
    database = Database(MONGO_URL, db_name, ssl=False)

    database.users.pymongo_create_index('username')
    yield database
    database.pymongo_client.drop_database(db_name)
    database.pymongo_client.close()


@pytest.fixture()
def database_with_limits():
    db_name = uuid.uuid4().hex
    database = Database(
        MONGO_URL, db_name, ssl=False, max_limit=10, max_agg_limit=10, max_time_ms=1
    )
    yield database
    database.pymongo_client.drop_database(db_name)
    database.pymongo_client.close()
