# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import unittest
import shutil
import sys
import os

from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.lib
import tests


class PagureLibModeltests(tests.Modeltests):
    """ Tests for pagure.lib.model """

    def test_user__repr__(self):
        """ Test the User.__repr__ function of pagure.lib.model. """
        item = pagure.lib.search_user(self.session, email='foo@bar.com')
        self.assertEqual(str(item), 'User: 2 - name foo')
        self.assertEqual('foo', item.user)
        self.assertEqual('foo', item.username)
        self.assertEqual([], item.groups)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_issue__repr__(self, p_send_email, p_ugt):
        """ Test the Issue.__repr__ function of pagure.lib.model. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        tests.create_projects(self.session)
        repo = pagure.lib.get_project(self.session, 'test')

        # Create an issue
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue',
            content='We should work on this',
            user='pingou',
            ticketfolder=None
        )
        self.assertEqual(msg.title, 'Test issue')

        issues = pagure.lib.search_issues(self.session, repo)
        self.assertEqual(len(issues), 1)
        self.assertEqual(
            str(issues[0]),
            'Issue(1, project:test, user:pingou, title:Test issue)')

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_pullrequest__repr__(self, p_send_email, p_ugt):
        """ Test the PullRequest.__repr__ function of pagure.lib.model. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        tests.create_projects(self.session)
        # Create a forked repo
        item = pagure.lib.model.Project(
            user_id=1,  # pingou
            name='test',
            description='test project #1',
            parent_id=1,
            hook_token='aaabbbyyy',
        )
        self.session.commit()
        self.session.add(item)

        repo = pagure.lib.get_project(self.session, 'test')
        forked_repo = pagure.lib.get_project(
            self.session, 'test', user='pingou')

        # Create an pull-request
        req = pagure.lib.new_pull_request(
            session=self.session,
            repo_from=forked_repo,
            branch_from='master',
            repo_to=repo,
            branch_to='master',
            title='test pull-request',
            user='pingou',
            requestfolder=None,
        )
        self.assertEqual(req.id, 1)
        self.assertEqual(req.title, 'test pull-request')

        self.assertEqual(
            str(req),
            'PullRequest(1, project:test, user:pingou, '
            'title:test pull-request)')

        request = pagure.lib.search_pull_requests(self.session, requestid=1)
        self.assertEqual(
            str(request),
            'PullRequest(1, project:test, user:pingou, '
            'title:test pull-request)')

    def test_paguregroup__repr__(self):
        """ Test the PagureGroup.__repr__ function of pagure.lib.model. """
        item = pagure.lib.model.PagureGroup(
            group_name='admin',
            user_id=1,
        )
        self.session.add(item)
        self.session.commit()

        self.assertEqual(str(item), 'Group: 1 - name admin')

    def test_tagissue__repr__(self):
        """ Test the TagIssue.__repr__ function of pagure.lib.model. """
        self.test_issue__repr__()
        repo = pagure.lib.get_project(self.session, 'test')
        issues = pagure.lib.search_issues(self.session, repo)
        self.assertEqual(len(issues), 1)

        item = pagure.lib.model.Tag(tag='foo')
        self.session.add(item)
        self.session.commit()

        item = pagure.lib.model.TagIssue(
            issue_uid=issues[0].uid,
            tag='foo',
        )
        self.session.add(item)
        self.session.commit()

        self.assertEqual(str(item), 'TagIssue(issue:1, tag:foo)')


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(PagureLibModeltests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
