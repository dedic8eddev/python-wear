from setuptools import setup

setup(
    name='spynl.data',
    description='Defines a data access layer and data models.',
    version='23.2.0',
    packages=['spynl_dbaccess', 'spynl_schemas'],
    install_requires=['marshmallow', 'bleach==4.1.0', 'pymongo', 'pytz', 'babel'],
)
