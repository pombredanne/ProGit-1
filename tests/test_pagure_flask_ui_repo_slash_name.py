# -*- coding: utf-8 -*-

"""
 (c) 2016 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import json
import unittest
import shutil
import sys
import tempfile
import os

import pygit2
from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.lib
import tests
from pagure.lib.repo import PagureRepo


class PagureFlaskSlashInNametests(tests.Modeltests):
    """ Tests for flask application when the project contains a '/'.
    """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskSlashInNametests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.SESSION = self.session
        pagure.lib.SESSION = self.session
        pagure.ui.app.SESSION = self.session
        pagure.ui.filters.SESSION = self.session
        pagure.ui.fork.SESSION = self.session
        pagure.ui.repo.SESSION = self.session
        pagure.ui.issues.SESSION = self.session

        pagure.APP.config['GIT_FOLDER'] = os.path.join(tests.HERE, 'repos')
        pagure.APP.config['FORK_FOLDER'] = os.path.join(tests.HERE, 'forks')
        pagure.APP.config['TICKETS_FOLDER'] = os.path.join(
            tests.HERE, 'tickets')
        pagure.APP.config['DOCS_FOLDER'] = os.path.join(
            tests.HERE, 'docs')
        pagure.APP.config['REQUESTS_FOLDER'] = os.path.join(
            tests.HERE, 'requests')
        self.app = pagure.APP.test_client()

    def set_up_git_repo(self, name='test'):
        """ Set up the git repo to play with. """

        # Create a git repo to play with
        gitrepo = os.path.join(tests.HERE, 'repos', '%s.git' % name)
        repo = pygit2.init_repository(gitrepo, bare=True)

        newpath = tempfile.mkdtemp(prefix='pagure-other-test')
        repopath = os.path.join(newpath, 'test')
        clone_repo = pygit2.clone_repository(gitrepo, repopath)

        # Create a file in that git repo
        with open(os.path.join(repopath, 'sources'), 'w') as stream:
            stream.write('foo\n bar')
        clone_repo.index.add('sources')
        clone_repo.index.write()

        # Commits the files added
        tree = clone_repo.index.write_tree()
        author = pygit2.Signature(
            'Alice Author', 'alice@authors.tld')
        committer = pygit2.Signature(
            'Cecil Committer', 'cecil@committers.tld')
        clone_repo.create_commit(
            'refs/heads/master',  # the name of the reference to update
            author,
            committer,
            'Add sources file for testing',
            # binary string representing the tree object ID
            tree,
            # list of binary strings representing parents of the new commit
            []
        )
        refname = 'refs/heads/master'
        ori_remote = clone_repo.remotes[0]
        PagureRepo.push(ori_remote, refname)

    @patch('pagure.lib.notify.send_email')
    def test_view_repo_empty(self, send_email):
        """ Test the view_repo endpoint when the project has a slash in its
        name.
        """
        send_email.return_value = True

        tests.create_projects(self.session)
        # Non-existant git repo
        output = self.app.get('/test')
        self.assertEqual(output.status_code, 404)

        # Create a git repo to play with
        gitrepo = os.path.join(tests.HERE, 'repos', 'test.git')
        repo = pygit2.init_repository(gitrepo, bare=True)

        # With git repo
        output = self.app.get('/test')
        self.assertEqual(output.status_code, 200)
        self.assertIn(
            '<div class="card-block">\n            '
            '<h5><strong>Owners</strong></h5>', output.data)
        self.assertIn(
            '<p>The Project Creator has not pushed any code yet</p>',
            output.data)

        # We can't create the project `forks/test` the normal way
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            self.session,
            name='forks/test',
            description='test project forks/test',
            url='',
            avatar_email='',
            user='pingou',
            blacklist=pagure.APP.config['BLACKLISTED_PROJECTS'],
            allowed_prefix=pagure.APP.config['ALLOWED_PREFIX'],
            gitfolder=pagure.APP.config['GIT_FOLDER'],
            docfolder=pagure.APP.config['DOCS_FOLDER'],
            ticketfolder=pagure.APP.config['TICKETS_FOLDER'],
            requestfolder=pagure.APP.config['REQUESTS_FOLDER'],
        )

        # So just put it in the DB
        item = pagure.lib.model.Project(
            user_id=1,  # pingou
            name='forks/test',
            description='test project forks/test',
            hook_token='aaabbbcccddd',
        )
        self.session.add(item)
        self.session.commit()

        # Create a git repo to play with
        gitrepo = os.path.join(tests.HERE, 'repos', 'forks/test.git')
        repo = pygit2.init_repository(gitrepo, bare=True)

        output = self.app.get('/forks/test')
        self.assertEqual(output.status_code, 200)
        self.assertIn(
            '<div class="card-block">\n            '
            '<h5><strong>Owners</strong></h5>', output.data)
        self.assertIn(
            '<p>The Project Creator has not pushed any code yet</p>',
            output.data)

        output = self.app.get('/forks/test/issues')
        self.assertEqual(output.status_code, 200)
        self.assertIn(
            '<title>Issues - forks/test - Pagure</title>', output.data)
        self.assertIn(
            '<td colspan="5" class="noresult">No issues found</td>',
            output.data)

    @patch('pagure.lib.notify.send_email')
    def test_view_repo(self, send_email):
        """ Test the view_repo endpoint when the project has a slash in its
        name.
        """
        send_email.return_value = True

        tests.create_projects(self.session)
        # Non-existant git repo
        output = self.app.get('/test')
        self.assertEqual(output.status_code, 404)

        self.set_up_git_repo()

        # With git repo
        output = self.app.get('/test')
        self.assertEqual(output.status_code, 200)
        self.assertIn(
            '<div class="card-block">\n            '
            '<h5><strong>Owners</strong></h5>', output.data)

        # We can't create the project `forks/test` the normal way
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            self.session,
            name='forks/test',
            description='test project forks/test',
            url='',
            avatar_email='',
            user='pingou',
            blacklist=pagure.APP.config['BLACKLISTED_PROJECTS'],
            allowed_prefix=pagure.APP.config['ALLOWED_PREFIX'],
            gitfolder=pagure.APP.config['GIT_FOLDER'],
            docfolder=pagure.APP.config['DOCS_FOLDER'],
            ticketfolder=pagure.APP.config['TICKETS_FOLDER'],
            requestfolder=pagure.APP.config['REQUESTS_FOLDER'],
        )

        # So just put it in the DB
        item = pagure.lib.model.Project(
            user_id=1,  # pingou
            name='forks/test',
            description='test project forks/test',
            hook_token='aaabbbcccddd',
        )
        self.session.add(item)
        self.session.commit()

        self.set_up_git_repo(name='forks/test')

        # Front page shows fine
        output = self.app.get('/forks/test')
        self.assertEqual(output.status_code, 200)
        self.assertIn(
            '<div class="card-block">\n            '
            '<h5><strong>Owners</strong></h5>', output.data)
        self.assertIn('Add sources file for testing', output.data)
        self.assertIn(
            '<title>Overview - forks/test - Pagure</title>', output.data)

        # Issues list shows fine
        output = self.app.get('/forks/test/issues')
        self.assertEqual(output.status_code, 200)
        self.assertIn(
            '<title>Issues - forks/test - Pagure</title>', output.data)
        self.assertIn(
            '<td colspan="5" class="noresult">No issues found</td>',
            output.data)

        # Try accessing the commit
        gitrepo = os.path.join(tests.HERE, 'repos', 'test.git')
        repo = pygit2.Repository(gitrepo)
        master_branch = repo.lookup_branch('master')
        first_commit = master_branch.get_object().hex

        output = self.app.get('/forks/test/c/%s' % first_commit)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Commit - forks/test ', output.data)
        self.assertIn(
            '<span class="label label-success">+2</span>          </span>',
            output.data)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(
        PagureFlaskSlashInNametests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
