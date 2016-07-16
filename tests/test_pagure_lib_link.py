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
import os

import pygit2
from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.lib.link
import tests

COMMENTS = [
    'Did you see #1?',
    'This is a duplicate of #2',
    'This is a fixes #3',
    'Might be worth looking at https://fedorahosted.org/pagure/tests2/issue/4',
    'This relates to #5',
    'Could this be related to https://fedorahosted.org/pagure/tests2/issue/6',
]


class PagureLibLinktests(tests.Modeltests):
    """ Tests for pagure.lib.link """

    def test_get_relation_relates(self):
        """ Test the get_relation function of pagure.lib.link with relates.
        """

        self.assertEqual(
            pagure.lib.link.get_relation(
                self.session,
                'test',
                None,
                COMMENTS[0],
                'relates',
            ),
            []
        )

        tests.create_projects(self.session)

        link = pagure.lib.link.get_relation(
            self.session, 'test', None, COMMENTS[4], 'relates')
        self.assertEqual(link, [])

        # Create the issue
        repo = pagure.lib.get_project(self.session, 'test')
        pagure.lib.new_issue(
            self.session,
            repo,
            title='foo',
            content='bar',
            user='pingou',
            ticketfolder=None,
            issue_id=5,
            notify=False)
        self.session.commit()

        for idx, comment in enumerate(COMMENTS):
            link = pagure.lib.link.get_relation(
                self.session, 'test', None, comment, 'relates')
            if idx == 4:
                self.assertEqual(
                    str(link),
                    '[Issue(5, project:test, user:pingou, title:foo)]')
            else:
                self.assertEqual(link, [])

        link = pagure.lib.link.get_relation(
            self.session, 'test', None, COMMENTS[5], 'relates')
        self.assertEqual(link, [])

        # Create the issue
        repo = pagure.lib.get_project(self.session, 'test')
        pagure.lib.new_issue(
            self.session,
            repo,
            title='another foo',
            content='another bar',
            user='pingou',
            ticketfolder=None,
            issue_id=6,
            notify=False)
        self.session.commit()

        for idx, comment in enumerate(COMMENTS):
            link = pagure.lib.link.get_relation(
                self.session, 'test', None, comment, 'relates')
            if idx == 4:
                self.assertEqual(
                    str(link),
                    '[Issue(5, project:test, user:pingou, title:foo)]')
            elif idx == 5:
                self.assertEqual(
                    str(link),
                    '[Issue(6, project:test, user:pingou, title:another foo)]')
            else:
                self.assertEqual(link, [])

    def test_get_relation_fixes(self):
        """ Test the get_relation function of pagure.lib.link with fixes.
        """

        self.assertEqual(
            pagure.lib.link.get_relation(
                self.session,
                'test',
                None,
                COMMENTS[0],
                'fixes',
            ),
            []
        )

        tests.create_projects(self.session)

        link = pagure.lib.link.get_relation(
            self.session, 'test', None, COMMENTS[2], 'fixes')
        self.assertEqual(link, [])

        # Create the issue
        repo = pagure.lib.get_project(self.session, 'test')
        pagure.lib.new_issue(
            self.session,
            repo,
            title='issue 3',
            content='content issue 3',
            user='pingou',
            ticketfolder=None,
            issue_id=3,
            notify=False)
        self.session.commit()

        for idx, comment in enumerate(COMMENTS):
            link = pagure.lib.link.get_relation(
                self.session, 'test', None, comment, 'fixes')
            if idx == 2:
                self.assertEqual(
                    str(link),
                    '[Issue(3, project:test, user:pingou, title:issue 3)]')
            else:
                self.assertEqual(link, [])

    def test_relates_regex(self):
        ''' Test the relates regex present in pagure.lib.link. '''
        text = 'relates  to   http://localhost/fork/pingou/test/issue/1'
        for index, regex in enumerate(pagure.lib.link.RELATES):
            if index == 2:
                self.assertNotEqual(regex.match(text), None)
            else:
                self.assertEqual(regex.match(text), None)

        text = 'relates http://209.132.184.222/fork/pingou/test/issue/1'
        for index, regex in enumerate(pagure.lib.link.RELATES):
            if index == 2:
                self.assertNotEqual(regex.match(text), None)
            else:
                self.assertEqual(regex.match(text), None)

        text = 'This relates  to  #5'
        for index, regex in enumerate(pagure.lib.link.RELATES):
            if index == 0:
                self.assertNotEqual(regex.match(text), None)
            else:
                self.assertEqual(regex.match(text), None)

        text = 'Could this be related to  '\
            ' https://fedorahosted.org/pagure/tests2/issue/6'
        for index, regex in enumerate(pagure.lib.link.RELATES):
            if index == 2:
                self.assertNotEqual(regex.match(text), None)
            else:
                self.assertEqual(regex.match(text), None)

    def test_fixes_regex(self):
        ''' Test the fixes regex present in pagure.lib.link. '''

        # project/issue matches
        def project_match(text, groups):
            match = None
            for regex in pagure.lib.link.FIXES:
                match = regex.match(text)
                if match:
                    break
            self.assertNotEqual(match, None)
            self.assertEqual(len(match.groups()), 2)
            self.assertEqual(match.groups(), groups)

        data = [
            # [string, groups]
        ]

        project_match('fixes     http://localhost/fork/pingou/test/issue/1',
            ('test', '1'))
        project_match('fix http://209.132.184.222/fork/pingou/test/issue/1',
            ('test', '1'))
        project_match('Could this be fixes  '
            ' https://fedorahosted.org/pagure/tests2/issue/6',
            ('tests2', '6'))
        project_match('merged https://pagure.io/myproject/pull-request/70',
            ('myproject', '70'))
        project_match('Now we merge https://pagure.io/myproject/pull-request/99',
            ('myproject', '99'))

        # issue matches
        def issue_match(text, issue):
            match = None
            for regex in pagure.lib.link.FIXES:
                match = regex.match(text)
                if match:
                    break
            self.assertNotEqual(match, None)
            self.assertEqual(len(match.groups()), 1)
            self.assertEqual(match.group(1), issue)

        issue_match('This fixed  #5', '5')
        issue_match('Merged  #17', '17')
        issue_match('Fixed:  #23', '23')
        issue_match('This commit fixes:  #42', '42')
        issue_match('Merge #137', '137')

        # no match
        def no_match(text):
            match = None
            for regex in pagure.lib.link.FIXES:
                match = regex.match(text)
                if match:
                    break
            self.assertEqual(match, None)

        no_match('nowhitespacemerge: #47')
        no_match('This commit unmerges #45')
        no_match('Fixed 45 typos')
        no_match('Fixed 4 typos')
        no_match("Merge branch 'work'")


if __name__ == '__main__':
    SUITE = unittest.TestLoader().loadTestsFromTestCase(PagureLibLinktests)
    unittest.TextTestRunner(verbosity=2).run(SUITE)
