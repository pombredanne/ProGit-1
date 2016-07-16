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
import pagure.lib.model
import tests


class PagureLibtests(tests.Modeltests):
    """ Tests for pagure.lib """

    def test_get_next_id(self):
        """ Test the get_next_id function of pagure.lib. """
        tests.create_projects(self.session)
        self.assertEqual(1, pagure.lib.get_next_id(self.session, 1))

    def test_search_user_all(self):
        """ Test the search_user of pagure.lib. """

        # Retrieve all users
        items = pagure.lib.search_user(self.session)
        self.assertEqual(2, len(items))
        self.assertEqual(2, items[0].id)
        self.assertEqual('foo', items[0].user)
        self.assertEqual('foo', items[0].username)
        self.assertEqual([], items[1].groups)
        self.assertEqual(1, items[1].id)
        self.assertEqual('pingou', items[1].user)
        self.assertEqual('pingou', items[1].username)
        self.assertEqual([], items[1].groups)

    def test_search_user_username(self):
        """ Test the search_user of pagure.lib. """

        # Retrieve user by username
        item = pagure.lib.search_user(self.session, username='foo')
        self.assertEqual('foo', item.user)
        self.assertEqual('foo', item.username)
        self.assertEqual([], item.groups)

        item = pagure.lib.search_user(self.session, username='bar')
        self.assertEqual(None, item)

    def test_search_user_email(self):
        """ Test the search_user of pagure.lib. """

        # Retrieve user by email
        item = pagure.lib.search_user(self.session, email='foo@foo.com')
        self.assertEqual(None, item)

        item = pagure.lib.search_user(self.session, email='foo@bar.com')
        self.assertEqual('foo', item.user)
        self.assertEqual('foo', item.username)
        self.assertEqual([], item.groups)
        self.assertEqual(
            ['foo@bar.com'], [email.email for email in item.emails])

        item = pagure.lib.search_user(self.session, email='foo@pingou.com')
        self.assertEqual('pingou', item.user)
        self.assertEqual(
            ['bar@pingou.com', 'foo@pingou.com'],
            [email.email for email in item.emails])

    def test_search_user_token(self):
        """ Test the search_user of pagure.lib. """

        # Retrieve user by token
        item = pagure.lib.search_user(self.session, token='aaa')
        self.assertEqual(None, item)

        item = pagure.lib.model.User(
            user='pingou2',
            fullname='PY C',
            token='aaabbb',
            default_email='bar@pingou.com',
        )
        self.session.add(item)
        self.session.commit()

        item = pagure.lib.search_user(self.session, token='aaabbb')
        self.assertEqual('pingou2', item.user)
        self.assertEqual('PY C', item.fullname)

    def test_search_user_pattern(self):
        """ Test the search_user of pagure.lib. """

        # Retrieve user by pattern
        item = pagure.lib.search_user(self.session, pattern='a*')
        self.assertEqual([], item)

        item = pagure.lib.model.User(
            user='pingou2',
            fullname='PY C',
            token='aaabbb',
            default_email='bar@pingou.com',
        )
        self.session.add(item)
        self.session.commit()

        items = pagure.lib.search_user(self.session, pattern='p*')
        self.assertEqual(2, len(items))
        self.assertEqual(1, items[0].id)
        self.assertEqual('pingou', items[0].user)
        self.assertEqual('pingou', items[0].username)
        self.assertEqual([], items[0].groups)
        self.assertEqual(
            ['bar@pingou.com', 'foo@pingou.com'],
            [email.email for email in items[0].emails])
        self.assertEqual(3, items[1].id)
        self.assertEqual('pingou2', items[1].user)
        self.assertEqual('pingou2', items[1].username)
        self.assertEqual([], items[1].groups)
        self.assertEqual(
            [], [email.email for email in items[1].emails])

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_new_issue(self, p_send_email, p_ugt):
        """ Test the new_issue of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        tests.create_projects(self.session)
        repo = pagure.lib.get_project(self.session, 'test')

        # Before
        issues = pagure.lib.search_issues(self.session, repo)
        self.assertEqual(len(issues), 0)
        self.assertEqual(repo.open_tickets, 0)
        self.assertEqual(repo.open_tickets_public, 0)

        # See where it fails
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_issue,
            session=self.session,
            repo=repo,
            title='Test issue',
            content='We should work on this',
            user='blah',
            ticketfolder=None
        )

        # Add an extra user to project `foo`
        repo = pagure.lib.get_project(self.session, 'test')
        msg = pagure.lib.add_user_to_project(
            session=self.session,
            project=repo,
            new_user='foo',
            user='pingou'
        )
        self.session.commit()
        self.assertEqual(msg, 'User added')

        # Try adding again this extra user to project `foo`
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_user_to_project,
            session=self.session,
            project=repo,
            new_user='foo',
            user='pingou'
        )
        self.session.commit()
        self.assertEqual(msg, 'User added')

        # Create issues to play with
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue',
            content='We should work on this',
            user='pingou',
            ticketfolder=None
        )
        self.session.commit()
        self.assertEqual(msg.title, 'Test issue')
        self.assertEqual(repo.open_tickets, 1)
        self.assertEqual(repo.open_tickets_public, 1)

        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue #2',
            content='We should work on this for the second time',
            user='foo',
            status='Open',
            ticketfolder=None
        )
        self.session.commit()
        self.assertEqual(msg.title, 'Test issue #2')
        self.assertEqual(repo.open_tickets, 2)
        self.assertEqual(repo.open_tickets_public, 2)

        # After
        issues = pagure.lib.search_issues(self.session, repo)
        self.assertEqual(len(issues), 2)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_edit_issue(self, p_send_email, p_ugt):
        """ Test the edit_issue of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()

        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=2)

        self.assertEqual(repo.open_tickets, 2)
        self.assertEqual(repo.open_tickets_public, 2)

        # Edit the issue
        msg = pagure.lib.edit_issue(
            session=self.session,
            issue=issue,
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, None)

        msg = pagure.lib.edit_issue(
            session=self.session,
            issue=issue,
            user='pingou',
            ticketfolder=None,
            title='Test issue #2',
            content='We should work on this for the second time',
            status='Open',
        )
        self.session.commit()
        self.assertEqual(msg, None)

        msg = pagure.lib.edit_issue(
            session=self.session,
            issue=issue,
            user='pingou',
            ticketfolder=None,
            title='Foo issue #2',
            content='We should work on this period',
            status='Invalid',
            private=True,
        )
        self.session.commit()
        self.assertEqual(msg, 'Successfully edited issue #2')

        self.assertEqual(repo.open_tickets, 1)
        self.assertEqual(repo.open_tickets_public, 1)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_add_issue_dependency(self, p_send_email, p_ugt):
        """ Test the add_issue_dependency of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)
        issue_blocked = pagure.lib.search_issues(
            self.session, repo, issueid=2)

        # Before
        self.assertEqual(issue.parents, [])
        self.assertEqual(issue.children, [])
        self.assertEqual(issue_blocked.parents, [])
        self.assertEqual(issue_blocked.children, [])

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_issue_dependency,
            session=self.session,
            issue=issue,
            issue_blocked=issue,
            user='pingou',
            ticketfolder=None)

        msg = pagure.lib.add_issue_dependency(
            session=self.session,
            issue=issue,
            issue_blocked=issue_blocked,
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Dependency added')

        # After
        self.assertEqual(len(issue.parents), 1)
        self.assertEqual(issue.parents[0].id, 2)
        self.assertEqual(len(issue.children), 0)
        self.assertEqual(issue.children, [])

        self.assertEqual(len(issue_blocked.parents), 0)
        self.assertEqual(issue_blocked.parents, [])
        self.assertEqual(len(issue_blocked.children), 1)
        self.assertEqual(issue_blocked.children[0].id, 1)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_add_tag_obj(self, p_send_email, p_ugt):
        """ Test the add_tag_obj of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_edit_issue()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        # Add a tag to the issue
        msg = pagure.lib.add_tag_obj(
            session=self.session,
            obj=issue,
            tags='tag1',
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Tag added: tag1')

        # Try a second time
        msg = pagure.lib.add_tag_obj(
            session=self.session,
            obj=issue,
            tags='tag1',
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Nothing to add')

        issues = pagure.lib.search_issues(self.session, repo, tags='tag1')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 1)
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Open')
        self.assertEqual([tag.tag for tag in issues[0].tags], ['tag1'])

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_remove_tags(self, p_send_email, p_ugt):
        """ Test the remove_tags of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_add_tag_obj()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.remove_tags,
            session=self.session,
            project=repo,
            tags='foo',
            user='pingou',
            ticketfolder=None)

        msgs = pagure.lib.remove_tags(
            session=self.session,
            project=repo,
            tags='tag1',
            user='pingou',
            ticketfolder=None)

        self.assertEqual(msgs, [u'Removed tag: tag1'])

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_remove_tags_obj(self, p_send_email, p_ugt):
        """ Test the remove_tags_obj of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_add_tag_obj()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        msgs = pagure.lib.remove_tags_obj(
            session=self.session,
            obj=issue,
            tags='tag1',
            user='pingou',
            ticketfolder=None)

        self.assertEqual(msgs, 'Removed tag: tag1')

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_edit_issue_tags(self, p_send_email, p_ugt):
        """ Test the edit_issue_tags of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_add_tag_obj()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.edit_issue_tags,
            session=self.session,
            project=repo,
            old_tag='foo',
            new_tag='bar',
            user='pingou',
            ticketfolder=None,
        )

        msgs = pagure.lib.edit_issue_tags(
            session=self.session,
            project=repo,
            old_tag='tag1',
            new_tag='tag2',
            user='pingou',
            ticketfolder=None,
        )
        self.session.commit()
        self.assertEqual(msgs, ['Edited tag: tag1 to tag2'])

        # Add a new tag
        msg = pagure.lib.add_tag_obj(
            session=self.session,
            obj=issue,
            tags='tag3',
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Tag added: tag3')
        self.assertEqual([tag.tag for tag in issue.tags], ['tag2', 'tag3'])

        # Rename an existing tag into another existing one
        msgs = pagure.lib.edit_issue_tags(
            session=self.session,
            project=repo,
            old_tag='tag2',
            new_tag='tag3',
            user='pingou',
            ticketfolder=None,
        )
        self.session.commit()
        self.assertEqual(msgs, ['Edited tag: tag2 to tag3'])
        self.assertEqual([tag.tag for tag in issue.tags], ['tag3'])

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.edit_issue_tags,
            session=self.session,
            project=repo,
            old_tag='tag2',
            new_tag='tag2',
            user='pingou',
            ticketfolder=None,
        )

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_search_issues(self, p_send_email, p_ugt):
        """ Test the search_issues of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_edit_issue()
        repo = pagure.lib.get_project(self.session, 'test')

        # All issues
        issues = pagure.lib.search_issues(self.session, repo)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].id, 1)
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Open')
        self.assertEqual(issues[0].tags, [])
        self.assertEqual(issues[1].id, 2)
        self.assertEqual(issues[1].project_id, 1)
        self.assertEqual(issues[1].status, 'Invalid')
        self.assertEqual(issues[1].tags, [])

        # Issues by status
        issues = pagure.lib.search_issues(
            self.session, repo, status='Invalid')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 2)
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Invalid')
        self.assertEqual(issues[0].tags, [])

        # Issues closed
        issues = pagure.lib.search_issues(
            self.session, repo, closed=True)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 2)
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Invalid')
        self.assertEqual(issues[0].tags, [])

        # Issues by tag
        issues = pagure.lib.search_issues(self.session, repo, tags='foo')
        self.assertEqual(len(issues), 0)
        issues = pagure.lib.search_issues(self.session, repo, tags='!foo')
        self.assertEqual(len(issues), 2)

        # Issue by id
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)
        self.assertEqual(issue.title, 'Test issue')
        self.assertEqual(issue.user.user, 'pingou')
        self.assertEqual(issue.tags, [])

        # Issues by authors
        issues = pagure.lib.search_issues(self.session, repo, author='foo')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 2)
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Invalid')
        self.assertEqual(issues[0].tags, [])

        # Issues by assignee
        issues = pagure.lib.search_issues(self.session, repo, assignee='foo')
        self.assertEqual(len(issues), 0)
        issues = pagure.lib.search_issues(self.session, repo, assignee='!foo')
        self.assertEqual(len(issues), 2)

        issues = pagure.lib.search_issues(self.session, repo, private='foo')
        self.assertEqual(len(issues), 2)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_add_issue_assignee(self, p_send_email, p_ugt):
        """ Test the add_issue_assignee of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=2)

        # Before
        issues = pagure.lib.search_issues(
            self.session, repo, assignee='pingou')
        self.assertEqual(len(issues), 0)

        # Test when it fails
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_issue_assignee,
            session=self.session,
            issue=issue,
            assignee='foo@foobar.com',
            user='foo@pingou.com',
            ticketfolder=None
        )

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_issue_assignee,
            session=self.session,
            issue=issue,
            assignee='foo@bar.com',
            user='foo@foopingou.com',
            ticketfolder=None
        )

        # Set the assignee by its email
        msg = pagure.lib.add_issue_assignee(
            session=self.session,
            issue=issue,
            assignee='foo@bar.com',
            user='foo@pingou.com',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Issue assigned')

        # Change the assignee to someone else by its username
        msg = pagure.lib.add_issue_assignee(
            session=self.session,
            issue=issue,
            assignee='pingou',
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Issue assigned')

        # After  -- Searches by assignee
        issues = pagure.lib.search_issues(
            self.session, repo, assignee='pingou')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 2)
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Open')
        self.assertEqual(issues[0].tags, [])

        issues = pagure.lib.search_issues(
            self.session, repo, assignee=True)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 2)
        self.assertEqual(issues[0].title, 'Test issue #2')
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Open')
        self.assertEqual(issues[0].tags, [])

        issues = pagure.lib.search_issues(
            self.session, repo, assignee=False)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, 1)
        self.assertEqual(issues[0].title, 'Test issue')
        self.assertEqual(issues[0].project_id, 1)
        self.assertEqual(issues[0].status, 'Open')
        self.assertEqual(issues[0].tags, [])

        # Reset the assignee to no-one
        msg = pagure.lib.add_issue_assignee(
            session=self.session,
            issue=issue,
            assignee=None,
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Assignee reset')

        issues = pagure.lib.search_issues(
            self.session, repo, assignee=False)
        self.assertEqual(len(issues), 2)
        self.assertEqual(issues[0].id, 1)
        self.assertEqual(issues[1].id, 2)

        issues = pagure.lib.search_issues(
            self.session, repo, assignee=True)
        self.assertEqual(len(issues), 0)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_add_issue_comment(self, p_send_email, p_ugt):
        """ Test the add_issue_comment of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()
        repo = pagure.lib.get_project(self.session, 'test')

        # Before
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)
        self.assertEqual(len(issue.comments), 0)

        # Set the assignee by its email
        msg = pagure.lib.add_issue_assignee(
            session=self.session,
            issue=issue,
            assignee='foo@bar.com',
            user='foo@pingou.com',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Issue assigned')

        # Add a comment to that issue
        msg = pagure.lib.add_issue_comment(
            session=self.session,
            issue=issue,
            comment='Hey look a comment!',
            user='foo',
            ticketfolder=None
        )
        self.session.commit()
        self.assertEqual(msg, 'Comment added')

        # After
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)
        self.assertEqual(len(issue.comments), 1)
        self.assertEqual(issue.comments[0].comment, 'Hey look a comment!')
        self.assertEqual(issue.comments[0].user.user, 'foo')

    @patch('pagure.lib.notify.send_email')
    def test_add_user_to_project(self, p_send_email):
        """ Test the add_user_to_project of pagure.lib. """
        p_send_email.return_value = True

        tests.create_projects(self.session)

        # Before
        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(len(repo.users), 0)

        # Add an user to a project
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_user_to_project,
            session=self.session,
            project=repo,
            new_user='foobar',
            user='pingou',
        )

        msg = pagure.lib.add_user_to_project(
            session=self.session,
            project=repo,
            new_user='foo',
            user='pingou',
        )
        self.session.commit()
        self.assertEqual(msg, 'User added')

        # After
        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(len(repo.users), 1)
        self.assertEqual(repo.users[0].user, 'foo')

    def test_new_project(self):
        """ Test the new_project of pagure.lib. """
        gitfolder = os.path.join(self.path, 'repos')
        docfolder = os.path.join(self.path, 'docs')
        ticketfolder = os.path.join(self.path, 'tickets')
        requestfolder = os.path.join(self.path, 'requests')

        os.mkdir(gitfolder)
        os.mkdir(docfolder)
        os.mkdir(ticketfolder)
        os.mkdir(requestfolder)

        # Try creating a blacklisted project
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            session=self.session,
            user='pingou',
            name='static',
            blacklist=['static'],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for static',
            parent_id=None,
        )

        # Create a new project
        msg = pagure.lib.new_project(
            session=self.session,
            user='pingou',
            name='testproject',
            blacklist=[],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for testproject',
            parent_id=None,
        )
        self.session.commit()
        self.assertEqual(msg, 'Project "testproject" created')

        repo = pagure.lib.get_project(self.session, 'testproject')
        self.assertEqual(repo.path, 'testproject.git')

        gitrepo = os.path.join(gitfolder, repo.path)
        docrepo = os.path.join(docfolder, repo.path)
        ticketrepo = os.path.join(ticketfolder, repo.path)
        requestrepo = os.path.join(requestfolder, repo.path)

        self.assertTrue(os.path.exists(gitrepo))
        self.assertTrue(os.path.exists(docrepo))
        self.assertTrue(os.path.exists(ticketrepo))
        self.assertTrue(os.path.exists(requestrepo))

        # Try re-creating it but all repos are existing
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            session=self.session,
            user='pingou',
            name='testproject',
            blacklist=[],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for testproject',
            parent_id=None
        )
        self.session.rollback()

        self.assertTrue(os.path.exists(gitrepo))
        self.assertTrue(os.path.exists(docrepo))
        self.assertTrue(os.path.exists(ticketrepo))
        self.assertTrue(os.path.exists(requestrepo))

        # Drop the main git repo and try again
        shutil.rmtree(gitrepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            session=self.session,
            user='pingou',
            name='testproject',
            blacklist=[],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for testproject',
            parent_id=None
        )
        self.session.rollback()

        self.assertFalse(os.path.exists(gitrepo))
        self.assertTrue(os.path.exists(docrepo))
        self.assertTrue(os.path.exists(ticketrepo))
        self.assertTrue(os.path.exists(requestrepo))

        # Drop the doc repo and try again
        shutil.rmtree(docrepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            session=self.session,
            user='pingou',
            name='testproject',
            blacklist=[],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for testproject',
            parent_id=None
        )
        self.session.rollback()
        self.assertFalse(os.path.exists(gitrepo))
        self.assertFalse(os.path.exists(docrepo))
        self.assertTrue(os.path.exists(ticketrepo))
        self.assertTrue(os.path.exists(requestrepo))

        # Drop the request repo and try again
        shutil.rmtree(ticketrepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.new_project,
            session=self.session,
            user='pingou',
            name='testproject',
            blacklist=[],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for testproject',
            parent_id=None
        )
        self.session.rollback()
        self.assertFalse(os.path.exists(gitrepo))
        self.assertFalse(os.path.exists(docrepo))
        self.assertFalse(os.path.exists(ticketrepo))
        self.assertTrue(os.path.exists(requestrepo))

    def test_update_project_settings(self):
        """ Test the update_project_settings of pagure.lib. """

        tests.create_projects(self.session)

        # Before
        repo = pagure.lib.get_project(self.session, 'test2')
        self.assertTrue(repo.settings['issue_tracker'])
        self.assertFalse(repo.settings['project_documentation'])

        msg = pagure.lib.update_project_settings(
            session=self.session,
            repo=repo,
            settings={
                'issue_tracker': True,
                'project_documentation': False,
                'pull_requests': True,
                'Only_assignee_can_merge_pull-request': False,
                'Minimum_score_to_merge_pull-request': -1,
                'Web-hooks': None,
                'Enforce_signed-off_commits_in_pull-request': False,
                'always_merge': False,
            },
            user='pingou',
        )
        self.assertEqual(msg, 'No settings to change')

        msg = pagure.lib.update_project_settings(
            session=self.session,
            repo=repo,
            settings={
                'issue_tracker': False,
                'project_documentation': True,
                'pull_requests': False,
                'Only_assignee_can_merge_pull-request': None,
                'Minimum_score_to_merge_pull-request': None,
                'Web-hooks': '',
                'Enforce_signed-off_commits_in_pull-request': False,
            },
            user='pingou',
        )
        self.assertEqual(msg, 'Edited successfully settings of repo: test2')

        # After
        repo = pagure.lib.get_project(self.session, 'test2')
        self.assertFalse(repo.settings['issue_tracker'])
        self.assertTrue(repo.settings['project_documentation'])
        self.assertFalse(repo.settings['pull_requests'])

    def test_search_projects(self):
        """ Test the search_projects of pagure.lib. """
        tests.create_projects(self.session)

        projects = pagure.lib.search_projects(self.session)
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0].id, 1)
        self.assertEqual(projects[1].id, 2)

        projects = pagure.lib.search_projects(self.session, username='foo')
        self.assertEqual(len(projects), 0)

        projects = pagure.lib.search_projects(self.session, username='pingou')
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0].id, 1)
        self.assertEqual(projects[1].id, 2)

        projects = pagure.lib.search_projects(self.session, start=1)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, 2)

        projects = pagure.lib.search_projects(self.session, limit=1)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].id, 1)

        projects = pagure.lib.search_projects(self.session, count=True)
        self.assertEqual(projects, 2)

    def test_search_project_forked(self):
        """ Test the search_project for forked projects in pagure.lib. """
        tests.create_projects(self.session)

        # Create two forked repo
        item = pagure.lib.model.Project(
            user_id=2,  # foo
            name='test',
            description='test project #1',
            parent_id=1,
            hook_token='aaabbbttt',
        )
        self.session.add(item)

        item = pagure.lib.model.Project(
            user_id=2,  # foo
            name='test2',
            description='test project #2',
            parent_id=2,
            hook_token='aaabbbuuu',
        )
        self.session.add(item)

        # Since we have two forks, let's search them
        projects = pagure.lib.search_projects(self.session, fork=True)
        self.assertEqual(len(projects), 2)
        projects = pagure.lib.search_projects(self.session, fork=False)
        self.assertEqual(len(projects), 2)

    def test_get_tags_of_project(self):
        """ Test the get_tags_of_project of pagure.lib. """

        self.test_add_tag_obj()
        repo = pagure.lib.get_project(self.session, 'test')

        tags = pagure.lib.get_tags_of_project(self.session, repo)
        self.assertEqual([tag.tag for tag in tags], ['tag1'])

        tags = pagure.lib.get_tags_of_project(
            self.session, repo, pattern='T*')
        self.assertEqual([tag.tag for tag in tags], ['tag1'])

        repo = pagure.lib.get_project(self.session, 'test2')

        tags = pagure.lib.get_tags_of_project(self.session, repo)
        self.assertEqual([tag.tag for tag in tags], [])

    def test_get_issue_statuses(self):
        """ Test the get_issue_statuses of pagure.lib. """
        statuses = pagure.lib.get_issue_statuses(self.session)
        self.assertEqual(
            sorted(statuses),
            ['Duplicate', 'Fixed', 'Insufficient data', 'Invalid', 'Open'])

    def test_set_up_user(self):
        """ Test the set_up_user of pagure.lib. """

        items = pagure.lib.search_user(self.session)
        self.assertEqual(2, len(items))
        self.assertEqual(2, items[0].id)
        self.assertEqual('foo', items[0].user)
        self.assertEqual(1, items[1].id)
        self.assertEqual('pingou', items[1].user)

        pagure.lib.set_up_user(
            session=self.session,
            username='skvidal',
            fullname='Seth',
            default_email='skvidal@fp.o',
            keydir=pagure.APP.config.get('GITOLITE_KEYDIR', None),
        )
        self.session.commit()

        items = pagure.lib.search_user(self.session)
        self.assertEqual(3, len(items))
        self.assertEqual(2, items[0].id)
        self.assertEqual('foo', items[0].user)
        self.assertEqual(1, items[1].id)
        self.assertEqual('pingou', items[1].user)
        self.assertEqual(3, items[2].id)
        self.assertEqual('skvidal', items[2].user)
        self.assertEqual('Seth', items[2].fullname)
        self.assertEqual(
            ['skvidal@fp.o'], [email.email for email in items[2].emails])

        # Add the user a second time
        pagure.lib.set_up_user(
            session=self.session,
            username='skvidal',
            fullname='Seth V',
            default_email='skvidal@fp.o',
            keydir=pagure.APP.config.get('GITOLITE_KEYDIR', None),
        )
        self.session.commit()
        # Nothing changed
        items = pagure.lib.search_user(self.session)
        self.assertEqual(3, len(items))
        self.assertEqual('skvidal', items[2].user)
        self.assertEqual('Seth V', items[2].fullname)
        self.assertEqual(
            ['skvidal@fp.o'], [email.email for email in items[2].emails])

        # Add the user a third time with a different email
        pagure.lib.set_up_user(
            session=self.session,
            username='skvidal',
            fullname='Seth',
            default_email='svidal@fp.o',
            keydir=pagure.APP.config.get('GITOLITE_KEYDIR', None),
        )
        self.session.commit()
        # Email added
        items = pagure.lib.search_user(self.session)
        self.assertEqual(3, len(items))
        self.assertEqual('skvidal', items[2].user)
        self.assertEqual(
            ['skvidal@fp.o', 'svidal@fp.o'],
            [email.email for email in items[2].emails])

    def test_update_user_ssh(self):
        """ Test the update_user_ssh of pagure.lib. """

        # Before
        user = pagure.lib.search_user(self.session, username='foo')
        self.assertEqual(user.public_ssh_key, None)

        msg = pagure.lib.update_user_ssh(self.session, user, 'blah', keydir=None)
        user = pagure.lib.search_user(self.session, username='foo')
        self.assertEqual(user.public_ssh_key, 'blah')

        msg = pagure.lib.update_user_ssh(self.session, user, 'blah', keydir=None)
        user = pagure.lib.search_user(self.session, username='foo')
        self.assertEqual(user.public_ssh_key, 'blah')

        msg = pagure.lib.update_user_ssh(self.session, 'foo', None, keydir=None)
        user = pagure.lib.search_user(self.session, username='foo')
        self.assertEqual(user.public_ssh_key, None)

    def test_avatar_url_from_openid(self):
        """ Test the avatar_url_from_openid of pagure.lib. """
        output = pagure.lib.avatar_url_from_openid('pingou@fedoraproject.org')
        self.assertEqual(
            output,
            'https://seccdn.libravatar.org/avatar/'
            'b3ee7bb4de70b6522c2478df3b4cd6322b5ec5d62ac7ceb1128e3d4ff42f6928'
            '?s=64&d=retro')

    def test_fork_project(self):
        """ Test the fork_project of pagure.lib. """
        gitfolder = os.path.join(self.path, 'repos')
        docfolder = os.path.join(self.path, 'docs')
        ticketfolder = os.path.join(self.path, 'tickets')
        requestfolder = os.path.join(self.path, 'requests')

        os.mkdir(gitfolder)
        os.mkdir(docfolder)
        os.mkdir(ticketfolder)

        projects = pagure.lib.search_projects(self.session)
        self.assertEqual(len(projects), 0)

        # Create a new project
        msg = pagure.lib.new_project(
            session=self.session,
            user='pingou',
            name='testproject',
            blacklist=[],
            allowed_prefix=[],
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
            description='description for testproject',
            parent_id=None,
        )
        self.session.commit()
        self.assertEqual(msg, 'Project "testproject" created')

        projects = pagure.lib.search_projects(self.session)
        self.assertEqual(len(projects), 1)

        repo = pagure.lib.get_project(self.session, 'testproject')
        gitrepo = os.path.join(gitfolder, repo.path)
        docrepo = os.path.join(docfolder, repo.path)
        ticketrepo = os.path.join(ticketfolder, repo.path)
        requestrepo = os.path.join(requestfolder, repo.path)

        self.assertTrue(os.path.exists(gitrepo))
        self.assertTrue(os.path.exists(docrepo))
        self.assertTrue(os.path.exists(ticketrepo))
        self.assertTrue(os.path.exists(requestrepo))

        # Git repo exists
        grepo = '%s.git' % os.path.join(
            gitfolder, 'forks', 'foo', 'testproject')
        os.makedirs(grepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.fork_project,
            session=self.session,
            user='foo',
            repo=repo,
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
        )
        self.session.rollback()
        shutil.rmtree(grepo)

        # Doc repo exists
        grepo = '%s.git' % os.path.join(
            docfolder, 'forks', 'foo', 'testproject')
        os.makedirs(grepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.fork_project,
            session=self.session,
            user='foo',
            repo=repo,
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
        )
        self.session.rollback()
        shutil.rmtree(grepo)

        # Ticket repo exists
        grepo = '%s.git' % os.path.join(
            ticketfolder, 'forks', 'foo', 'testproject')
        os.makedirs(grepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.fork_project,
            session=self.session,
            user='foo',
            repo=repo,
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
        )
        self.session.rollback()
        shutil.rmtree(grepo)

        # Request repo exists
        grepo = '%s.git' % os.path.join(
            requestfolder, 'forks', 'foo', 'testproject')
        os.makedirs(grepo)
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.fork_project,
            session=self.session,
            user='foo',
            repo=repo,
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
        )
        self.session.rollback()
        shutil.rmtree(grepo)

        projects = pagure.lib.search_projects(self.session)
        self.assertEqual(len(projects), 1)

        # Fork worked

        msg = pagure.lib.fork_project(
            session=self.session,
            user='foo',
            repo=repo,
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
        )
        self.session.commit()
        self.assertEqual(
            msg, 'Repo "testproject" cloned to "foo/testproject"')

        projects = pagure.lib.search_projects(self.session)
        self.assertEqual(len(projects), 2)

        # Fork a fork

        repo = pagure.lib.get_project(
            self.session, 'testproject', user='foo')

        msg = pagure.lib.fork_project(
            session=self.session,
            user='pingou',
            repo=repo,
            gitfolder=gitfolder,
            docfolder=docfolder,
            ticketfolder=ticketfolder,
            requestfolder=requestfolder,
        )
        self.session.commit()
        self.assertEqual(
            msg, 'Repo "testproject" cloned to "pingou/testproject"')

        projects = pagure.lib.search_projects(self.session)
        self.assertEqual(len(projects), 3)

    @patch('pagure.lib.notify.send_email')
    def test_new_pull_request(self, mockemail):
        """ test new_pull_request of pagure.lib. """
        mockemail.return_value = True

        tests.create_projects(self.session)

        # Create a forked repo
        item = pagure.lib.model.Project(
            user_id=1,  # pingou
            name='test',
            description='test project #1',
            parent_id=1,
            hook_token='aaabbbrrr',
        )
        self.session.commit()
        self.session.add(item)

        # Add an extra user to project `foo`
        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(repo.open_requests, 0)

        msg = pagure.lib.add_user_to_project(
            session=self.session,
            project=repo,
            new_user='foo',
            user='pingou',
        )
        self.session.commit()
        self.assertEqual(msg, 'User added')

        repo = pagure.lib.get_project(self.session, 'test')
        forked_repo = pagure.lib.get_project(
            self.session, 'test', user='pingou')

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
        self.session.commit()
        self.assertEqual(req.id, 1)
        self.assertEqual(req.title, 'test pull-request')
        self.assertEqual(repo.open_requests, 1)

    @patch('pagure.lib.notify.send_email')
    def test_add_pull_request_comment(self, mockemail):
        """ Test add_pull_request_comment of pagure.lib. """
        mockemail.return_value = True

        self.test_new_pull_request()

        request = pagure.lib.search_pull_requests(self.session, requestid=1)

        msg = pagure.lib.add_pull_request_comment(
            session=self.session,
            request=request,
            commit='commithash',
            tree_id=None,
            filename='file',
            row=None,
            comment='This is awesome, I got to remember it!',
            user='foo',
            requestfolder=None,
        )
        self.assertEqual(msg, 'Comment added')
        self.session.commit()

        self.assertEqual(len(request.discussion), 0)
        self.assertEqual(len(request.comments), 1)
        self.assertEqual(request.score, 0)

    @patch('pagure.lib.notify.send_email')
    def test_add_pull_request_flag(self, mockemail):
        """ Test add_pull_request_flag of pagure.lib. """
        mockemail.return_value = True

        self.test_new_pull_request()

        request = pagure.lib.search_pull_requests(self.session, requestid=1)
        self.assertEqual(len(request.flags), 0)

        msg = pagure.lib.add_pull_request_flag(
            session=self.session,
            request=request,
            username="jenkins",
            percent=100,
            comment="Build passes",
            url="http://jenkins.cloud.fedoraproject.org",
            uid="jenkins_build_pagure_34",
            user='foo',
            requestfolder=None,
        )
        self.assertEqual(msg, 'Flag added')
        self.session.commit()

        self.assertEqual(len(request.flags), 1)

    def test_search_pull_requests(self):
        """ Test search_pull_requests of pagure.lib. """

        self.test_new_pull_request()

        prs = pagure.lib.search_pull_requests(
            session=self.session
        )
        self.assertEqual(len(prs), 1)

        prs = pagure.lib.search_pull_requests(
            session=self.session,
            project_id=1
        )
        self.assertEqual(len(prs), 1)

        prs = pagure.lib.search_pull_requests(
            session=self.session,
            project_id_from=3
        )
        self.assertEqual(len(prs), 1)

        prs = pagure.lib.search_pull_requests(
            session=self.session,
            status=False
        )
        self.assertEqual(len(prs), 0)

        # All non-assigned PR
        prs = pagure.lib.search_pull_requests(
            session=self.session,
            assignee=False
        )
        self.assertEqual(len(prs), 1)

        prs[0].assignee_id = 1
        self.session.add(prs[0])
        self.session.commit()

        # All the PR assigned
        prs = pagure.lib.search_pull_requests(
            session=self.session,
            assignee=True
        )
        self.assertEqual(len(prs), 1)

        # Basically the same as above but then for a specific user
        prs = pagure.lib.search_pull_requests(
            session=self.session,
            assignee='pingou'
        )
        self.assertEqual(len(prs), 1)

        # All PR except those assigned to pingou
        prs = pagure.lib.search_pull_requests(
            session=self.session,
            assignee='!pingou'
        )
        self.assertEqual(len(prs), 0)

        # All PR created by the specified author
        prs = pagure.lib.search_pull_requests(
            session=self.session,
            author='pingou'
        )
        self.assertEqual(len(prs), 1)

        # Count the PR instead of listing them
        prs = pagure.lib.search_pull_requests(
            session=self.session,
            author='pingou',
            count=True
        )
        self.assertEqual(prs, 1)

    @patch('pagure.lib.notify.send_email')
    def test_close_pull_request(self, send_email):
        """ Test close_pull_request of pagure.lib. """
        send_email.return_value = True

        self.test_new_pull_request()

        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(repo.open_requests, 1)
        request = pagure.lib.search_pull_requests(self.session, requestid=1)

        pagure.lib.close_pull_request(
            session=self.session,
            request=request,
            user='pingou',
            requestfolder=None,
            merged=True,
        )
        self.session.commit()
        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(repo.open_requests, 0)

        prs = pagure.lib.search_pull_requests(
            session=self.session,
            status=False
        )
        self.assertEqual(len(prs), 1)

        # Does not change much, just the notification sent

        pagure.lib.close_pull_request(
            session=self.session,
            request=request,
            user='pingou',
            requestfolder=None,
            merged=False,
        )
        self.session.commit()

        prs = pagure.lib.search_pull_requests(
            session=self.session,
            status=False
        )
        self.assertEqual(len(prs), 1)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_remove_issue_dependency(self, p_send_email, p_ugt):
        """ Test remove_issue_dependency of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_add_issue_dependency()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)
        issue_blocked = pagure.lib.search_issues(
            self.session, repo, issueid=2)

        # Before
        self.assertEqual(len(issue.parents), 1)
        self.assertEqual(issue.parents[0].id, 2)
        self.assertEqual(len(issue.children), 0)
        self.assertEqual(issue.children, [])

        self.assertEqual(len(issue_blocked.parents), 0)
        self.assertEqual(issue_blocked.parents, [])
        self.assertEqual(len(issue_blocked.children), 1)
        self.assertEqual(issue_blocked.children[0].id, 1)

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.remove_issue_dependency,
            session=self.session,
            issue=issue,
            issue_blocked=issue,
            user='pingou',
            ticketfolder=None)

        # Wrong order of issues
        msg = pagure.lib.remove_issue_dependency(
            session=self.session,
            issue=issue,
            issue_blocked=issue_blocked,
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, None)

        # Drop deps
        msg = pagure.lib.remove_issue_dependency(
            session=self.session,
            issue=issue_blocked,
            issue_blocked=issue,
            user='pingou',
            ticketfolder=None)
        self.session.commit()
        self.assertEqual(msg, 'Dependency removed')

        # After
        self.assertEqual(issue.parents, [])
        self.assertEqual(issue.children, [])
        self.assertEqual(issue_blocked.parents, [])
        self.assertEqual(issue_blocked.children, [])

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_get_issue_comment(self, p_send_email, p_ugt):
        """ Test the get_issue_comment of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_add_issue_comment()

        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        self.assertEqual(
            pagure.lib.get_issue_comment(self.session, issue.uid, 10),
            None
        )

        comment = pagure.lib.get_issue_comment(self.session, issue.uid, 1)
        self.assertEqual(comment.comment, 'Hey look a comment!')

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_get_issue_by_uid(self, p_send_email, p_ugt):
        """ Test the get_issue_by_uid of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()

        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        self.assertEqual(
            pagure.lib.get_issue_by_uid(self.session, 'foobar'),
            None
        )

        new_issue = pagure.lib.get_issue_by_uid(self.session, issue.uid)
        self.assertEqual(issue, new_issue)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_update_tags(self, p_send_email, p_ugt):
        """ Test the update_tags of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        # before
        self.assertEqual(issue.tags_text, [])

        messages = pagure.lib.update_tags(
            self.session, issue, 'tag', 'pingou', ticketfolder=None)
        self.assertEqual(messages, ['Tag added: tag'])
        messages = pagure.lib.update_tags(
            self.session, issue, ['tag2', 'tag3'], 'pingou',
            ticketfolder=None)
        self.assertEqual(
            messages, ['Tag added: tag2, tag3', 'Removed tag: tag'])

        # after
        self.assertEqual(issue.tags_text, ['tag2', 'tag3'])

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_update_dependency_issue(self, p_send_email, p_ugt):
        """ Test the update_dependency_issue of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        self.assertEqual(repo.open_tickets, 2)
        self.assertEqual(repo.open_tickets_public, 2)

        # Create issues to play with
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue #3',
            content='We should work on this (3rd time!)',
            user='pingou',
            ticketfolder=None,
            private=True,
        )
        self.session.commit()
        self.assertEqual(msg.title, 'Test issue #3')

        self.assertEqual(repo.open_tickets, 3)
        self.assertEqual(repo.open_tickets_public, 2)

        # before
        self.assertEqual(issue.tags_text, [])
        self.assertEqual(issue.depends_text, [])
        self.assertEqual(issue.blocks_text, [])

        messages = pagure.lib.update_dependency_issue(
            self.session, repo, issue, '2', 'pingou', ticketfolder=None)
        self.assertEqual(messages, ['Dependency added'])
        messages = pagure.lib.update_dependency_issue(
            self.session, repo, issue, ['3', '4', 5], 'pingou',
            ticketfolder=None)
        self.assertEqual(
            messages, ['Dependency added', 'Dependency removed'])

        # after
        self.assertEqual(issue.tags_text, [])
        self.assertEqual(issue.depends_text, [3])
        self.assertEqual(issue.blocks_text, [])

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_update_blocked_issue(self, p_send_email, p_ugt):
        """ Test the update_blocked_issue of pagure.lib. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        self.test_new_issue()
        repo = pagure.lib.get_project(self.session, 'test')
        issue = pagure.lib.search_issues(self.session, repo, issueid=1)

        # Create issues to play with
        msg = pagure.lib.new_issue(
            session=self.session,
            repo=repo,
            title='Test issue #3',
            content='We should work on this (3rd time!)',
            user='pingou',
            ticketfolder=None,
            private=True,
        )
        self.session.commit()
        self.assertEqual(msg.title, 'Test issue #3')

        # before
        self.assertEqual(issue.tags_text, [])
        self.assertEqual(issue.depends_text, [])
        self.assertEqual(issue.blocks_text, [])

        messages = pagure.lib.update_blocked_issue(
            self.session, repo, issue, '2', 'pingou', ticketfolder=None)
        self.assertEqual(messages, ['Dependency added'])
        messages = pagure.lib.update_blocked_issue(
            self.session, repo, issue, ['3', '4', 5], 'pingou',
            ticketfolder=None)
        self.assertEqual(
            messages, ['Dependency added', 'Dependency removed'])

        # after
        self.assertEqual(issue.tags_text, [])
        self.assertEqual(issue.depends_text, [])
        self.assertEqual(issue.blocks_text, [3])

    @patch('pagure.lib.notify.send_email')
    def test_add_pull_request_assignee(self, mockemail):
        """ Test add_pull_request_assignee of pagure.lib. """
        mockemail.return_value = True

        self.test_new_pull_request()

        request = pagure.lib.search_pull_requests(self.session, requestid=1)

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_pull_request_assignee,
            session=self.session,
            request=request,
            assignee='bar',
            user='foo',
            requestfolder=None,
        )

        # Assign
        msg = pagure.lib.add_pull_request_assignee(
            session=self.session,
            request=request,
            assignee='pingou',
            user='foo',
            requestfolder=None,
        )
        self.assertEqual(msg, 'Request assigned')

        # Reset
        msg = pagure.lib.add_pull_request_assignee(
            session=self.session,
            request=request,
            assignee=None,
            user='foo',
            requestfolder=None,
        )
        self.assertEqual(msg, 'Request reset')

        # Try resetting again
        msg = pagure.lib.add_pull_request_assignee(
            session=self.session,
            request=request,
            assignee=None,
            user='foo',
            requestfolder=None,
        )
        self.assertEqual(msg, None)

    def test_search_pending_email(self):
        """ Test search_pending_email of pagure.lib. """

        self.assertEqual(
            pagure.lib.search_pending_email(self.session), None)

        user = pagure.lib.search_user(self.session, username='pingou')

        email_pend = pagure.lib.model.UserEmailPending(
            user_id=user.id,
            email='foo@fp.o',
            token='abcdef',
        )
        self.session.add(email_pend)
        self.session.commit()

        self.assertNotEqual(
            pagure.lib.search_pending_email(self.session), None)
        self.assertNotEqual(
            pagure.lib.search_pending_email(self.session, token='abcdef'),
            None)

        pend = pagure.lib.search_pending_email(self.session, token='abcdef')
        self.assertEqual(pend.user.username, 'pingou')
        self.assertEqual(pend.email, 'foo@fp.o')
        self.assertEqual(pend.token, 'abcdef')

        pend = pagure.lib.search_pending_email(self.session, email='foo@fp.o')
        self.assertEqual(pend.user.username, 'pingou')
        self.assertEqual(pend.email, 'foo@fp.o')
        self.assertEqual(pend.token, 'abcdef')

    def test_generate_hook_token(self):
        """ Test generate_hook_token of pagure.lib. """

        tests.create_projects(self.session)

        projects = pagure.lib.search_projects(self.session)
        for proj in projects:
            self.assertIn(proj.hook_token, ['aaabbbccc', 'aaabbbddd'])

        pagure.lib.generate_hook_token(self.session)

        projects = pagure.lib.search_projects(self.session)
        for proj in projects:
            self.assertNotIn(proj.hook_token, ['aaabbbccc', 'aaabbbddd'])

    @patch('pagure.lib.notify.send_email')
    def test_pull_request_score(self, mockemail):
        """ Test PullRequest.score of pagure.lib.model. """
        mockemail.return_value = True

        self.test_new_pull_request()

        request = pagure.lib.search_pull_requests(self.session, requestid=1)

        msg = pagure.lib.add_pull_request_comment(
            session=self.session,
            request=request,
            commit=None,
            tree_id=None,
            filename=None,
            row=None,
            comment='This looks great :thumbsup:',
            user='foo',
            requestfolder=None,
        )
        self.session.commit()
        self.assertEqual(msg, 'Comment added')

        msg = pagure.lib.add_pull_request_comment(
            session=self.session,
            request=request,
            commit=None,
            tree_id=None,
            filename=None,
            row=None,
            comment='I disagree -1',
            user='pingou',
            requestfolder=None,
        )
        self.session.commit()
        self.assertEqual(msg, 'Comment added')

        msg = pagure.lib.add_pull_request_comment(
            session=self.session,
            request=request,
            commit=None,
            tree_id=None,
            filename=None,
            row=None,
            comment='NM this looks great now +1000',
            user='pingou',
            requestfolder=None,
        )
        self.session.commit()
        self.assertEqual(msg, 'Comment added')

        self.assertEqual(len(request.discussion), 3)
        self.assertEqual(request.score, 1)

    def test_add_group(self):
        """ Test the add_group method of pagure.lib. """
        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 0)
        self.assertEqual(groups, [])

        # Invalid type
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group,
            self.session,
            group_name='foo',
            group_type='bar',
            user='pingou',
            is_admin=True,
            blacklist=[],
        )
        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 0)
        self.assertEqual(groups, [])

        # Invalid user
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group,
            self.session,
            group_name='foo',
            group_type='user',
            user='test',
            is_admin=False,
            blacklist=[],
        )
        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 0)
        self.assertEqual(groups, [])

        msg = pagure.lib.add_group(
            self.session,
            group_name='foo',
            group_type='bar',
            user='pingou',
            is_admin=False,
            blacklist=[],
        )
        self.session.commit()
        self.assertEqual(msg, 'User `pingou` added to the group `foo`.')

        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_name, 'foo')

        # Group with this name already exists
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group,
            self.session,
            group_name='foo',
            group_type='bar',
            user='pingou',
            is_admin=False,
            blacklist=[],
        )

        # Group with a blacklisted prefix
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group,
            self.session,
            group_name='forks',
            group_type='bar',
            user='pingou',
            is_admin=False,
            blacklist=['forks'],
        )

    def test_add_user_to_group(self):
        """ Test the add_user_to_group method of pagure.lib. """
        self.test_add_group()
        group = pagure.lib.search_groups(self.session, group_name='foo')
        self.assertNotEqual(group, None)
        self.assertEqual(group.group_name, 'foo')

        # Invalid new user
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_user_to_group,
            self.session,
            username='foobar',
            group=group,
            user='foo',
            is_admin=False,
        )

        # Invalid user
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_user_to_group,
            self.session,
            username='foo',
            group=group,
            user='foobar',
            is_admin=False,
        )

        # User not allowed
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_user_to_group,
            self.session,
            username='foo',
            group=group,
            user='foo',
            is_admin=False,
        )

        msg = pagure.lib.add_user_to_group(
            self.session,
            username='foo',
            group=group,
            user='pingou',
            is_admin=False,
        )
        self.session.commit()
        self.assertEqual(msg, 'User `foo` added to the group `foo`.')

        msg = pagure.lib.add_user_to_group(
            self.session,
            username='foo',
            group=group,
            user='pingou',
            is_admin=False,
        )
        self.session.commit()
        self.assertEqual(
            msg, 'User `foo` already in the group, nothing to change.')

    def test_is_group_member(self):
        """ Test the is_group_member method of pagure.lib. """
        self.test_add_group()

        self.assertFalse(
            pagure.lib.is_group_member(self.session, None, 'foo'))

        self.assertFalse(
            pagure.lib.is_group_member(self.session, 'bar', 'foo'))

        self.assertFalse(
            pagure.lib.is_group_member(self.session, 'foo', 'foo'))

        self.assertTrue(
            pagure.lib.is_group_member(self.session, 'pingou', 'foo'))

    def test_get_user_group(self):
        """ Test the get_user_group method of pagure.lib. """

        self.test_add_group()

        item = pagure.lib.get_user_group(self.session, 1, 1)
        self.assertEqual(item.user_id, 1)
        self.assertEqual(item.group_id, 1)

        item = pagure.lib.get_user_group(self.session, 1, 2)
        self.assertEqual(item, None)

        item = pagure.lib.get_user_group(self.session, 2, 1)
        self.assertEqual(item, None)

    def test_get_group_types(self):
        """ Test the get_group_types method of pagure.lib. """

        self.test_add_group()

        groups = pagure.lib.get_group_types(self.session, 'user')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_type, 'user')

        groups = pagure.lib.get_group_types(self.session)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].group_type, 'admin')
        self.assertEqual(groups[1].group_type, 'user')

    def test_search_groups(self):
        """ Test the search_groups method of pagure.lib. """

        self.assertEqual(pagure.lib.search_groups(self.session), [])

        msg = pagure.lib.add_group(
            self.session,
            group_name='foo',
            group_type='bar',
            user='pingou',
            is_admin=False,
            blacklist=[],
        )
        self.session.commit()
        self.assertEqual(msg, 'User `pingou` added to the group `foo`.')

        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_name, 'foo')

        msg = pagure.lib.add_group(
            self.session,
            group_name='bar',
            group_type='admin',
            user='pingou',
            is_admin=True,
            blacklist=[],
        )
        self.session.commit()
        self.assertEqual(msg, 'User `pingou` added to the group `bar`.')

        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].group_name, 'bar')
        self.assertEqual(groups[1].group_name, 'foo')

        groups = pagure.lib.search_groups(self.session, group_type='user')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_name, 'foo')

        groups = pagure.lib.search_groups(self.session, group_type='admin')
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_name, 'bar')

        groups = pagure.lib.search_groups(self.session, group_name='foo')
        self.assertEqual(groups.group_name, 'foo')

    def test_delete_user_of_group(self):
        """ Test the delete_user_of_group method of pagure.lib. """
        self.test_add_user_to_group()

        groups = pagure.lib.search_groups(self.session)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].group_name, 'foo')

        # Invalid username
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.delete_user_of_group,
            self.session,
            username='bar',
            groupname='foo',
            user='pingou',
            is_admin=False,
        )

        # Invalid groupname
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.delete_user_of_group,
            self.session,
            username='foo',
            groupname='bar',
            user='pingou',
            is_admin=False,
        )

        # Invalid user
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.delete_user_of_group,
            self.session,
            username='foo',
            groupname='foo',
            user='test',
            is_admin=False,
        )

        # User not in the group
        item = pagure.lib.model.User(
            user='bar',
            fullname='bar',
            password='foo',
            default_email='bar@bar.com',
        )
        self.session.add(item)
        item = pagure.lib.model.UserEmail(
            user_id=3,
            email='bar@bar.com')
        self.session.add(item)
        self.session.commit()

        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.delete_user_of_group,
            self.session,
            username='bar',
            groupname='foo',
            user='pingou',
            is_admin=False,
        )

        # User is not allowed to remove the username
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.delete_user_of_group,
            self.session,
            username='foo',
            groupname='foo',
            user='bar',
            is_admin=False,
        )

        # Username is the creator of the group
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.delete_user_of_group,
            self.session,
            username='pingou',
            groupname='foo',
            user='pingou',
            is_admin=False,
        )

        # All good
        group = pagure.lib.search_groups(self.session, group_name='foo')
        self.assertEqual(len(group.users), 2)

        pagure.lib.delete_user_of_group(
            self.session,
            username='foo',
            groupname='foo',
            user='pingou',
            is_admin=False,
        )
        self.session.commit()

        group = pagure.lib.search_groups(self.session, group_name='foo')
        self.assertEqual(len(group.users), 1)

    def test_add_group_to_project(self):
        """ Test the add_group_to_project method of pagure.lib. """
        tests.create_projects(self.session)
        self.test_add_group()

        project = pagure.lib.get_project(self.session, 'test2')

        # Group does not exist
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group_to_project,
            session=self.session,
            project=project,
            new_group='bar',
            user='foo',
        )

        # User does not exist
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group_to_project,
            session=self.session,
            project=project,
            new_group='foo',
            user='bar',
        )

        # User not allowed
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group_to_project,
            session=self.session,
            project=project,
            new_group='foo',
            user='foo',
        )

        # All good
        msg = pagure.lib.add_group_to_project(
            session=self.session,
            project=project,
            new_group='foo',
            user='pingou',
        )
        self.session.commit()
        self.assertEqual(msg, 'Group added')

        # Group already associated with the project
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.add_group_to_project,
            session=self.session,
            project=project,
            new_group='foo',
            user='pingou',
        )

    def test_update_watch_status(self):
        """ Test the update_watch_status method of pagure.lib. """
        tests.create_projects(self.session)

        project = pagure.lib.get_project(self.session, 'test')

        # User does not exist
        self.assertRaises(
            pagure.exceptions.PagureException,
            pagure.lib.update_watch_status,
            session=self.session,
            project=project,
            user='aavrug',
            watch='1',
        )

        # All good and when user seleted watch option.
        msg = pagure.lib.update_watch_status(
            session=self.session,
            project=project,
            user='pingou',
            watch='1',
        )
        self.session.commit()
        self.assertEqual(msg, 'You are now watching this repo.')

        # All good and when user selected unwatch option.
        msg = pagure.lib.update_watch_status(
            session=self.session,
            project=project,
            user='pingou',
            watch='0',
        )
        self.session.commit()
        self.assertEqual(msg, 'You are no longer watching this repo.')

    def test_is_watching(self):
        """ Test the is_watching method of pagure.lib. """
        tests.create_projects(self.session)
        self.test_add_group()

        project = pagure.lib.get_project(self.session, 'test')

        # If user not logged in
        watch = pagure.lib.is_watching(
            session=self.session,
            user=None,
            reponame='test',
        )
        self.assertFalse(watch)

        # User does not exist
        user = tests.FakeUser()
        user.username = 'aavrug'
        watch = pagure.lib.is_watching(
            session=self.session,
            user=user,
            reponame='test',
        )
        self.assertFalse(watch)

        pagure.lib.add_group_to_project(
            session=self.session,
            project=project,
            new_group='foo',
            user='pingou',
        )
        self.session.commit()

        group = pagure.lib.search_groups(self.session, group_name='foo')
        pagure.lib.add_user_to_group(
            self.session,
            username='foo',
            group=group,
            user='pingou',
            is_admin=False,
        )
        self.session.commit()
        group = pagure.lib.search_groups(self.session, group_name='foo')

        # If user belongs to any group of that project
        user.username = 'foo'
        watch = pagure.lib.is_watching(
            session=self.session,
            user=user,
            reponame='test',
        )
        self.assertTrue(watch)

        # If user is the creator
        user.username = 'pingou'
        watch = pagure.lib.is_watching(
            session=self.session,
            user=user,
            reponame='test',
        )
        self.assertTrue(watch)

        # Entry into watchers table
        pagure.lib.update_watch_status(
            session=self.session,
            project=project,
            user='pingou',
            watch='1',
        )
        self.session.commit()

        # From watchers table
        watch = pagure.lib.is_watching(
            session=self.session,
            user=user,
            reponame='test',
        )
        self.assertTrue(watch)

        # Entry into watchers table
        pagure.lib.update_watch_status(
            session=self.session,
            project=project,
            user='pingou',
            watch='0',
        )
        self.session.commit()

        # From watchers table
        watch = pagure.lib.is_watching(
            session=self.session,
            user=user,
            reponame='test',
        )
        self.assertFalse(watch)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(PagureLibtests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
