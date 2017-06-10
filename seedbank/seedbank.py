"""
This module defines a class called `seedbank` that supports
all of the methods necessary to implement the CLI.
"""
import os, git, boto3, json

# TODO: generate this more dynamically
DEFAULT_CONFIG = """{
    "vault_name" : "seedbank"
}
"""

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
        self.path = path

        if not self.path.endswith('/'):
            self.path += '/'

    def relative(self, path):
        """
        Return an absolute path relative to the repository root.

        Keyword arguments:
        path -- Path to add on to the root of the repository's path.
        """
        return self.path + path

    def ensure_path_exists(self):
        """
        Ensure the path supplied on intialization exists.
        """
        if not os.path.exists(self.path):
            raise Exception('Invalid path for seedbank repo: ' + self.path)

    def is_repo_initialized(self):
        """
        Return true if the repository at self.path was initialized,
        otherwise return false.

        `Initialized` means it has a .git folder and a seedbank.json
        configuration file.

        """
        # TODO: Make this a bit more elegant
        git = self.relative('.git')
        conf = self.relative('seedbank.conf')
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
        self.repo = git.Repo.init(self.path)
        conf_name = self.relative('seedbank.json')
        with open(conf_name, 'w+') as config:
            config.write(DEFAULT_CONFIG)
        self.repo.index.add(['seedbank.json'])
        self.repo.index.commit('SEEDBANK INITIAL COMMIT')
        print 'Seedbank initialized at ' + self.path

    def connect(self):
        """
        Creates a reference to the seedbank's git repository
        and any other construction we have to do for repos
        that already exist.
        """
        self.repo = git.Repo(self.path)
        self.client = boto3.client('glacier')
