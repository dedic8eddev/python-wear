import os
import shlex
import subprocess
from sys import platform

import click


def fail(msg):
    click.get_current_context().fail(msg)


def run_command(command, capture_output=False, **kwargs):
    posix = True
    if platform == 'win32':
        posix = False

    if capture_output:
        return (
            subprocess.check_output(shlex.split(command, posix=posix), **kwargs)
            .decode('utf-8')
            .strip()
        )

    return subprocess.run(shlex.split(command, posix=posix), **kwargs)


def check_ini(ctx, param, value):
    if value:
        return value
    elif os.environ.get('SPYNL_INI'):
        return os.environ['SPYNL_INI']

    return './development.ini'
