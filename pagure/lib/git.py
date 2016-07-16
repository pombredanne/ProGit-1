# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""


import datetime
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import re

import pygit2
import werkzeug

from sqlalchemy.exc import SQLAlchemyError

import pagure
import pagure.exceptions
import pagure.lib
import pagure.lib.notify
from pagure.lib import model
from pagure.lib.repo import PagureRepo

# pylint: disable=R0913,E1101,R0914


def commit_to_patch(repo_obj, commits):
    ''' For a given commit (PyGit2 commit object) of a specified git repo,
    returns a string representation of the changes the commit did in a
    format that allows it to be used as patch.
    '''
    if not isinstance(commits, list):
        commits = [commits]

    patch = ""
    for cnt, commit in enumerate(commits):
        if commit.parents:
            diff = commit.tree.diff_to_tree()

            parent = repo_obj.revparse_single('%s^' % commit.oid.hex)
            diff = repo_obj.diff(parent, commit)
        else:
            # First commit in the repo
            diff = commit.tree.diff_to_tree(swap=True)

        subject = message = ''
        if '\n' in commit.message:
            subject, message = commit.message.split('\n', 1)
        else:
            subject = commit.message

        if len(commits) > 1:
            subject = '[PATCH %s/%s] %s' % (cnt + 1, len(commits), subject)

        patch += u"""From {commit} Mon Sep 17 00:00:00 2001
From: {author_name} <{author_email}>
Date: {date}
Subject: {subject}

{msg}
---

{patch}
""".format(commit=commit.oid.hex,
           author_name=commit.author.name,
           author_email=commit.author.email,
           date=datetime.datetime.utcfromtimestamp(
               commit.commit_time).strftime('%b %d %Y %H:%M:%S +0000'),
           subject=subject,
           msg=message,
           patch=diff.patch)
    return patch


def write_gitolite_acls(session, configfile):
    ''' Generate the configuration file for gitolite for all projects
    on the forge.
    '''
    config = []
    groups = {}
    for project in session.query(model.Project).all():
        for group in project.groups:
            if group.group_name not in groups:
                groups[group.group_name] = [
                    user.username for user in group.users]

        for repos in ['repos', 'docs/', 'tickets/', 'requests/']:
            if repos == 'repos':
                repos = ''

            config.append('repo %s%s' % (repos, project.fullname))
            if repos not in ['tickets/', 'requests/']:
                config.append('  R   = @all')
            if project.groups:
                config.append('  RW+ = @%s' % ' @'.join([
                    group.group_name for group in project.groups]))
            config.append('  RW+ = %s' % project.user.user)
            for user in project.users:
                if user != project.user:
                    config.append('  RW+ = %s' % user.user)
            config.append('')

    with open(configfile, 'w') as stream:
        for key, users in groups.iteritems():
            stream.write('@%s   = %s\n' % (key, ' '.join(users)))
        stream.write('\n')

        for row in config:
            stream.write(row + '\n')


def generate_gitolite_acls():
    """ Generate the gitolite configuration file for all repos
    """
    pagure.lib.git.write_gitolite_acls(
        pagure.SESSION, pagure.APP.config['GITOLITE_CONFIG'])

    gitolite_folder = pagure.APP.config.get('GITOLITE_HOME', None)
    gitolite_version = pagure.APP.config.get('GITOLITE_VERSION', 3)
    if gitolite_folder:
        if gitolite_version == 2:
            cmd = 'GL_RC=%s GL_BINDIR=%s gl-compile-conf' % (
                pagure.APP.config.get('GL_RC'),
                pagure.APP.config.get('GL_BINDIR')
            )
        elif gitolite_version == 3:
            cmd = 'HOME=%s gitolite compile && HOME=%s gitolite trigger '\
                'POST_COMPILE' % (
                    pagure.APP.config.get('GITOLITE_HOME'),
                    pagure.APP.config.get('GITOLITE_HOME')
                )
        else:
            raise pagure.exceptions.PagureException(
                'Non-supported gitolite version "%s"' % gitolite_version
            )
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=gitolite_folder
        )


def update_git(obj, repo, repofolder):
    """ Update the given issue in its git.

    This method forks the provided repo, add/edit the issue whose file name
    is defined by the uid field of the issue and if there are additions/
    changes commit them and push them back to the original repo.

    """

    if not repofolder:
        return

    # Get the fork
    repopath = os.path.join(repofolder, repo.path)

    # Clone the repo into a temp folder
    newpath = tempfile.mkdtemp(prefix='pagure-')
    new_repo = pygit2.clone_repository(repopath, newpath)

    file_path = os.path.join(newpath, obj.uid)

    # Get the current index
    index = new_repo.index

    # Are we adding files
    added = False
    if not os.path.exists(file_path):
        added = True

    # Write down what changed
    with open(file_path, 'w') as stream:
        stream.write(json.dumps(
            obj.to_json(), sort_keys=True, indent=4,
            separators=(',', ': ')))

    # Retrieve the list of files that changed
    diff = new_repo.diff()
    files = []
    for p in diff:
        if hasattr(p, 'new_file_path'):
            files.append(p.new_file_path)
        elif hasattr(p, 'delta'):
            files.append(p.delta.new_file.path)

    # Add the changes to the index
    if added:
        index.add(obj.uid)
    for filename in files:
        index.add(filename)

    # If not change, return
    if not files and not added:
        shutil.rmtree(newpath)
        return

    # See if there is a parent to this commit
    parent = None
    try:
        parent = new_repo.head.get_object().oid
    except pygit2.GitError:
        pass

    parents = []
    if parent:
        parents.append(parent)

    # Author/commiter will always be this one
    author = pygit2.Signature(name='pagure', email='pagure')

    # Actually commit
    new_repo.create_commit(
        'refs/heads/master',
        author,
        author,
        'Updated %s %s: %s' % (obj.isa, obj.uid, obj.title),
        new_repo.index.write_tree(),
        parents)
    index.write()

    # Push to origin
    ori_remote = new_repo.remotes[0]
    master_ref = new_repo.lookup_reference('HEAD').resolve()
    refname = '%s:%s' % (master_ref.name, master_ref.name)

    PagureRepo.push(ori_remote, refname)

    # Remove the clone
    shutil.rmtree(newpath)


def clean_git(obj, repo, repofolder):
    """ Update the given issue remove it from its git.

    """

    if not repofolder:
        return

    # Get the fork
    repopath = os.path.join(repofolder, repo.path)

    # Clone the repo into a temp folder
    newpath = tempfile.mkdtemp(prefix='pagure-')
    new_repo = pygit2.clone_repository(repopath, newpath)

    file_path = os.path.join(newpath, obj.uid)

    # Get the current index
    index = new_repo.index

    # Are we adding files
    if not os.path.exists(file_path):
        shutil.rmtree(newpath)
        return

    # Remove the file
    os.unlink(file_path)

    # Add the changes to the index
    index.remove(obj.uid)

    # See if there is a parent to this commit
    parent = None
    if not new_repo.is_empty:
        parent = new_repo.head.get_object().oid

    parents = []
    if parent:
        parents.append(parent)

    # Author/commiter will always be this one
    author = pygit2.Signature(name='pagure', email='pagure')

    # Actually commit
    new_repo.create_commit(
        'refs/heads/master',
        author,
        author,
        'Removed %s %s: %s' % (obj.isa, obj.uid, obj.title),
        new_repo.index.write_tree(),
        parents)
    index.write()

    # Push to origin
    ori_remote = new_repo.remotes[0]
    master_ref = new_repo.lookup_reference('HEAD').resolve()
    refname = '%s:%s' % (master_ref.name, master_ref.name)

    PagureRepo.push(ori_remote, refname)

    # Remove the clone
    shutil.rmtree(newpath)


def get_user_from_json(session, jsondata, key='user'):
    """ From the given json blob, retrieve the user info and search for it
    in the db and create the user if it does not already exist.
    """
    user = None

    username = fullname = useremails = default_email = None

    data = jsondata.get(key, None)

    if data:
        username = data.get('name')
        fullname = data.get('fullname')
        useremails = data.get('emails')
        default_email = data.get('default_email')

    if not default_email and useremails:
        default_email = useremails[0]

    if not username and not useremails:
        return

    user = pagure.lib.search_user(session, username=username)
    if not user:
        for email in useremails:
            user = pagure.lib.search_user(session, email=email)
            if user:
                break

    if not user:
        user = pagure.lib.set_up_user(
            session=session,
            username=username,
            fullname=fullname or username,
            default_email=default_email,
            emails=useremails,
            keydir=pagure.APP.config.get('GITOLITE_KEYDIR', None),
        )
        session.commit()

    return user


def get_project_from_json(
        session, jsondata,
        gitfolder, docfolder, ticketfolder, requestfolder):
    """ From the given json blob, retrieve the project info and search for
    it in the db and create the projec if it does not already exist.
    """
    project = None

    user = get_user_from_json(session, jsondata)
    name = jsondata.get('name')
    project_user = None
    if jsondata.get('parent'):
        project_user = user.username
    project = pagure.lib.get_project(session, name, user=project_user)

    if not project:
        parent = None
        if jsondata.get('parent'):
            parent = get_project_from_json(
                session, jsondata.get('parent'),
                gitfolder, docfolder, ticketfolder, requestfolder)

            pagure.lib.fork_project(
                session=session,
                repo=parent,
                gitfolder=pagure.APP.config['GIT_FOLDER'],
                docfolder=pagure.APP.config['DOCS_FOLDER'],
                ticketfolder=pagure.APP.config['TICKETS_FOLDER'],
                requestfolder=pagure.APP.config['REQUESTS_FOLDER'],
                user=user.username)

        else:
            pagure.lib.new_project(
                session,
                user=user.username,
                name=name,
                description=jsondata.get('description'),
                parent_id=parent.id if parent else None,
                blacklist=pagure.APP.config.get('BLACKLISTED_PROJECTS', []),
                gitfolder=os.path.join(gitfolder, 'forks', user.username)
                    if parent else gitfolder,
                docfolder=docfolder,
                ticketfolder=ticketfolder,
                requestfolder=requestfolder,
            )

        session.commit()
        project = pagure.lib.get_project(session, name, user=user.username)
        tags = jsondata.get('tags', None)
        if tags:
            pagure.lib.add_tag_obj(
                session, project, tags=tags, user=user.username,
                ticketfolder=None)

    return project


def update_ticket_from_git(
        session, reponame, username, issue_uid, json_data):
    """ Update the specified issue (identified by its unique identifier)
    with the data present in the json blob provided.

    :arg session: the session to connect to the database with.
    :arg repo: the name of the project to update
    :arg issue_uid: the unique identifier of the issue to update
    :arg json_data: the json representation of the issue taken from the git
        and used to update the data in the database.

    """

    repo = pagure.lib.get_project(session, reponame, user=username)
    if not repo:
        raise pagure.exceptions.PagureException(
            'Unknown repo %s of username: %s' % (reponame, username))

    user = get_user_from_json(session, json_data)

    issue = pagure.lib.get_issue_by_uid(session, issue_uid=issue_uid)
    if not issue:
        # Create new issue
        pagure.lib.new_issue(
            session,
            repo=repo,
            title=json_data.get('title'),
            content=json_data.get('content'),
            user=user.username,
            ticketfolder=None,
            issue_id=json_data.get('id'),
            issue_uid=issue_uid,
            private=json_data.get('private'),
            status=json_data.get('status'),
            date_created=datetime.datetime.utcfromtimestamp(
                float(json_data.get('date_created'))),
            notify=False,
        )

    else:
        # Edit existing issue
        pagure.lib.edit_issue(
            session,
            issue=issue,
            ticketfolder=None,
            user=user.username,
            title=json_data.get('title'),
            content=json_data.get('content'),
            status=json_data.get('status'),
            private=json_data.get('private'),
        )
    session.commit()

    issue = pagure.lib.get_issue_by_uid(session, issue_uid=issue_uid)

    # Update tags
    tags = json_data.get('tags', [])
    pagure.lib.update_tags(
        session, issue, tags, username=user.user, ticketfolder=None)

    # Update assignee
    assignee = get_user_from_json(session, json_data, key='assignee')
    if assignee:
        pagure.lib.add_issue_assignee(
            session, issue, assignee.username,
            user=user.user, ticketfolder=None, notify=False)

    # Update depends
    depends = json_data.get('depends', [])
    pagure.lib.update_dependency_issue(
        session, issue.project, issue, depends,
        username=user.user, ticketfolder=None)

    # Update blocks
    blocks = json_data.get('blocks', [])
    pagure.lib.update_blocked_issue(
        session, issue.project, issue, blocks,
        username=user.user, ticketfolder=None)

    for comment in json_data['comments']:
        user = get_user_from_json(session, comment)
        commentobj = pagure.lib.get_issue_comment(
            session, issue_uid, comment['id'])
        if not commentobj:
            pagure.lib.add_issue_comment(
                session,
                issue=issue,
                comment=comment['comment'],
                user=user.username,
                ticketfolder=None,
                notify=False,
                date_created=datetime.datetime.utcfromtimestamp(
                    float(comment['date_created'])),
            )
    session.commit()


def update_request_from_git(
        session, reponame, username, request_uid, json_data,
        gitfolder, docfolder, ticketfolder, requestfolder):
    """ Update the specified request (identified by its unique identifier)
    with the data present in the json blob provided.

    :arg session: the session to connect to the database with.
    :arg repo: the name of the project to update
    :arg username: the username to find the repo, is not None for forked
        projects
    :arg request_uid: the unique identifier of the issue to update
    :arg json_data: the json representation of the issue taken from the git
        and used to update the data in the database.

    """

    repo = pagure.lib.get_project(session, reponame, user=username)
    if not repo:
        raise pagure.exceptions.PagureException(
            'Unknown repo %s of username: %s' % (reponame, username))

    user = get_user_from_json(session, json_data)

    request = pagure.lib.get_request_by_uid(
        session, request_uid=request_uid)

    if not request:
        repo_from = get_project_from_json(
            session, json_data.get('repo_from'),
            gitfolder, docfolder, ticketfolder, requestfolder
        )

        repo_to = get_project_from_json(
            session, json_data.get('project'),
            gitfolder, docfolder, ticketfolder, requestfolder
        )

        status = json_data.get('status')
        if str(status).lower() == 'true':
            status = 'Open'
        elif str(status).lower() == 'false':
            status = 'Merged'

        # Create new request
        pagure.lib.new_pull_request(
            session,
            repo_from=repo_from,
            branch_from=json_data.get('branch_from'),
            repo_to=repo_to if repo_to else None,
            remote_git=json_data.get('remote_git'),
            branch_to=json_data.get('branch'),
            title=json_data.get('title'),
            user=user.username,
            requestuid=json_data.get('uid'),
            requestid=json_data.get('id'),
            status=status,
            requestfolder=None,
            notify=False,
        )
        session.commit()

    request = pagure.lib.get_request_by_uid(
        session, request_uid=request_uid)

    # Update start and stop commits
    request.commit_start = json_data.get('commit_start')
    request.commit_stop = json_data.get('commit_stop')

    # Update assignee
    assignee = get_user_from_json(session, json_data, key='assignee')
    if assignee:
        pagure.lib.add_pull_request_assignee(
            session, request, assignee.username,
            user=user.user, requestfolder=None)

    for comment in json_data['comments']:
        user = get_user_from_json(session, comment)
        commentobj = pagure.lib.get_request_comment(
            session, request_uid, comment['id'])
        if not commentobj:
            pagure.lib.add_pull_request_comment(
                session,
                request,
                commit=comment['commit'],
                tree_id=comment.get('tree_id') or None,
                filename=comment['filename'],
                row=comment['line'],
                comment=comment['comment'],
                user=user.username,
                requestfolder=None,
                notify=False,
            )
    session.commit()


def add_file_to_git(repo, issue, ticketfolder, user, filename, filestream):
    ''' Add a given file to the specified ticket git repository.

    :arg repo: the Project object from the database
    :arg ticketfolder: the folder on the filesystem where the git repo for
        tickets are stored
    :arg user: the user object with its username and email
    :arg filename: the name of the file to save
    :arg filestream: the actual content of the file

    '''

    if not ticketfolder:
        return

    # Prefix the filename with a timestamp:
    filename = '%s-%s' % (
        hashlib.sha256(filestream.read()).hexdigest(),
        werkzeug.secure_filename(filename)
    )

    # Get the fork
    repopath = os.path.join(ticketfolder, repo.path)

    # Clone the repo into a temp folder
    newpath = tempfile.mkdtemp(prefix='pagure-')
    new_repo = pygit2.clone_repository(repopath, newpath)

    folder_path = os.path.join(newpath, 'files')
    file_path = os.path.join(folder_path, filename)

    # Get the current index
    index = new_repo.index

    # Are we adding files
    added = False
    if not os.path.exists(file_path):
        added = True
    else:
        # File exists, remove the clone and return
        shutil.rmtree(newpath)
        return os.path.join('files', filename)

    if not os.path.exists(folder_path):
        os.mkdir(folder_path)

    # Write down what changed
    filestream.seek(0)
    with open(file_path, 'w') as stream:
        stream.write(filestream.read())

    # Retrieve the list of files that changed
    diff = new_repo.diff()
    files = [patch.new_file_path for patch in diff]

    # Add the changes to the index
    if added:
        index.add(os.path.join('files', filename))
    for filename in files:
        index.add(filename)

    # If not change, return
    if not files and not added:
        shutil.rmtree(newpath)
        return

    # See if there is a parent to this commit
    parent = None
    try:
        parent = new_repo.head.get_object().oid
    except pygit2.GitError:
        pass

    parents = []
    if parent:
        parents.append(parent)

    # Author/commiter will always be this one
    author = pygit2.Signature(
        name=user.username.encode('utf-8'),
        email=user.email.encode('utf-8')
    )

    # Actually commit
    new_repo.create_commit(
        'refs/heads/master',
        author,
        author,
        'Add file %s to ticket %s: %s' % (filename, issue.uid, issue.title),
        new_repo.index.write_tree(),
        parents)
    index.write()

    # Push to origin
    ori_remote = new_repo.remotes[0]
    master_ref = new_repo.lookup_reference('HEAD').resolve()
    refname = '%s:%s' % (master_ref.name, master_ref.name)

    PagureRepo.push(ori_remote, refname)

    # Remove the clone
    shutil.rmtree(newpath)

    return os.path.join('files', filename)


def update_file_in_git(
        repo, branch, branchto, filename, content, message, user, email):
    ''' Update a specific file in the specified repository with the content
    given and commit the change under the user's name.

    :arg repo: the Project object from the database
    :arg filename: the name of the file to save
    :arg content: the new content of the file
    :arg message: the message of the git commit
    :arg user: the user object with its username and email

    '''

    # Get the fork
    repopath = pagure.get_repo_path(repo)

    # Clone the repo into a temp folder
    newpath = tempfile.mkdtemp(prefix='pagure-')
    new_repo = pygit2.clone_repository(
        repopath, newpath, checkout_branch=branch)

    file_path = os.path.join(newpath, filename)

    # Get the current index
    index = new_repo.index

    # Write down what changed
    with open(file_path, 'w') as stream:
        stream.write(content.replace('\r', '').encode('utf-8'))

    # Retrieve the list of files that changed
    diff = new_repo.diff()
    files = []
    for p in diff:
        if hasattr(p, 'new_file_path'):
            files.append(p.new_file_path)
        elif hasattr(p, 'delta'):
            files.append(p.delta.new_file.path)

    # Add the changes to the index
    added = False
    for filename in files:
        added = True
        index.add(filename)

    # If not change, return
    if not files and not added:
        shutil.rmtree(newpath)
        return

    # See if there is a parent to this commit
    branch_ref = get_branch_ref(new_repo, branch)
    parent = branch_ref.get_object()

    # See if we need to create the branch
    nbranch_ref = None
    if branchto not in new_repo.listall_branches():
        nbranch_ref = new_repo.create_branch(branchto, parent)

    parents = []
    if parent:
        parents.append(parent.hex)

    # Author/commiter will always be this one
    author = pygit2.Signature(
        name=user.username.encode('utf-8'),
        email=email.encode('utf-8')
    )

    # Actually commit
    new_repo.create_commit(
        nbranch_ref.name if nbranch_ref else branch_ref.name,
        author,
        author,
        message.strip(),
        new_repo.index.write_tree(),
        parents)
    index.write()

    # Push to origin
    ori_remote = new_repo.remotes[0]
    refname = '%s:refs/heads/%s' % (
        nbranch_ref.name if nbranch_ref else branch_ref.name,
        branchto)

    try:
        PagureRepo.push(ori_remote, refname)
    except pygit2.GitError as err:  # pragma: no cover
        shutil.rmtree(newpath)
        raise pagure.exceptions.PagureException(
            'Commit could not be done: %s' % err)

    # Remove the clone
    shutil.rmtree(newpath)

    return os.path.join('files', filename)


def read_output(cmd, abspath, input=None, keepends=False, **kw):
    """ Read the output from the given command to run """
    if input:
        stdin = subprocess.PIPE
    else:
        stdin = None
    procs = subprocess.Popen(
        cmd,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=abspath,
        **kw)
    (out, err) = procs.communicate(input)
    retcode = procs.wait()
    if retcode:
        print 'ERROR: %s =-- %s' % (cmd, retcode)
        print out
        print err
    if not keepends:
        out = out.rstrip('\n\r')
    return out


def read_git_output(args, abspath, input=None, keepends=False, **kw):
    """Read the output of a Git command."""

    return read_output(
        ['git'] + args, abspath, input=input, keepends=keepends, **kw)


def read_git_lines(args, abspath, keepends=False, **kw):
    """Return the lines output by Git command.

    Return as single lines, with newlines stripped off."""

    return read_git_output(
        args, abspath, keepends=keepends, **kw
    ).splitlines(keepends)


def get_revs_between(oldrev, newrev, abspath, refname, forced=False):
    """ Yield revisions between HEAD and BASE. """

    cmd = ['rev-list', '%s...%s' % (oldrev, newrev)]
    if forced:
        head = get_default_branch(abspath)
        cmd.append('^%s' % head)
    if set(newrev) == set('0'):
        cmd = ['rev-list', '%s' % oldrev]
    elif set(oldrev) == set('0') or set(oldrev) == set('^0'):
        head = get_default_branch(abspath)
        cmd = ['rev-list', '%s' % newrev, '^%s' % head]
        if head in refname:
            cmd = ['rev-list', '%s' % newrev]
    return pagure.lib.git.read_git_lines(cmd, abspath)


def is_forced_push(oldrev, newrev, abspath):
    """ Returns wether there was a force push between HEAD and BASE.
    Doc: http://stackoverflow.com/a/12258773
    """

    # Returns if there was any commits deleted in the changeset
    cmd = ['rev-list', '%s' % oldrev, '^%s' % newrev]
    out = pagure.lib.git.read_git_lines(cmd, abspath)
    return len(out) > 0


def get_base_revision(torev, fromrev, abspath):
    """ Return the base revision between HEAD and BASE.
    This is useful in case of force-push.
    """
    cmd = ['merge-base', fromrev, torev]
    return pagure.lib.git.read_git_lines(cmd, abspath)


def get_default_branch(abspath):
    """ Return the default branch of a repo. """
    cmd = ['rev-parse', '--abbrev-ref', 'HEAD']
    out = pagure.lib.git.read_git_lines(cmd, abspath)
    if out:
        return out[0]
    else:
        return 'master'


def get_author(commit, abspath):
    ''' Return the name of the person that authored the commit. '''
    user = pagure.lib.git.read_git_lines(
        ['log', '-1', '--pretty=format:"%an"', commit],
        abspath)[0].replace('"', '')
    return user


def get_author_email(commit, abspath):
    ''' Return the email of the person that authored the commit. '''
    user = pagure.lib.git.read_git_lines(
        ['log', '-1', '--pretty=format:"%ae"', commit],
        abspath)[0].replace('"', '')
    return user


def get_repo_name(abspath):
    ''' Return the name of the git repo based on its path.
    '''
    repo_name = '.'.join(abspath.split(os.path.sep)[-1].split('.')[:-1])
    return repo_name


def get_username(abspath):
    ''' Return the username of the git repo based on its path.
    '''
    username = None
    repo = os.path.abspath(os.path.join(abspath, '..'))
    if pagure.APP.config['FORK_FOLDER'] in repo:
        username = repo.split(pagure.APP.config['FORK_FOLDER'])[1]
        if username.startswith('/'):
            username = username[1:]
    return username


def get_branch_ref(repo, branchname):
    ''' Return the reference to the specified branch or raises an exception.
    '''
    location = pygit2.GIT_BRANCH_LOCAL
    if branchname not in repo.listall_branches():
        branchname = 'origin/%s' % branchname
        location = pygit2.GIT_BRANCH_REMOTE
    branch_ref = repo.lookup_branch(branchname, location).resolve()

    if not branch_ref:
        raise pagure.exceptions.PagureException(
            'No refs found for %s' % branchname)
    return branch_ref


def merge_pull_request(
        session, request, username, request_folder, domerge=True):
    ''' Merge the specified pull-request.
    '''
    if request.remote:
        # Get the fork
        repopath = pagure.get_remote_repo_path(
            request.remote_git, request.branch_from)
    else:
        # Get the fork
        repopath = pagure.get_repo_path(request.project_from)

    fork_obj = PagureRepo(repopath)

    # Get the original repo
    parentpath = pagure.get_repo_path(request.project)

    # Clone the original repo into a temp folder
    newpath = tempfile.mkdtemp(prefix='pagure-pr-merge')
    new_repo = pygit2.clone_repository(parentpath, newpath)

    # Update the start and stop commits in the DB, one last time
    diff_commits = diff_pull_request(
        session, request, fork_obj, PagureRepo(parentpath),
        requestfolder=request_folder, with_diff=False)[0]

    if request.project.settings.get(
            'Enforce_signed-off_commits_in_pull-request', False):
        for commit in diff_commits:
            if 'signed-off-by' not in commit.message.lower():
                shutil.rmtree(newpath)
                raise pagure.exceptions.PagureException(
                    'This repo enforces that all commits are '
                    'signed off by their author. ')

    # Checkout the correct branch
    branch_ref = get_branch_ref(new_repo, request.branch)
    if not branch_ref:
        shutil.rmtree(newpath)
        raise pagure.exceptions.BranchNotFoundException(
            'Branch %s could not be found in the repo %s' % (
                request.branch, request.project.fullname
            ))

    new_repo.checkout(branch_ref)

    branch = get_branch_ref(fork_obj, request.branch_from)
    if not branch:
        shutil.rmtree(newpath)
        raise pagure.exceptions.BranchNotFoundException(
            'Branch %s could not be found in the repo %s' % (
                request.branch_from, request.project_from.fullname
                if request.project_from else request.remote_git
            ))

    repo_commit = fork_obj[branch.get_object().hex]

    ori_remote = new_repo.remotes[0]
    # Add the fork as remote repo
    reponame = '%s_%s' % (request.user.user, request.uid)

    remote = new_repo.create_remote(reponame, repopath)

    # Fetch the commits
    remote.fetch()

    merge = new_repo.merge(repo_commit.oid)
    if merge is None:
        mergecode = new_repo.merge_analysis(repo_commit.oid)[0]

    refname = '%s:refs/heads/%s' % (branch_ref.name, request.branch)
    if (
            (merge is not None and merge.is_uptodate)
            or
            (merge is None and
             mergecode & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE)):

        if domerge:
            pagure.lib.close_pull_request(
                session, request, username,
                requestfolder=request_folder)
            shutil.rmtree(newpath)
            try:
                session.commit()
            except SQLAlchemyError as err:  # pragma: no cover
                session.rollback()
                pagure.APP.logger.exception(err)
                raise pagure.exceptions.PagureException(
                    'Could not close this pull-request')
            raise pagure.exceptions.PagureException(
                'Nothing to do, changes were already merged')
        else:
            request.merge_status = 'NO_CHANGE'
            session.commit()
            shutil.rmtree(newpath)
            return 'NO_CHANGE'

    elif (
            (merge is not None and merge.is_fastforward)
            or
            (merge is None and
             mergecode & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD)):

        if domerge:
            if not request.project.settings.get('always_merge', False):
                if merge is not None:
                    # This is depending on the pygit2 version
                    branch_ref.target = merge.fastforward_oid
                elif merge is None and mergecode is not None:
                    branch_ref.set_target(repo_commit.oid.hex)
            else:
                tree = new_repo.index.write_tree()
                head = new_repo.lookup_reference('HEAD').get_object()
                user_obj = pagure.lib.__get_user(session, username)
                author = pygit2.Signature(
                    user_obj.fullname.encode('utf-8'),
                    user_obj.default_email.encode('utf-8'))
                new_repo.create_commit(
                    'refs/heads/%s' % request.branch,
                    author,
                    author,
                    'Merge #%s `%s`' % (request.id, request.title),
                    tree,
                    [head.hex, repo_commit.oid.hex])

            PagureRepo.push(ori_remote, refname)
        else:
            request.merge_status = 'FFORWARD'
            session.commit()
            shutil.rmtree(newpath)
            return 'FFORWARD'

    else:
        tree = None
        try:
            tree = new_repo.index.write_tree()
        except pygit2.GitError:
            shutil.rmtree(newpath)
            if domerge:
                raise pagure.exceptions.PagureException('Merge conflicts!')
            else:
                request.merge_status = 'CONFLICTS'
                session.commit()
                return 'CONFLICTS'

        if domerge:
            head = new_repo.lookup_reference('HEAD').get_object()
            user_obj = pagure.lib.__get_user(session, username)
            author = pygit2.Signature(
                user_obj.fullname.encode('utf-8'),
                user_obj.default_email.encode('utf-8'))
            new_repo.create_commit(
                'refs/heads/%s' % request.branch,
                author,
                author,
                'Merge #%s `%s`' % (request.id, request.title),
                tree,
                [head.hex, repo_commit.oid.hex])
            PagureRepo.push(ori_remote, refname)

        else:
            request.merge_status = 'MERGE'
            session.commit()
            shutil.rmtree(newpath)
            return 'MERGE'


    # Update status
    pagure.lib.close_pull_request(
        session, request, username,
        requestfolder=request_folder,
    )
    try:
        # Reset the merge_status of all opened PR to refresh their cache
        pagure.lib.reset_status_pull_request(session, request.project)
        session.commit()
    except SQLAlchemyError as err:  # pragma: no cover
        session.rollback()
        pagure.APP.logger.exception(err)
        shutil.rmtree(newpath)
        raise pagure.exceptions.PagureException(
            'Could not update this pull-request in the database')
    shutil.rmtree(newpath)

    return 'Changes merged!'


def diff_pull_request(
        session, request, repo_obj, orig_repo, requestfolder,
        with_diff=True):
    """ Returns the diff and the list of commits between the two git repos
    mentionned in the given pull-request.
    """

    commitid = None
    diff = None
    diff_commits = []
    branch = repo_obj.lookup_branch(request.branch_from)
    if branch:
        commitid = branch.get_object().hex

    if not repo_obj.is_empty and not orig_repo.is_empty:
        # Pull-request open
        master_commits = [
            commit.oid.hex
            for commit in orig_repo.walk(
                orig_repo.lookup_branch(request.branch).get_object().hex,
                pygit2.GIT_SORT_TIME)
        ]
        for commit in repo_obj.walk(commitid, pygit2.GIT_SORT_TIME):
            if request.status and commit.oid.hex in master_commits:
                break
            diff_commits.append(commit)

        if request.status and diff_commits:
            first_commit = repo_obj[diff_commits[-1].oid.hex]
            # Check if we can still rely on the merge_status
            commenttext = None
            if request.commit_start != first_commit.oid.hex or\
                    request.commit_stop != diff_commits[0].oid.hex:
                request.merge_status = None
                if request.commit_start:
                    new_commits_count = 0
                    commenttext = ""
                    for i in diff_commits:
                        if i.oid.hex == request.commit_stop:
                            break
                        new_commits_count = new_commits_count + 1
                        commenttext = '%s * %s\n' % (commenttext, i.message.strip().split('\n')[0])
                    if new_commits_count == 1:
                        commenttext = "**%d new commit added**\n\n%s" % (new_commits_count, commenttext)
                    else:
                        commenttext = "**%d new commits added**\n\n%s" % (new_commits_count, commenttext)
                if request.commit_start and \
                        request.commit_start != first_commit.oid.hex:
                    commenttext = 'rebased'
            request.commit_start = first_commit.oid.hex
            request.commit_stop = diff_commits[0].oid.hex
            session.add(request)
            session.commit()
            if commenttext:
                pagure.lib.add_pull_request_comment(
                    session, request,
                    commit=None, tree_id=None, filename=None, row=None,
                    comment='%s' % commenttext,
                    user=request.user.username,
                    requestfolder=requestfolder,
                    notify=False, notification=True
                )
                session.commit()
            pagure.lib.git.update_git(
                request, repo=request.project,
                repofolder=requestfolder)

        if diff_commits and with_diff:
            diff = repo_obj.diff(
                repo_obj.revparse_single(diff_commits[-1].parents[0].oid.hex),
                repo_obj.revparse_single(diff_commits[0].oid.hex)
            )

    elif orig_repo.is_empty and not repo_obj.is_empty:
        for commit in repo_obj.walk(commitid, pygit2.GIT_SORT_TIME):
            diff_commits.append(commit)
        if request.status and diff_commits:
            first_commit = repo_obj[diff_commits[-1].oid.hex]
            # Check if we can still rely on the merge_status
            if request.commit_start != first_commit.oid.hex or\
                    request.commit_stop != diff_commits[0].oid.hex:
                request.merge_status = None
            request.commit_start = first_commit.oid.hex
            request.commit_stop = diff_commits[0].oid.hex
            session.add(request)
            session.commit()
            pagure.lib.git.update_git(
                request, repo=request.project,
                repofolder=requestfolder)

        repo_commit = repo_obj[request.commit_stop]
        if with_diff:
            diff = repo_commit.tree.diff_to_tree(swap=True)
    else:
        raise pagure.exceptions.PagureException(
            'Fork is empty, there are no commits to request pulling')

    return (diff_commits, diff)


def get_git_tags(project):
    """ Returns the list of tags created in the git repositorie of the
    specified project.
    """
    repopath = pagure.get_repo_path(project)
    repo_obj = PagureRepo(repopath)

    tags = [
        tag.split('refs/tags/')[1]
        for tag in repo_obj.listall_references()
        if 'refs/tags/' in tag
    ]

    return tags


def get_git_tags_objects(project):
    """ Returns the list of references of the tags created in the git
    repositorie the specified project.
    The list is sorted using the time of the commit associated to the tag """
    repopath = pagure.get_repo_path(project)
    repo_obj = PagureRepo(repopath)
    tags = {}
    for tag in repo_obj.listall_references():
        if 'refs/tags/' in tag and repo_obj.lookup_reference(tag):
            commit_time = ""
            theobject = repo_obj[repo_obj.lookup_reference(tag).target]
            objecttype = ""
            if isinstance(theobject, pygit2.Tag):
                commit_time = theobject.get_object().commit_time
                objecttype = "tag"
            elif isinstance(theobject, pygit2.Commit):
                commit_time = theobject.commit_time
                objecttype = "commit"

            tags[commit_time] = {
                "object": repo_obj[repo_obj.lookup_reference(tag).target],
                "tagname": tag.replace("refs/tags/",""),
                "date": commit_time,
                "objecttype": objecttype,
                "head_msg": None,
                "body_msg": None,
            }
            if objecttype == 'tag':
                head_msg, _, body_msg = tags[commit_time][
                    "object"].message.partition('\n')
                if body_msg.strip().endswith('\n-----END PGP SIGNATURE-----'):
                    body_msg = body_msg.rsplit(
                        '-----BEGIN PGP SIGNATURE-----', 1)[0].strip()
                tags[commit_time]["head_msg"] = head_msg
                tags[commit_time]["body_msg"] = body_msg
    sorted_tags = []

    for tag in sorted(tags, reverse=True):
        sorted_tags.append(tags[tag])

    return sorted_tags
