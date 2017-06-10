"""
This module defines a class called `seedbank` that supports
all of the methods necessary to implement the CLI.
"""
import os, git, boto3, json, shutil, zipfile

# TODO: generate this more dynamically
DEFAULT_CONFIG = {
            'vault_name' : 'seedbank'
        }

def to_json(obj):
    """
    Convert a dictionary to pretty-printed JSON.

    Keyword arguments:
    obj -- Dictionary to convert.
    """
    return json.dumps(obj, sort_keys=True, indent=4)

class Path:
    def __init__(self, path):
        self.path = os.path.abspath(path)

        if not self.path.endswith('/'):
            self.path += '/'

    def root(self):
        """
        Return the root path this object was initialized with.
        """
        return self.path

    def relative(self, path):
        """
        Return an absolute path relative to the repository root.

        Keyword arguments:
        path -- Path to add on to the root of the repository's path.
        """
        return self.path + path

class Seedbank:
    def __init__(self, path):
        """
        Initialize a Seedbank object. Does not perform any
        operations on the directory provided in path, just
        sets up any internal state needed for Seedbank to
        function.

        Keyword arguments:
        path -- Path to a seedbank repository that may or may
                not have been initialized.
        """
        self.path = Path(path)

    def ensure_path_exists(self):
        """
        Ensure the path supplied on intialization exists.
        """
        root = self.path.root()
        if not os.path.exists(root):
            raise Exception('Invalid path for seedbank repo: ' + root)

    def is_repo_initialized(self):
        """
        Return true if the repository at self.path was initialized,
        otherwise return false.

        `Initialized` means it has a .git folder and a seedbank.json
        configuration file.

        """
        # TODO: Make this a bit more elegant
        git = self.path.relative('.git')
        conf = self.path.relative('seedbank.json')
        return os.path.exists(git) and os.path.exists(conf)

    def init(self):
        """
        Initializes a Seedbank repository. Will throw exception
        if the repository is already initialized (has a seedbank.json).
        """
        self.ensure_path_exists()

        if self.is_repo_initialized():
            raise Exception('Seedbank repository already ' +
                            'initialized: %s" % self.path')

        # Initialize a repository with an empty config
        repo = git.Repo.init(self.path.root())
        # TODO: also include meta.json file with information
        # about the repository's creation date
        conf_name = self.path.relative('seedbank.json')
        with open(conf_name, 'w+') as config:
            config.write(to_json(DEFAULT_CONFIG))
        repo.index.add(['seedbank.json'])
        repo.index.commit('SEEDBANK INITIAL COMMIT')
        print 'Seedbank initialized at ' + self.path.root()

    def connect(self):
        """
        Creates a reference to the seedbank's git repository
        and any other construction we have to do for repos
        that already exist.
        """
        for directory in ['archives', 'local']:
            path = self.path.relative(directory)
            if not os.path.exists(path):
                os.mkdir(path)

        self.repo = git.Repo(self.path.root())
        self.client = boto3.client('glacier')
    
    def create_archive(self, path):
        """
        Create an archive from the given directory.
        Directory can contain a description.md with
        information about the contents of the archive.

        A file list is included by default.


        Keyword arguments:
        path -- Path to directory to archive.
        """
        path = Path(path)
        print "Building archive of '%s'" % path.root()

        # TODO: actually calculate uid somehow
        # hashing the current time is probably ok
        uid = 'deadbeef'
        zip_path = self.path.relative('local/' + uid)

        # Build the archive
        shutil.make_archive(zip_path, 'zip', path.root())

        # Extract a file list from the archive
        file_list = []
        with zipfile.ZipFile(zip_path + '.zip', 'r') as archive:
            for item in archive.infolist():
                file_list.append(item.filename)

        # Get the text of the description if it exists
        description = ''
        description_path = path.relative('description.md')
        if os.path.exists(description_path):
            description = open(description_path, 'r').read()
            print 'Using archive description %s' % description_path
