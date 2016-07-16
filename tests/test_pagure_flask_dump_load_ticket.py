# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

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


class PagureFlaskDumpLoadTicketTests(tests.Modeltests):
    """ Tests for flask application for dumping and re-loading the JSON of
    a ticket.
    """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskDumpLoadTicketTests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.SESSION = self.session
        pagure.lib.SESSION = self.session
        pagure.ui.app.SESSION = self.session
        pagure.ui.filters.SESSION = self.session
        pagure.ui.fork.SESSION = self.session
        pagure.ui.repo.SESSION = self.session

        pagure.APP.config['GIT_FOLDER'] = os.path.join(tests.HERE, 'repos')
        pagure.APP.config['FORK_FOLDER'] = os.path.join(tests.HERE, 'forks')
        pagure.APP.config['TICKETS_FOLDER'] = os.path.join(
            tests.HERE, 'tickets')
        pagure.APP.config['DOCS_FOLDER'] = os.path.join(
            tests.HERE, 'docs')
        pagure.APP.config['REQUESTS_FOLDER'] = os.path.join(
            tests.HERE, 'requests')
        self.app = pagure.APP.test_client()

    @patch('pagure.lib.notify.send_email')
    def test_dumping_ticket(self, send_email):
        """ Test dumping a ticket into a JSON blob. """
        send_email.return_value = True

        tests.create_projects(self.session)

        # Create repo
        self.gitrepo = os.path.join(tests.HERE, 'tickets', 'test.git')
        repopath = os.path.join(tests.HERE, 'tickets')
        os.makedirs(self.gitrepo)
        repo_obj = pygit2.init_repository(self.gitrepo, bare=True)

        repo = pagure.lib.get_project(self.session, 'test')
        # Create an issue to play with
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue',
            content='We should work on this',
            user='pingou',
            ticketfolder=repopath
        )
        self.assertEqual(msg.title, 'Test issue')

        # Need another two issue to test the dependencie chain
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue #2',
            content='Another bug',
            user='pingou',
            ticketfolder=repopath
        )
        self.assertEqual(msg.title, 'Test issue #2')
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue #3',
            content='That would be nice feature no?',
            user='foo',
            ticketfolder=repopath
        )
        self.assertEqual(msg.title, 'Test issue #3')

        issue = pagure.lib.search_issues(self.session, repo, issueid=1)
        issue2 = pagure.lib.search_issues(self.session, repo, issueid=2)
        issue3 = pagure.lib.search_issues(self.session, repo, issueid=3)

        # Add a couple of comment on the ticket
        msg = pagure.lib.add_issue_comment(
            session=self.session,
            issue=issue,
            comment='Hey look a comment!',
            user='foo',
            ticketfolder=repopath,
        )
        self.session.commit()
        self.assertEqual(msg, 'Comment added')
        msg = pagure.lib.add_issue_comment(
            session=self.session,
            issue=issue,
            comment='crazy right?',
            user='pingou',
            ticketfolder=repopath,
        )
        self.session.commit()
        self.assertEqual(msg, 'Comment added')
        # Assign the ticket to someone
        msg = pagure.lib.add_issue_assignee(
            session=self.session,
            issue=issue,
            assignee='pingou',
            user='pingou',
            ticketfolder=repopath,
        )
        self.session.commit()
        self.assertEqual(msg, 'Issue assigned')
        # Add a couple of tags on the ticket
        msg = pagure.lib.add_tag_obj(
            session=self.session,
            obj=issue,
            tags=[' feature ', 'future '],
            user='pingou',
            ticketfolder=repopath,
        )
        self.session.commit()
        self.assertEqual(msg, 'Tag added: feature, future')
        # Add dependencies
        msg = pagure.lib.add_issue_dependency(
            session=self.session,
            issue=issue,
            issue_blocked=issue2,
            user='pingou',
            ticketfolder=repopath,
        )
        self.session.commit()
        self.assertEqual(msg, 'Dependency added')
        msg = pagure.lib.add_issue_dependency(
            session=self.session,
            issue=issue3,
            issue_blocked=issue,
            user='foo',
            ticketfolder=repopath,
        )
        self.session.commit()
        self.assertEqual(msg, 'Dependency added')

        # Dump the JSON
        pagure.lib.git.update_git(issue, repo, repopath)
        repo = pygit2.Repository(self.gitrepo)
        cnt = len([commit
            for commit in repo.walk(
                repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)])
        self.assertEqual(cnt, 10)

        last_commit = repo.revparse_single('HEAD')
        patch = pagure.lib.git.commit_to_patch(repo, last_commit)
        for line in patch.split('\n'):
            if line.startswith('--- a/'):
                fileid = line.split('--- a/')[1]
                break

        newpath = tempfile.mkdtemp(prefix='pagure-dump-load')
        clone_repo = pygit2.clone_repository(self.gitrepo, newpath)

        self.assertEqual(len(os.listdir(newpath)), 4)

        ticket_json = os.path.join(tests.HERE, 'test_ticket.json')
        self.assertFalse(os.path.exists(ticket_json))
        shutil.copyfile(os.path.join(newpath, fileid), ticket_json)
        self.assertTrue(os.path.exists(ticket_json))

        shutil.rmtree(newpath)

    @patch('pagure.lib.notify.send_email')
    def test_reload_ticket(self, send_email):
        """ Test reloading a ticket from a JSON blob. """
        send_email.return_value = True
        ticket_json = os.path.join(tests.HERE, 'test_ticket.json')
        self.assertTrue(os.path.exists(ticket_json))

        tests.create_projects(self.session)

        jsondata = None
        with open(ticket_json) as stream:
            jsondata = json.load(stream)
        self.assertNotEqual(jsondata, None)

        pagure.lib.git.update_ticket_from_git(
            self.session,
            reponame='test',
            username=None,
            issue_uid='foobar',
            json_data=jsondata,
        )

        # Post loading
        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(len(repo.issues), 1)
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        # Check after re-loading
        self.assertEqual(len(issue.comments), 2)
        self.assertEqual(len(issue.tags), 2)
        self.assertEqual(issue.tags_text, ['future', 'feature'])
        self.assertEqual(issue.assignee.username, 'pingou')
        self.assertEqual(issue.children, [])
        self.assertEqual(issue.parents, [])

        self.assertTrue(os.path.exists(ticket_json))
        os.unlink(ticket_json)
        self.assertFalse(os.path.exists(ticket_json))


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(
        PagureFlaskDumpLoadTicketTests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
