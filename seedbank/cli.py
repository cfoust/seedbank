
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

    archives = bank.get_list()
    archives.sort(key=lambda archive: archive.create_time)
    for archive in archives:
        description = archive.description[:40]
        description = description.replace('\n','')
        if len(description) == 0:
            description = '[No description provided]'
        click.echo('%s %s' % (archive.uid[:8], description))

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

@cli.command()
@click.argument('uid_prefix')
def upload(uid_prefix):
    """
    Upload an archive.
    """
    bank = load_seedbank()

    archive = bank.resolve_archive(uid_prefix)

    if not archive:
        click.echo('Archive specified by %s does not exist.' % uid_prefix)
        exit(1)
    # Ask the user to make sure they want to reupload an archive.
    if archive.is_uploaded():
        click.confirm('The archive %s already exists remotely. Reupload it?' % archive.uid, abort=True)

    bank.upload_archive(uid_prefix)

@cli.command()
@click.argument('uid_prefix')
def download(uid_prefix):
    """
    Initiate an archive retrieval.
    """
    click.echo('Not yet implemented.')
