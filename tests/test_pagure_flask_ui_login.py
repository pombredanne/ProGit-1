# -*- coding: utf-8 -*-

"""
 (c) 2016 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>
   Farhaan Bukhsh <farhaan.bukhsh@gmail.com>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import datetime
import hashlib
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

import pagure.ui.login


class PagureFlaskLogintests(tests.Modeltests):
    """ Tests for flask app controller of pagure """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskLogintests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.APP.config['EMAIL_SEND'] = False
        pagure.APP.config['PAGURE_AUTH'] = 'local'
        pagure.SESSION = self.session
        pagure.ui.SESSION = self.session
        pagure.ui.app.SESSION = self.session
        pagure.ui.login.SESSION = self.session
        pagure.ui.filters.SESSION = self.session

        self.app = pagure.APP.test_client()

    def test_new_user(self):
        """ Test the new_user endpoint. """

        # Check before:
        items = pagure.lib.search_user(self.session)
        self.assertEqual(2, len(items))

        # First access the new user page
        output = self.app.get('/user/new')
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>New user - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/user/new" method="post">', output.data)

        # Create the form to send there

        # This has all the data needed
        data = {
            'user': 'foo',
            'fullname': 'user foo',
            'email_address': 'foo@bar.com',
            'password': 'barpass',
            'confirm_password': 'barpass',
        }

        # Submit this form  -  Doesn't work since there is no csrf token
        output = self.app.post('/user/new', data=data)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>New user - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/user/new" method="post">', output.data)

        csrf_token = output.data.split(
            'name="csrf_token" type="hidden" value="')[1].split('">')[0]

        # Submit the form with the csrf token
        data['csrf_token'] = csrf_token
        output = self.app.post('/user/new', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>New user - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/user/new" method="post">', output.data)
        self.assertIn('Username already taken.', output.data)

        # Submit the form with another username
        data['user'] = 'foouser'
        output = self.app.post('/user/new', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>New user - Pagure</title>', output.data)
        self.assertIn('Email address already taken.', output.data)

        # Submit the form with proper data
        data['email_address'] = 'foo@example.com'
        output = self.app.post('/user/new', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            'User created, please check your email to activate the account',
            output.data)

        # Check after:
        items = pagure.lib.search_user(self.session)
        self.assertEqual(3, len(items))

    def test_do_login(self):
        """ Test the do_login endpoint. """

        output = self.app.get('/login/')
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)

        # This has all the data needed
        data = {
            'username': 'foouser',
            'password': 'barpass',
        }

        # Submit this form  -  Doesn't work since there is no csrf token
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn('Insufficient information provided', output.data)

        csrf_token = output.data.split(
            'name="csrf_token" type="hidden" value="')[1].split('">')[0]

        # Submit the form with the csrf token  -  but invalid user
        data['csrf_token'] = csrf_token
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn('Username or password invalid.', output.data)

        # Create a local user
        self.test_new_user()

        items = pagure.lib.search_user(self.session)
        self.assertEqual(3, len(items))

        # Submit the form with the csrf token  -  but user not confirmed
        data['csrf_token'] = csrf_token
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn(
            'Invalid user, did you confirm the creation with the url '
            'provided by email?', output.data)

        # User in the DB, csrf provided  -  but wrong password submitted
        data['password'] = 'password'
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn('Username or password invalid.', output.data)

        # When account is not confirmed i.e user_obj != None
        data['password'] = 'barpass'
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn(
            'Invalid user, did you confirm the creation with the url '
            'provided by email?', output.data)

        # Wrong password submitted
        data['password'] = 'password'
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn('Username or password invalid.', output.data)

        # When account is not confirmed i.e user_obj != None
        data['password'] = 'barpass'
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn(
            'Invalid user, did you confirm the creation with the url '
            'provided by email?', output.data)

        # Confirm the user so that we can log in
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertNotEqual(item.token, None)

        # Remove the token
        item.token = None
        self.session.add(item)
        self.session.commit

        # Check the user
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertEqual(item.token, None)

        # Login but cannot save the session to the DB due to the missing IP
        # address in the flask request
        data['password'] = 'barpass'
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Home - Pagure</title>', output.data)
        self.assertIn(
            '<a class="nav-link" href="/login/?next=http://localhost/">',
            output.data)
        self.assertIn(
            'Could not set the session in the db, please report this error '
            'to an admin', output.data)

        # Make the password invalid
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertTrue(item.password.startswith('$2$'))

        # Remove the $2$
        item.password = item.password[3:]
        self.session.add(item)
        self.session.commit

        # Check the password
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertFalse(item.password.startswith('$2$'))

        # Try login again
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/dologin" method="post">', output.data)
        self.assertIn('Username or password of invalid format.', output.data)

        # Make the password be version 1
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertTrue(item.password.startswith('$2$'))

        # V1 password
        password = '%s%s' % ('barpass', None)
        password = hashlib.sha512(password).hexdigest()
        item.token = None
        item.password = '$1$%s' % password
        self.session.add(item)
        self.session.commit

        # Check the password
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertTrue(item.password.startswith('$1$'))

        # Log in with a v1 password
        output = self.app.post('/dologin', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Home - Pagure</title>', output.data)
        self.assertIn(
            '<a class="nav-link" href="/login/?next=http://localhost/">',
            output.data)
        self.assertIn(
            'Could not set the session in the db, please report this error '
            'to an admin', output.data)

    def test_confirm_user(self):
        """ Test the confirm_user endpoint. """

        output = self.app.get('/confirm/foo', follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Home - Pagure</title>', output.data)
        self.assertIn(
            'No user associated with this token.', output.data)

        # Create a local user
        self.test_new_user()

        items = pagure.lib.search_user(self.session)
        self.assertEqual(3, len(items))
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertTrue(item.password.startswith('$2$'))
        self.assertNotEqual(item.token, None)

        output = self.app.get(
            '/confirm/%s' % item.token, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            'Email confirmed, account activated', output.data)

    def test_lost_password(self):
        """ Test the lost_password endpoint. """

        output = self.app.get('/password/lost')
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Lost password - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/password/lost" method="post">', output.data)

        # Prepare the data to send
        data = {
            'username': 'foouser',
        }

        # Missing CSRF
        output = self.app.post('/password/lost', data=data)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Lost password - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/password/lost" method="post">', output.data)

        csrf_token = output.data.split(
            'name="csrf_token" type="hidden" value="')[1].split('">')[0]

        # With the CSRF  -  But invalid user
        data['csrf_token'] = csrf_token
        output = self.app.post(
            '/password/lost', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn('Username invalid.', output.data)

        # With the CSRF and a valid user
        data['username'] = 'foo'
        output = self.app.post(
            '/password/lost', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            'Check your email to finish changing your password', output.data)

        # With the CSRF and a valid user  -  but too quick after the last one
        data['username'] = 'foo'
        output = self.app.post(
            '/password/lost', data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn(
            'An email was sent to you less than 3 minutes ago, did you '
            'check your spam folder? Otherwise, try again after some time.',
            output.data)

    def test_reset_password(self):
        """ Test the reset_password endpoint. """

        output = self.app.get('/password/reset/foo', follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn('No user associated with this token.', output.data)
        self.assertIn('<form action="/dologin" method="post">', output.data)

        self.test_lost_password()
        self.test_new_user()

        # Check the password
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertNotEqual(item.token, None)
        self.assertTrue(item.password.startswith('$2$'))

        old_password = item.password
        token = item.token

        output = self.app.get(
            '/password/reset/%s' % token, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Change password - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/password/reset/', output.data)

        data = {
            'password': 'passwd',
            'confirm_password': 'passwd',
        }

        # Missing CSRF
        output = self.app.post(
            '/password/reset/%s' % token, data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Change password - Pagure</title>', output.data)
        self.assertIn(
            '<form action="/password/reset/', output.data)

        csrf_token = output.data.split(
            'name="csrf_token" type="hidden" value="')[1].split('">')[0]

        # With CSRF
        data['csrf_token'] = csrf_token
        output = self.app.post(
            '/password/reset/%s' % token, data=data, follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn('Password changed', output.data)

    def test_change_password(self):
        """ Test the change_password endpoint. """

        # Not logged in, redirects
        output = self.app.get('/password/change', follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Login - Pagure</title>', output.data)
        self.assertIn('<form action="/dologin" method="post">', output.data)

        user = tests.FakeUser()
        with tests.user_set(pagure.APP, user):
            output = self.app.get('/password/change')
            self.assertEqual(output.status_code, 404)
            self.assertIn('User not found', output.data)

        user = tests.FakeUser(username='foo')
        with tests.user_set(pagure.APP, user):
            output = self.app.get('/password/change')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Change password - Pagure</title>', output.data)
            self.assertIn(
                '<form action="/password/change" method="post">', output.data)

            data = {
                'old_password': 'foo',
                'password': 'foo',
                'confirm_password': 'foo',
            }

            # No CSRF token
            output = self.app.post('/password/change', data=data)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Change password - Pagure</title>', output.data)
            self.assertIn(
                '<form action="/password/change" method="post">', output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            # With CSRF  -  Invalid password format
            data['csrf_token'] = csrf_token
            output = self.app.post(
                '/password/change', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn('<title>Home - Pagure</title>', output.data)
            self.assertIn(
                'Could not update your password, either user or password '
                'could not be checked', output.data)

        self.test_new_user()

        # Remove token of foouser
        item = pagure.lib.search_user(self.session, username='foouser')
        self.assertEqual(item.user, 'foouser')
        self.assertNotEqual(item.token, None)
        self.assertTrue(item.password.startswith('$2$'))
        item.token = None
        self.session.add(item)
        self.session.commit()

        user = tests.FakeUser(username='foouser')
        with tests.user_set(pagure.APP, user):
            output = self.app.get('/password/change')
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Change password - Pagure</title>', output.data)
            self.assertIn(
                '<form action="/password/change" method="post">', output.data)

            data = {
                'old_password': 'foo',
                'password': 'foo',
                'confirm_password': 'foo',
            }

            # No CSRF token
            output = self.app.post('/password/change', data=data)
            self.assertEqual(output.status_code, 200)
            self.assertIn(
                '<title>Change password - Pagure</title>', output.data)
            self.assertIn(
                '<form action="/password/change" method="post">', output.data)

            csrf_token = output.data.split(
                'name="csrf_token" type="hidden" value="')[1].split('">')[0]

            # With CSRF  -  Incorrect password
            data['csrf_token'] = csrf_token
            output = self.app.post(
                '/password/change', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn('<title>Home - Pagure</title>', output.data)
            self.assertIn(
                'Could not update your password, either user or password '
                'could not be checked', output.data)

            # With CSRF  -  Correct password
            data['old_password'] = 'barpass'
            output = self.app.post(
                '/password/change', data=data, follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn('<title>Home - Pagure</title>', output.data)
            self.assertIn('Password changed', output.data)

    def test_logout(self):
        """ Test the auth_logout endpoint for local login. """

        output = self.app.get('/logout/', follow_redirects=True)
        self.assertEqual(output.status_code, 200)
        self.assertIn('<title>Home - Pagure</title>', output.data)
        self.assertNotIn('You have been logged out', output.data)
        self.assertIn(
            '<a class="nav-link" href="/login/?next=http://localhost/">',
            output.data)

        user = tests.FakeUser(username='foo')
        with tests.user_set(pagure.APP, user):
            output = self.app.get('/logout/', follow_redirects=True)
            self.assertEqual(output.status_code, 200)
            self.assertIn('<title>Home - Pagure</title>', output.data)
            self.assertIn('You have been logged out', output.data)
            # Due to the way the tests are running we do not actually
            # log out
            self.assertIn(
                '<a href="/logout/?next=http://localhost/">log out</a>',
                output.data)

    def test_settings_admin_session_timedout(self):
        """ Test the admin_session_timedout with settings endpoint. """
        lifetime = pagure.APP.config.get('ADMIN_SESSION_LIFETIME',
                                         datetime.timedelta(minutes=15))
        td1 = datetime.timedelta(minutes=1)
        # session already expired
        user = tests.FakeUser(username='foo')
        user.login_time = datetime.datetime.utcnow() - lifetime - td1
        with tests.user_set(pagure.APP, user):
            # not following the redirect because user_set contextmanager
            # will run again for the login page and set back the user
            # which results in a loop, since admin_session_timedout will
            # redirect again for the login page
            output = self.app.get('/settings/')
            self.assertEqual(output.status_code, 302)
            self.assertIn('http://localhost/login/', output.location)
        # session did not expire
        user.login_time = datetime.datetime.utcnow() - lifetime + td1
        with tests.user_set(pagure.APP, user):
            output = self.app.get('/settings/')
            self.assertEqual(output.status_code, 200)

    @patch('flask.flash')
    @patch('flask.g')
    def test_admin_session_timedout(self, g, flash):
        """ Test the call to admin_session_timedout. """
        lifetime = pagure.APP.config.get('ADMIN_SESSION_LIFETIME',
                                         datetime.timedelta(minutes=15))
        td1 = datetime.timedelta(minutes=1)
        # session already expired
        user = tests.FakeUser(username='foo')
        user.login_time = datetime.datetime.utcnow() - lifetime - td1
        g.fas_user = user
        self.assertTrue(pagure.admin_session_timedout())
        # session did not expire
        user.login_time = datetime.datetime.utcnow() - lifetime + td1
        g.fas_user = user
        self.assertFalse(pagure.admin_session_timedout())


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(PagureFlaskLogintests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
