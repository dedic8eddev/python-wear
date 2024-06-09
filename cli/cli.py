import click

from spynl.main.version import __version__ as spynl_version


@click.group()
@click.version_option(spynl_version)
def cli():
    """Entry point for all commands."""
