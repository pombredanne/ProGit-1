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
import os

import pygit2
from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.lib
import tests


class PagureFlaskPluginRtdHooktests(tests.Modeltests):
    """ Tests for rtd_hook plugin of pagure """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskPluginRtdHooktests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.SESSION = self.session
        pagure.ui.SESSION = self.session
        pagure.ui.app.SESSION = self.session
        pagure.ui.plugins.SESSION = self.session
        pagure.ui.repo.SESSION = self.session
        pagure.ui.filters.SESSION = self.session

        pagure.APP.config['GIT_FOLDER'] = tests.HERE
        pagure.APP.config['FORK_FOLDER'] = os.path.join(
            tests.HERE, 'forks')
        pagure.APP.config['REQUESTS_FOLDER'] = os.path.join(
            tests.HERE, 'requests')
        pagure.APP.config['DOCS_FOLDER'] = os.path.join(
            tests.HERE, 'docs')
        self.app = pagure.APP.test_client()

    def test_plugin_pagure_request(self):
        """ Test the pagure_request plugin on/off endpoint. """

        tests.create_projects(self.session)

        user = tests.FakeUser(username='pingou')
        with tests.user_set(pagure.APP, user):
            output = self.app.get('/test/settings/Read the Doc')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn('<h3>Read the Doc settings</h3>', output.data)
            self.assertIn(
                '<input id="active" name="active" type="checkbox" value="y">',
                output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            data = {}

            output = self.app.post('/test/settings/Read the Doc', data=data)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn('<h3>Read the Doc settings</h3>', output.data)
            self.assertIn(
                '<input id="active" name="active" type="checkbox" value="y">',
                output.data)

            data['csrf_token'] = csrf_token
            # No git found
            output = self.app.post('/test/settings/Read the Doc', data=data)
            self.assertEqual(output.status_code, 404)

            # Create both the requests repo
            tests.create_projects_git(os.path.join(tests.HERE, 'requests'))

            # With the git repo
            tests.create_projects_git(tests.HERE)
            output = self.app.post(
                '/test/settings/Read the Doc', data=data,
                follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<section class="settings">\n  <h3>Settings for test</h3>',
                output.data)
            self.assertIn(
                '</button>\n                      Hook Read the Doc inactived',
                output.data)

            output = self.app.get('/test/settings/Read the Doc')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn('<h3>Read the Doc settings</h3>', output.data)
            self.assertIn(
                '<input id="active" name="active" type="checkbox" value="y">',
                output.data)

            self.assertFalse(os.path.exists(os.path.join(
                tests.HERE, 'requests', 'test.git', 'hooks',
                'post-receive.pagure')))

            # Activate hook
            data = {
                'csrf_token': csrf_token,
                'active': 'y',
                'project_name': 'foo',
            }

            output = self.app.post(
                '/test/settings/Read the Doc', data=data,
                follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<section class="settings">\n  <h3>Settings for test</h3>',
                output.data)
            self.assertIn(
                '</button>\n                      Hook Read the Doc activated',
                output.data)

            output = self.app.get('/test/settings/Read the Doc')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn('<h3>Read the Doc settings</h3>', output.data)
            self.assertIn(
                '<input checked id="active" name="active" type="checkbox" '
                'value="y">', output.data)

            self.assertTrue(os.path.exists(os.path.join(
                tests.HERE, 'test.git', 'hooks',
                'post-receive.rtd')))

            # De-Activate hook
            data = {'csrf_token': csrf_token}
            output = self.app.post(
                '/test/settings/Read the Doc', data=data,
                follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<section class="settings">\n  <h3>Settings for test</h3>',
                output.data)
            self.assertIn(
                '</button>\n                      Hook Read the Doc inactived',
                output.data)

            output = self.app.get('/test/settings/Read the Doc')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<div class="projectinfo m-t-1 m-b-1">\n'
                'test project #1        </div>', output.data)
            self.assertIn('<h3>Read the Doc settings</h3>', output.data)
            self.assertIn(
                '<input id="active" name="active" type="checkbox" '
                'value="y">', output.data)

            self.assertFalse(os.path.exists(os.path.join(
                tests.HERE, 'test.git', 'hooks',
                'post-receive.rtd')))

            # Try re-activate hook w/o the git repo
            data = {
                'csrf_token': csrf_token,
                'active': 'y',
                'project_name': 'foo',
            }
            shutil.rmtree(os.path.join(tests.HERE, 'test.git'))

            output = self.app.post('/test/settings/Read the Doc', data=data)
            self.assertEqual(output.status_code, 404)


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(
        PagureFlaskPluginRtdHooktests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
