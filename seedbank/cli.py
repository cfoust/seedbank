
"""
This module implements the seedbank cli.
"""
import click, os, seedbank

def init_seedbank():
    """
    Return a Seedbank instance pointing to the cwd.
    """
    return seedbank.Seedbank(os.getcwd())

def load_seedbank():
    """
    Create a Seedbank object pointing to the current working directory.
    If it is not initialized, print something and exit.
    """
    bank = init_seedbank()

    if not bank.is_repo_initialized():
        click.echo('A seedbank repo is not initialized here.')
        click.echo('Type `sb init` to create one.')
        exit(1)

    bank.connect()
    return bank

@click.group()
def cli():
    pass

@cli.command()
def list():
    """
    List the archives in the repository.
    The order is from least to most recent.
    """
    bank = load_seedbank()

    # TODO: pretty-print a list of archives
    click.echo(bank.get_list())

@cli.command()
def init():
    """
    Initialize an empty seedbank repository.
    """
    bank = init_seedbank()

    if bank.is_repo_initialized():
        click.echo('A seedbank repo is already initialized here.')
        exit(1)

    bank.init()
    bank.connect()

@cli.command()
@click.argument('path')
def create(path):
    """
    Create an archive.
    Note that this does not upload the archive automatically.
    """
    bank = load_seedbank()

    if not os.path.isdir(path):
        click.echo('Path %s does not exist or is not a directory.' % path)
        exit(1)

    bank.create_archive(path)
