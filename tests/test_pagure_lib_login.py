# -*- coding: utf-8 -*-

"""
 (c) 2016 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>
   Farhaan Bukhsh <farhaan.bukhsh@gmail.com>

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
from pagure.exceptions import PagureException
import pagure.lib.login
import hashlib
from pagure import APP
import tests


class PagureLibLogintests(tests.Modeltests):
    """ Tests for pagure.lib.login """

    def test_id_generator(self):
        ''' Test pagure.lib.login.id_generator. '''
        self.assertEqual(
            pagure.lib.login.id_generator(size=3, chars=['a']),
            'aaa'
        )

    def test_get_users_by_group(self):
        ''' Test pagure.lib.login.get_users_by_group. '''

        users = pagure.lib.login.get_users_by_group(self.session, 'foo')
        self.assertEqual(users, [])

    def test_get_session_by_visitkey(self):
        ''' Test pagure.lib.login.get_session_by_visitkey. '''

        session = pagure.lib.login.get_session_by_visitkey(self.session, 'foo')
        self.assertEqual(session, None)

    def test_generate_hashed_value(self):
        ''' Test pagure.lib.login.generate_hashed_value. '''
        password = pagure.lib.login.generate_hashed_value('foo')
        self.assertTrue(password.startswith('$2$'))
        self.assertEqual(len(password), 63)

    def test_check_password(self):
        ''' Test pagure.lib.login.check_password. '''

        # Version 2
        password = pagure.lib.login.generate_hashed_value('foo')
        self.assertTrue(
            pagure.lib.login.check_password('foo', password))
        self.assertFalse(
            pagure.lib.login.check_password('bar', password))

        # Version 1
        password = '%s%s' % ('foo', APP.config.get('PASSWORD_SEED', None))
        password = '$1$' + hashlib.sha512(password).hexdigest()
        self.assertTrue(pagure.lib.login.check_password('foo', password))
        self.assertFalse(pagure.lib.login.check_password('bar', password))

        # Invalid password  -  No version
        password = '%s%s' % ('foo', APP.config.get('PASSWORD_SEED', None))
        password = hashlib.sha512(password).hexdigest()
        self.assertRaises(
            PagureException,
            pagure.lib.login.check_password,
            'foo', password
        )

        # Invalid password  -  Invalid version
        password = '$3$' + password
        self.assertRaises(
            PagureException,
            pagure.lib.login.check_password,
            'foo',
            password
        )
        password = '%s%s' % ('foo', APP.config.get('PASSWORD_SEED', None))
        password = hashlib.sha512(password).hexdigest()
        self.assertRaises(
            PagureException,
            pagure.lib.login.check_password,
            'foo', password
        )

        # Invalid password  -  Invalid version
        password = '$3$' + password
        self.assertRaises(
            PagureException,
            pagure.lib.login.check_password,
            'foo',
            password
        )

if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(PagureLibLogintests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
