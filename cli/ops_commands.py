import contextlib
import os
import re
import shlex
import subprocess

import click

from cli.cli import cli
from cli.utils import run_command

# get base directory (*spynl.app*/commands/commands.py), without git dependency
PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

JIRA_ID_REGEX = "[A-Z]{1,10}-\\d+"


@contextlib.contextmanager
def chdir(dir):
    curdir = os.getcwd()
    os.chdir(dir)
    yield
    os.chdir(curdir)


with chdir(os.path.abspath(os.path.dirname(__file__))):
    BASE_DIR = (
        run_command('git rev-parse --show-toplevel', stdout=subprocess.PIPE)
        .stdout.decode('u8')
        .strip()
    )


@cli.group()
def ops():
    """Entry point for ops commands."""


@ops.command()
def changelog():
    """Return a changelog"""
    tag_list = run_command(
        "git log --tags --simplify-by-decoration --pretty='%D' --since='last month'",
        capture_output=True,
    )
    print("Last month's tags", ', '.join(re.findall('tag: (.*)\n', tag_list)))
    version = input('Pick a version to compare to: ')

    print('\n\n<h2>All changes since {}:</h2>'.format(version))

    all_messages = _get_all_messages(version)

    print('<ul>')
    for line in all_messages:
        print(_format_title(line))
    print('</ul>')

    unique_ids = _get_unique_jira_ids(all_messages)

    print('<a href="{}">Changes list in jira</a>'.format(_to_jira_url(unique_ids)))


@ops.command()
def quick_changelog():
    """
    Return a changelog with tickets. If there are multiple tickets in a commit
    message, it includes both.

    please note, if there are new commits after the last tag, checkout that tag before
    you run this, otherwise tickets in those untagged commits are also included.
    """
    tag_list = run_command(
        "git log --tags --simplify-by-decoration --pretty='%D' --since='last month'",
        capture_output=True,
    )
    print("Last month's tags", ', '.join(re.findall('tag: (.*)\n', tag_list)))
    version = input('Pick a version to compare to: ')

    command = 'git log --pretty="%s" HEAD...{}'.format(version)
    output = run_command(command, capture_output=True)

    unique_ids = list(set(re.findall(JIRA_ID_REGEX, output)))
    print('<a href="{}">Changes list in jira</a>'.format(_to_jira_url(unique_ids)))


def _format_title(message):
    return '<li><a href="https://jira.softwear.nl/browse/{}">{}</a></li>'.format(
        _get_ticket_id(message), message
    )


def _get_ticket_id(message):
    return re.match(JIRA_ID_REGEX, message)[0]


def _get_all_messages(version):
    command = 'git log --pretty="%s" HEAD...{}'.format(version)
    messages = run_command(command, capture_output=True).split('\n')

    all_messages = list(
        filter(lambda message: bool(re.match(JIRA_ID_REGEX, message)), messages)
    )
    all_messages.sort()

    return all_messages


def _get_unique_jira_ids(messages):
    all_ids = list(map(_get_ticket_id, messages))
    return list(set(all_ids))


def _to_jira_url(ids):
    return 'https://jira.softwear.nl/issues/?jql=issue%20in%20({})'.format(
        '%2C'.join(ids)
    )


@ops.command()
@click.option('--push', '-p', is_flag=True)
def tag(push):
    with chdir(BASE_DIR):
        dirty = run_command(
            'git status --porcelain', stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        ).stdout

    if dirty:
        click.get_current_context().fail(
            click.style('Repo not in clean state.', fg='red')
        )

    new_tag = _get_tag()

    _tag(new_tag, push, BASE_DIR)


def _tag(new_tag, push, project_folder):
    with chdir(project_folder):
        _modify_setup_py(new_tag)
        _tag_repo(new_tag)
        if push:
            _push_tag(new_tag)


def _reset_repo(project_folder):
    """
    Reset the master branch to origin/master
    Sync the local tags witht the remote tags. Dropping local tags that do
    not exist on the remote.
    """
    with chdir(project_folder):
        for command in (
            'fetch origin master',
            'checkout master',
            'reset --hard origin/master',
        ):
            run_command(
                'git ' + command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

        # https://stackoverflow.com/a/5373319
        list_tags = subprocess.Popen(
            shlex.split('git tag -l'), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        subprocess.Popen(
            shlex.split('xargs git tag -d'),
            stdin=list_tags.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).communicate()

        run_command(
            'git fetch --tags', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def _get_tag():
    while True:
        tag_prompt = 'Tag :'
        new_tag = click.prompt(tag_prompt)

        if not re.match(r'\d+\.\d+\.\d+$', new_tag):
            click.echo(
                click.style(
                    'Tag must follow the format [year].[week].[release]. ', fg='red'
                )
            )
        else:
            return new_tag


def _tag_repo(tag):
    run_command('git add .')
    run_command(
        'git commit -m "Release {}"'.format(tag),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    run_command(
        'git tag -a v{tag} -m "Release {tag}"'.format(tag=tag),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _push_tag(tag):
    run_command('git push origin master', check=True)
    run_command('git push origin --tags', check=True)


def _modify_setup_py(new_tag):
    with open('setup.py', 'r') as f:
        version_file_content = f.read()

    with open('setup.py', 'w') as f:
        version_pattern = re.compile(r"(version.{0,3}= ?.)(.*)(['\"])")
        version = version_pattern.search(version_file_content).group(2)
        new_contents = re.sub(version, new_tag, version_file_content)
        f.write(new_contents)
