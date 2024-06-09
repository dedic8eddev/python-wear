"""
Utils to get info about Spynl packages
"""

import os
import subprocess

from spynl.main.utils import chdir


def lookup_scm_commit(package_location):
    """Look up the SCM commit ID for a package."""
    with chdir(package_location):
        if os.path.exists('.git'):
            cmd = 'git rev-parse HEAD'
        elif os.path.exists('.hg'):
            cmd = 'hg id -i'
        else:
            return None
        cmd_result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True
        )
        return cmd_result.stdout.strip()


def lookup_scm_commit_describe(package_location):
    """
    Look up the SCM commit ID to give the version and, if the latest commit is
    not that of the version tag, the commit number (for git, hg works slightly
    differently)
    """
    with chdir(package_location):
        if os.path.exists('.git'):
            cmd = 'git describe --dirty'
        elif os.path.exists('.hg'):
            cmd = (
                'hg log -r . --template '
                '"{latesttag}-{latesttagdistance}-{node|short}\n"'
            )
        else:
            return None
        cmd_result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, universal_newlines=True
        )
        return cmd_result.stdout.strip()
