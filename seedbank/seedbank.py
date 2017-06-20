"""
This module defines a class called `seedbank` that supports
all of the methods necessary to implement the CLI.
"""
import os, git, boto3, shutil, zipfile, datetime, hashlib
import jsondate as json
from botocore.utils import calculate_tree_hash
from .constants import *

DEFAULT_CONFIG = {
            'vault_name' : 'seedbank'
        }

""" A megabyte multiplied by 2^3 (8MB). Used for multipart uploads."""
PART_SIZE = 1048576 * pow(2, 3)

def to_json(obj):
    """
    Convert a dictionary to pretty-printed JSON.

    Keyword arguments:
    obj -- Dictionary to convert.
    """
    return json.dumps(obj, sort_keys=True, indent=4)

def make_now_hash():
    """
    Make a SHA256 hash of the current date and time.
    """
    return hashlib.sha256(str(datetime.datetime.now())).hexdigest()

class Path:
    """
    Offer simple extractions over paths so as to not
    require string additions everywhere.
    """

    def __init__(self, path):
        # Expand any uses of ~ and transform to absolute
        self.path = os.path.expanduser(path)
        self.path = os.path.abspath(self.path)

        if not self.path.endswith('/'):
            self.path += '/'

    def root(self):
        """
        Return the root path this object was initialized with.
        """
        return self.path
    
    def exists(self):
        """
        Check whether the directory at the root path exists.
        """
        return os.path.exists(self.root())

    def relative(self, path):
        """
        Return an absolute path relative to the repository root.

        Keyword arguments:
        path -- Path to add on to the root of the repository's path.
        """
        return self.path + path

class Archive:
    def __init__(self):
        self.title = ""
        self.description = ""
        self.uid = make_now_hash()
        self.create_time = datetime.datetime.now()
        self.path = None
        self.size = 0
        self.file_list = []
        self.aws_response = {}
        self.remote_id = ""

    @staticmethod
    def from_file(file_path):
        """
        Initialize an archive by parsing it from a file.

        Keyword arguments:
        file_path -- Path to read JSON from.
        """
        archive = Archive()
        archive_obj = json.loads(open(file_path, 'r').read())
        archive.create_time = archive_obj['create_time']
        archive.description = archive_obj['description']
        archive.uid = archive_obj['uid']
        archive.file_list = archive_obj['file_list']
        archive.aws_response = archive_obj['aws_response']
        archive.size = archive_obj['size']
        archive.remote_id = archive_obj['remote_id']
        return archive

    def to_file(self, file_path):
        """
        Turn this Archive instance into its JSON
        representation and write it to a file.

        Keyword arguments:
        file_path -- Path to write JSON to.
        """
        archive_obj = {}
        archive_obj['create_time'] = self.create_time
        archive_obj['description'] = self.description
        archive_obj['uid']         = self.uid
        archive_obj['file_list']   = self.file_list
        archive_obj['aws_response']= self.aws_response
        archive_obj['size']        = self.size
        archive_obj['remote_id']   = self.remote_id
        open(file_path, 'w').write(to_json(archive_obj))

    def is_uploaded(self):
        return self.remote_id != ''

    def get_meta(self, path):
        """
        Given a root Path, return this archive's metadata .json
        file path.
        """
        return path.relative('archives/%s.json' % self.uid)

    def get_local(self, path):
        """
        Given a root Path, return this archive's .zip file
        path locally. May or may not exist.
        """
        return path.relative('local/%s.zip' % self.uid)

class ArchiveManager:
    """
    Manages all archives stored locally and creates them on demand.
    Also has handy functions for searching through all archives in
    the seedbank.
    """

    def __init__(self, archive_path):
        """
        Initialize the ArchiveManager instance. Does not perform
        any operations on the archives folder.
        It assumes that the path supplied exists.

        Keyword arguments:
        archive_path -- The path to the archives/ folder, which contains
                        a .json file for every archive.
        """
        self.path = Path(archive_path)

    def parse_files(self):
        """
        Parse the files found in this manager's directory.
        """
        files = []
        for (dirpath, dirnames, filenames) in os.walk(self.path.root()):
            files = [f for f in filenames if '.json' in f]
            break

        # Parse the files into Archive objects
        self.archives = []
        for archive_file in files:
            self.archives.append(Archive.from_file(self.path.relative(archive_file)))

    def get_list(self):
        """
        Get the list of archives this manager has parsed.
        """
        return self.archives

    def add(self, archive):
        """
        Add an archive to this manager.
        """
        self.archives.append(archive)

    def get_archive(self, uid_prefix):
        """
        Get an archive by the prefix of its uid.
        Raises and exception if more than one match.

        Keyword arguments:
        uid_prefix -- Prefix of an existing archive.
        """
        matches = [x for x in self.archives if x.uid.startswith(uid_prefix)]
        if len(matches) > 1:
            raise Exception('Ambiguous prefix %s matches more than one archive' % uid_prefix)

        if len(matches) == 0:
            return None

        return matches[0]

class ConfigManager:
    def __init__(self, config_path):
        self.path = config_path

    def parse_config(self):
        """
        Parse a JSON config.

        Keyword arguments:
        config_path -- Path to a seedbank.json
        """
        self.data = json.loads(open(self.path, 'r').read())

    def get(self, key):
        return self.data[key]

class MultipartUploader:
    """
    Convenience class for handling an individual multipart
    upload.
    """


    def __init__(self, client, archive, config, zip_path):
        """
        Initialize a MultipartUploader instance.

        Keyword arguments:
        client   -- boto3 Glacier client
        archive  -- Archive object to upload
        config   -- ConfigManager object
        zip_path -- Path to archive's zip
        """
        self.client   = client
        self.archive  = archive
        self.config   = config
        self.zip_path = zip_path

    def open(self):
        """
        Open the zip file for reading and get any config
        vars we might need a lot.
        """
        self.zip_file = open(self.zip_path, 'r')
        self.zip_file_size = os.path.getsize(self.zip_path)
        self.vault_name = self.config.get('vault_name')

    def start_upload(self):
        """
        Start the multipart upload.
        """
        # Start a multipart upload
        response = self.client.initiate_multipart_upload(
            vaultName=self.vault_name,
            archiveDescription=self.archive.uid,
            partSize=str(PART_SIZE)
        )
        self.upload_id = response.get('uploadId')

    def upload_part(self):
        """
        Upload the next part of the archive.
        Return True if we're done uploading, false otherwise.
        """
        current_byte = self.zip_file.tell()
        end_byte = (current_byte + PART_SIZE) - 1
        if end_byte > self.zip_file_size:
            end_byte = self.zip_file_size - 1

        format_tuple = (current_byte, end_byte, self.zip_file_size)
        byte_range = "bytes %d-%d/%d" % format_tuple

        response = self.client.upload_multipart_part(
                vaultName=self.vault_name,
                uploadId=self.upload_id,
                range=byte_range,
                body=self.zip_file.read(PART_SIZE)
        )
        # TODO: error check `response`
        return self.zip_file.tell() == self.zip_file_size

    def upload(self):
        """
        Upload the archive to Amazon Glacier by chunking it.
        """
        self.start_upload()
        while not self.upload_part():
            continue
        # Move to the front of the file to calculate its hash
        self.zip_file.seek(0)
        zip_hash = calculate_tree_hash(self.zip_file)
        response = self.client.complete_multipart_upload(
                vaultName=self.vault_name,
                uploadId=self.upload_id,
                archiveSize=str(self.zip_file_size),
                checksum=zip_hash
        )
        return response

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
        print self.path.root()
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

        # Initialize a repository
        repo = git.Repo.init(self.path.root())
        # TODO: also include meta.json file with information
        # about the repository's creation date

        conf_name = self.path.relative('seedbank.json')
        with open(conf_name, 'w+') as config:
            config.write(to_json(DEFAULT_CONFIG))

        gitignore_name = self.path.relative('.gitignore')
        with open(gitignore_name, 'w+') as gitignore:
            # Just ignore the `local` directory, which
            # has any archives created locally or
            # downloaded
            gitignore.write('local')

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

        self.manager = ArchiveManager(self.path.relative('archives'))
        self.manager.parse_files()

        self.config = ConfigManager(self.path.relative('seedbank.json'))
        self.config.parse_config()

    def create_archive(self, path):
        """
        Create an archive from the given directory.
        Directory can contain a description.md with
        information about the contents of the archive.

        A file list is included by default.

        Returns the new archive's uid.

        Keyword arguments:
        path -- Path to directory to archive.
        """
        path = Path(path)
        print "Building archive of %s" % path.root()

        archive = Archive()
        meta_path, local_path = self.get_archive_paths(archive)

        # Build the archive
        zip_file = zipfile.ZipFile(
                local_path,
                'w',
                zipfile.ZIP_DEFLATED,
                allowZip64=True)

        # Walk through the directory we want to create an archive for.
        for root, _, filenames in os.walk(path.root()):
            for name in filenames:
                # The absolute path of the file on this filesystem
                real_path = os.path.join(root, name)
                # The destination path to the file inside the zip
                relative_path = real_path[len(path.root()):]
                zip_file.write(real_path, relative_path)
                print 'Wrote %s' % relative_path

        # Extract a file list from the archive
        file_list = []
        for item in zip_file.infolist():
            file_list.append(item.filename)

        # Get the text of the description if it exists
        description = ''
        description_path = path.relative('description.md')
        if os.path.exists(description_path):
            description = open(description_path, 'r').read()
            print 'Using archive description %s' % description_path

        # Store information about the archive
        archive.create_time = datetime.datetime.utcnow()
        archive.description = description
        archive.file_list   = file_list
        # Note that archive.size is the size of the archive
        # in bytes BEFORE adding the meta file
        archive.size = os.path.getsize(local_path)

        # Write archive metadata to both the repo and the
        # archive itself
        archive.to_file(meta_path)
        zip_file.write(meta_path, 'info.json')
        zip_file.close()

        self.manager.add(archive)
        print 'Archive %s of %s created.' % (archive.uid[:8], path.root())

        return archive.uid

    def get_list(self):
        """Get the list of `Archive` instances that this controls."""
        return self.manager.get_list()

    def resolve_archive(self, uid_prefix):
        """
        Attempts to get an archive via a uid_prefix.
        Returns a tuple with the following:
            -- Archive object for archive
            -- Path to archive's .json file
            -- Path to archive's .zip file

        Keyword arguments:
        uid_prefix -- Prefix of an existing archive.
        """
        archive = self.manager.get_archive(uid_prefix)

        if not archive:
            raise Exception('No archive found for prefix %s' % uid_prefix)

        return archive

    def get_archive_paths(self, archive):
        """
        Return the resolved paths for an archive's .json and .zip file.
        """
        return (archive.get_meta(self.path), archive.get_local(self.path))

    def upload_archive(self, uid_prefix):
        """
        Upload an archive specified from a uid prefix.
        Chooses multipart if the size is greater than two times PART_SIZE.
        """
        archive = self.resolve_archive(uid_prefix)
        meta_path, local_path = self.get_archive_paths(archive)

        if not os.path.exists(local_path):
            raise Exception('Cannot upload archive %s because it does not exist on this system' % archive.uid)

        # Decide whether we should do a single-part or multipart upload
        size = os.path.getsize(local_path)
        response = None
        if size > 2 * PART_SIZE:
            response = self.upload_multipart_archive(archive)
        else:
            response = self.upload_whole_archive(archive)

        archive.aws_response = response
        archive.remote_id = response['archiveId']

        # Overwrite the previous .json file describing this archive
        archive.to_file(meta_path)

        self.repo.index.add([meta_path])
        commit_text = UPLOAD_COMMIT % (archive.uid, archive.aws_response['location'])
        if len(archive.description) > 0:
            commit_text += UPLOAD_COMMIT_DESCRIPTION % archive.description
        self.repo.index.commit(commit_text)

    def upload_whole_archive(self, archive):
        """
        Upload an archive to Amazon Glacier in a single request.

        Keyword arguments:
        archive -- Archive object
        """
        meta_path, local_path = self.get_archive_paths(archive)

        vault_name = self.config.get('vault_name')
        zip_file = open(local_path, 'r')

        # Upload the archive to the vault
        response = self.client.upload_archive(
            vaultName=vault_name,
            archiveDescription=archive.uid,
            body=zip_file
        )
        return response

    def upload_multipart_archive(self, archive):
        """
        Upload an archive to Amazon Glacier by splitting the zip
        into parts.

        Keyword arguments:
        archive -- Archive object
        """
        meta_path, local_path = self.get_archive_paths(archive)
        vault_name = self.config.get('vault_name')

        uploader = MultipartUploader(
                self.client,
                archive,
                self.config,
                local_path
        )

        # Open the zip file
        uploader.open()

        # Upload the chunks
        return uploader.upload()
