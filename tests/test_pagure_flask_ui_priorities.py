# -*- coding: utf-8 -*-

"""
 (c) 2016 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import datetime
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


class PagureFlaskPrioritiestests(tests.Modeltests):
    """ Tests for the behavior of priorities in pagure """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskPrioritiestests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.SESSION = self.session
        pagure.ui.SESSION = self.session
        pagure.ui.app.SESSION = self.session
        pagure.ui.filters.SESSION = self.session
        pagure.ui.repo.SESSION = self.session
        pagure.ui.issues.SESSION = self.session

        pagure.APP.config['GIT_FOLDER'] = tests.HERE
        pagure.APP.config['REQUESTS_FOLDER'] = os.path.join(
            tests.HERE, 'requests')
        pagure.APP.config['TICKETS_FOLDER'] = os.path.join(
            tests.HERE, 'tickets')
        pagure.APP.config['DOCS_FOLDER'] = os.path.join(
            tests.HERE, 'docs')
        self.app = pagure.APP.test_client()

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_ticket_with_no_priority(self, p_send_email, p_ugt):
        """ Test creating a ticket without priority. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(tests.HERE), bare=True)

        user = tests.FakeUser()
        user.username = 'pingou'
        with tests.user_set(pagure.APP, user):

            # Get the CSRF token
            output = self.app.get('/test/new_issue')
            self.assertEqual(output.status_code, 200)
            self.assertTrue(
                '<div class="card-header">\n        New issue'
                in output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            data = {
                'title': 'Test issue',
                'issue_content': 'We really should improve on this issue',
                'status': 'Open',
                'csrf_token': csrf_token,
            }

            # Create the issue
            output = self.app.post(
                '/test/new_issue', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Issue #1: Test issue - test - Pagure</title>',
                output.data)
            self.assertIn(
                '<a class="btn btn-primary btn-sm" '
                'href="/test/issue/1/edit" title="Edit this issue">',
                output.data)
            self.assertNotIn('<div id="priority_plain">', output.data)
            self.assertNotIn('<option value="1">High</option>', output.data)

    @patch('pagure.lib.git.update_git')
    @patch('pagure.lib.notify.send_email')
    def test_ticket_with_priorities(self, p_send_email, p_ugt):
        """ Test creating a ticket with priorities. """
        p_send_email.return_value = True
        p_ugt.return_value = True

        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(tests.HERE), bare=True)

        # Set some priorities
        repo = pagure.lib.get_project(self.session, 'test')
        repo.priorities = {'1': 'High', '2': 'Normal'}
        self.session.add(repo)
        self.session.commit()

        user = tests.FakeUser()
        user.username = 'pingou'
        with tests.user_set(pagure.APP, user):

            # Get the CSRF token
            output = self.app.get('/test/new_issue')
            self.assertEqual(output.status_code, 200)
            self.assertTrue(
                '<div class="card-header">\n        New issue'
                in output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            data = {
                'title': 'Test issue',
                'issue_content': 'We really should improve on this issue',
                'status': 'Open',
                'csrf_token': csrf_token,
            }

            # Create the issue
            output = self.app.post(
                '/test/new_issue', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Issue #1: Test issue - test - Pagure</title>',
                output.data)
            self.assertIn(
                '<a class="btn btn-primary btn-sm" '
                'href="/test/issue/1/edit" title="Edit this issue">',
                output.data)
            self.assertIn('<div id="priority_plain">', output.data)
            self.assertIn('<option value="1">High</option>', output.data)

    def test_update_priorities(self):
        """ Test updating priorities of a repo. """
        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(tests.HERE), bare=True)

        # Set some priorities
        repo = pagure.lib.get_project(self.session, 'test')
        self.assertEqual(repo.priorities, {})

        user = tests.FakeUser()
        user.username = 'pingou'
        with tests.user_set(pagure.APP, user):

            # Get the CSRF token
            output = self.app.get('/test/settings')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            data = {
                'priority_weigth': 1,
                'priority_title': 'High',
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            # Check the result of the action -- None, no CSRF
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(repo.priorities, {})

            data = {
                'priority_weigth': 1,
                'priority_title': 'High',
                'csrf_token': csrf_token,
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            # Check the result of the action -- Priority recorded
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(repo.priorities, {u'': u'', u'1': u'High'})

            data = {
                'priority_weigth': [1, 2, 3],
                'priority_title': ['High', 'Normal', 'Low'],
                'csrf_token': csrf_token,
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            # Check the result of the action -- Priority recorded
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(
                repo.priorities,
                {u'': u'', u'1': u'High', u'2': u'Normal', u'3': u'Low'}
            )

            # Check error - less weigths than titles
            data = {
                'priority_weigth': [1, 2],
                'priority_title': ['High', 'Normal', 'Low'],
                'csrf_token': csrf_token,
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            self.assertIn(
                '</button>\n'
                '                      Priorities weights and titles are '
                'not of the same length', output.data)            # Check the result of the action -- Priorities un-changed
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(
                repo.priorities,
                {u'': u'', u'1': u'High', u'2': u'Normal', u'3': u'Low'}
            )

            # Check error - weigths must be integer
            data = {
                'priority_weigth': [1, 2, 'c'],
                'priority_title': ['High', 'Normal', 'Low'],
                'csrf_token': csrf_token,
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            self.assertIn(
                '</button>\n'
                '                      Priorities weights must be numbers',
                output.data)
            # Check the result of the action -- Priorities un-changed
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(
                repo.priorities,
                {u'': u'', u'1': u'High', u'2': u'Normal', u'3': u'Low'}
            )

            # Check error - Twice the same priority weigth
            data = {
                'priority_weigth': [1, 2, 2],
                'priority_title': ['High', 'Normal', 'Low'],
                'csrf_token': csrf_token,
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            self.assertIn(
                '</button>\n'
                '                      Priority weight 2 is present 2 times',
                output.data)
            # Check the result of the action -- Priorities un-changed
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(
                repo.priorities,
                {u'': u'', u'1': u'High', u'2': u'Normal', u'3': u'Low'}
            )

            # Check error - Twice the same priority title
            data = {
                'priority_weigth': [1, 2, 3],
                'priority_title': ['High', 'Normal', 'Normal'],
                'csrf_token': csrf_token,
            }
            output = self.app.post(
                '/test/update/priorities', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            # Check the redirect
            self.assertIn(
                '<title>Settings - test - Pagure</title>', output.data)
            self.assertIn('<h3>Settings for test</h3>', output.data)
            self.assertIn(
                '</button>\n'
                '                      Priority Normal is present 2 times',
                output.data)
            # Check the result of the action -- Priorities un-changed
            repo = pagure.lib.get_project(self.session, 'test')
            self.assertEqual(
                repo.priorities,
                {u'': u'', u'1': u'High', u'2': u'Normal', u'3': u'Low'}
            )

            # Check the behavior if the project disabled the issue tracker
            settings = repo.settings
            settings['issue_tracker'] = False
            repo.settings = settings
            self.session.add(repo)
            self.session.commit()

            output = self.app.post(
                '/test/update/priorities', data=data)
            self.assertEqual(output.status_code, 404)

            # Check for an invalid project
            output = self.app.post(
                '/foo/update/priorities', data=data)
            self.assertEqual(output.status_code, 404)

        # Check for a non-admin user
        settings = repo.settings
        settings['issue_tracker'] = True
        repo.settings = settings
        self.session.add(repo)
        self.session.commit()

        user.username = 'ralph'
        with tests.user_set(pagure.APP, user):
            output = self.app.post(
                '/test/update/priorities', data=data)
            self.assertEqual(output.status_code, 403)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(
        PagureFlaskPrioritiestests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
