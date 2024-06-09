import json
import os
import subprocess
import sys

import click
import pkg_resources

from cli.cli import cli
from cli.utils import check_ini, fail, run_command

from spynl.main.pkg_utils import lookup_scm_commit, lookup_scm_commit_describe

# get base directory (*spynl.app*/commands/commands.py), without git dependency
PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@cli.group()
def dev():
    """entry point for dev commands."""


ini_option = click.option(
    '-i',
    '--ini',
    help='Specify an ini file to use.',
    type=click.Path(exists=True),
    callback=check_ini,
)


@dev.command()
def versions():
    """Generate a human readable json file specifiying the versions in use."""
    versions = {
        'spynl_app': {
            'version': pkg_resources.get_distribution('spynl.app').version,
            'commit': lookup_scm_commit('./'),
            'scmVersion': lookup_scm_commit_describe('./'),
        },
    }

    versions_path = os.path.join(sys.prefix, 'versions.json')
    with open(versions_path, 'w') as f:
        versions = json.dumps(versions, indent=4)
        print(versions, file=f)
    click.echo('Installed versions file successfully.')
    click.echo(versions)


@dev.command()
@ini_option
def serve(ini):
    """Run a local server."""
    run_command('pserve {} --reload'.format(ini))


@dev.command()
@ini_option
def generate_documentation(ini):
    print(ini)
    """Run a local server."""
    os.environ['GENERATE_SPYNL_DOCUMENTATION'] = 'generate'
    run_command('pserve {}'.format(ini))


@dev.command()
def test():
    """
    Run tests from anywhere.
    Report files will be in folder where command was excecuted.
    """
    cmd = sys.executable + ' -m pytest '

    test_path = ' '.join(
        [os.path.join(PATH, 'tests', folder) for folder in ['main', 'api', 'services']]
    )
    rcfile = os.path.join(PATH, 'setup.cfg')

    app_tests_failed = run_command(
        f'{cmd} --junit-xml=report.xml --cov={PATH}/spynl --cov-config={rcfile} '
        f'{test_path}'
    ).returncode

    run_command('coverage xml')
    # remove path from xml file so gitlab can parse it to show coverage in MR's:
    run_command(f"sed -i 's,{PATH}/,,g' coverage.xml")

    test_path = os.path.join(PATH, 'spynl.data', 'tests')
    data_tests_failed = run_command(
        f'{cmd} --junit-xml=report_spynl_data.xml  {test_path}'
    ).returncode

    if app_tests_failed or data_tests_failed:
        fail('Failed tests')


@dev.command()
@click.option(
    '-l',
    '--languages',
    multiple=True,
    default=['nl', 'en', 'de', 'fr', 'es', 'it'],
    help=(
        'A language code such as "en" or "nl". '
        'Can be provided multiple times for multiple languages.'
    ),
)
@click.option(
    '--refresh', '-r', help='Refresh the translations calalogs.', is_flag=True
)
@click.option(
    '--location',
    help='Show the comments (locations) in the .pot and .po file',
    is_flag=True,
)
@click.option(
    '--add-comments',
    '-c',
    help=(
        'Add translator comments from the code (translator comments'
        ' should start with #.)'
    ),
    is_flag=True,
)
def translate(languages, refresh, location, add_comments):
    """Perform translation tasks."""
    # needs a chdir to be able to run it everywhere!
    def format_command(command, lang=None):
        base_command = sys.executable + ' ' + os.path.join(PATH, 'setup.py')

        if lang:
            command += f' -l {lang}'

        return f'{base_command} {command}'

    if refresh:
        cmd = format_command('extract_messages')
        if not location:
            cmd += ' --no-location'
        if add_comments:
            cmd += ' --add-comments .'

        run_command(cmd)

        for lang in languages:
            try:
                run_command(format_command('update_catalog', lang=lang), check=True)
            except subprocess.CalledProcessError:
                # po file does not exist
                run_command(format_command('init_catalog', lang=lang))

    for lang in languages:
        run_command(format_command('compile_catalog', lang=lang))
