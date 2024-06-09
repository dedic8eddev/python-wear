import os
from pprint import pprint  # noqa
from urllib.parse import urlparse

import psycopg2
import pymongo
from bson.codec_options import CodecOptions

options = urlparse(
    os.environ.get(
        'REDSHIFT_URI', 'redshift://postgres:password@localhost:5439/softwearbi'
    )
)
conn = psycopg2.connect(
    **{
        'dbname': options.path[1:],
        'user': options.username,
        'password': options.password,
        'port': options.port,
        'host': options.hostname,
    }
)

uri = os.environ.get('MONGO_URI', 'mongodb://mongo-user:password@localhost:27020')
db = os.environ.get('MONGO_DB', 'e2edb')
mongo_client = pymongo.MongoClient(uri)
db = mongo_client.get_database(db, codec_options=CodecOptions(uuid_representation=4))
