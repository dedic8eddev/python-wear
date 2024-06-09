import sys

from setuptools import setup


def pytest_runner_dependency():
    """Return a list that contains the pytest_runner dependency if needed"""
    needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
    return ['pytest-runner'] if needs_pytest else []


install_requires = [
    'babel',
    'beaker',
    'boto3',
    'click',
    'dnspython3',
    'gunicorn',
    'html2text',
    'html5lib',
    'jinja2',
    'jsonschema',
    'lxml',
    'marshmallow',
    'openpyxl',
    'pbkdf2',
    'pillow>=3.0.0',
    'psycopg2-binary',
    'pycparser',
    'pycryptodome',
    'pyjwt',
    'pymongo',
    'pyotp',
    'pyramid==2.0',
    'pyramid_exclog',
    'pyramid_jinja2',
    'pyramid_mailer>=0.15.1',
    'pytest',
    'pytest-cov',
    'python-dateutil',
    'pytz',
    'pyyaml',
    'raven',
    'requests',
    'responses',
    'sentry_sdk',
    'sphinx',
    'tld==0.7.9',
    'waitress',
    'weasyprint',
    'webob',
    'webtest',
]

setup(
    name='spynl.app',
    version='23.6.0',
    entry_points={
        'paste.app_factory': ['main = spynl.main:main'],
        'console_scripts': ['spynl-cli = cli:cli'],
    },
    packages=['spynl', 'cli'],
    paster_plugins=['pyramid'],
    install_requires=[install_requires],
    tests_require=['pytest', 'pytest_raisesregexp'],
    setup_requires=pytest_runner_dependency() + ['PasteScript'],
    author='Softwear BV',
    author_email='development@softwear.nl',
    keywords='API SaaS',
    include_package_data=True,
    zip_safe=False,
    message_extractors={
        'spynl': [
            ('**.py', 'python', None),
            ('**/email-templates/**.jinja2', 'jinja2', None),
            ('**/pdf-templates/**.jinja2', 'jinja2', None),
            ('**/templates/**.jinja2', 'jinja2', None),
        ],
    },
)
