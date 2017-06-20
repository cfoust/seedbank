
"""
This module implements the seedbank cli.
"""
import click, os, seedbank

def init_seedbank(directory=os.getcwd()):
    """
    Return a Seedbank instance pointing to the provided directory or None if
    it doesn't exist.
    """
    if not os.path.exists(directory):
        return None

    return seedbank.Seedbank(directory)

def load_seedbank():
    """
    Create a Seedbank object pointing to the current working directory.
    If it is not initialized, print something and exit.
    """
    # Attempt to load sbrc
    config = load_sbrc()

    # First check to see if we can load the default repo
    bank = load_bank_from_sbrc(config)

    # Otherwise just use the current working directory
    if not bank:
        bank = init_seedbank()

    # Don't do anything if the repo isn't initialized
    if not bank.is_repo_initialized():
        click.echo('A seedbank repo is not initialized here.')
        click.echo('Type `sb init` to create one.')
        exit(1)

    bank.connect()
    return bank

def load_bank_from_sbrc(config):
    """
    Attempt to load the default seedbank repository from the .sbrc.json
    file. Return the Seedbank or None if either there is no path in
    .sbrc or the path does not exist.
    """
    if not config:
        return None

    default_repo = config.get("default_repo")

    if not default_repo:
        return None

    default_repo_path = seedbank.Path(default_repo)

    if not default_repo_path.exists():
        return None

    return init_seedbank(default_repo_path.root())

def load_sbrc():
    """
    Check for a .sbrc.json that contains system-global seedbank
    settings, including the location of the system's seedbank repo.
    """
    home_dir_path = seedbank.Path('~')
    locations = [
        home_dir_path.relative('.sbrc.json')
    ]
    for location in locations:
        if os.path.isfile(location):
            manager = seedbank.ConfigManager(location)
            manager.parse_config()
            print(location, manager)
            return manager
        print location + ' does not exist'
    return None

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
