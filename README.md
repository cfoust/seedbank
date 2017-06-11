# Seedbank

Seedbank is a librarian for your Amazon Glacier archives.

## Features

It allows you to create archives with more metadata including file lists, Markdown descriptions, and timestamps. It also integrates with Git to track changes to your archives over time. You can upload copies of your seedbank repository to Glacier automatically.

Amazon Glacier limits the length of archive descriptions to 1KB of ASCII characters. Amazon's suggestion is to store metadata in another database, but that doesn't make sense if you're a consumer user just trying to store old archives. Seedbank enables you to store the metadata for your archives both in Git and Amazon Glacier itself so that even if the repository for your archives gets lost, you can still recover all of your metadata.

## Example workflow
Starting in an empty directory, initialize a seedbank repository.
```
> sb init
```
In addition to creating seedbank's config file (`seedbank.json`,) `sb init` also initializes the git repository and makes the initial commit.

*Note:* it's recommended that you add a remote (preferably a private repo) for the git repository. Seedbank will offer to push to it automatically after you have it set up.

Creating an archive is just as easy.
```
> sb create ~/somedir
Building archive of ~/somedir...
Using provided archive description '~/somedir/description.md'.
```
and then some time later...
```
Archive [uid] for ~/somedir created.
```

`sb list [-n N]` lists all of your archives in chronological order. The `-n` option shows only the last `N` recent archives. It also warns you about archives that have been created, but not uploaded.

`sb upload {uid}` uploads an archive to Amazon Glacier. Automatically chooses between multipart and singlepart uploads.

`sb download {uid}` initiates a retrieval from Glacier. This is not currently implemented, but ideally you could check (with `sb check`) to see the status of any outstanding jobs.

As with `git`, you do not have to provide the full uid in to reference an
individual archive, but only enough bytes for the reference to be unambiguous.

All local archives are saved in the (`.gitignore`d) `local` folder in the seebank repository.

## Why target Python2?

Python3 opens stdout and stdin in Unicode mode. WTF Python3? Seedbank relies on click, which [has a page](http://click.pocoo.org/5/python3/) describing why Python3 support breaks easily.
