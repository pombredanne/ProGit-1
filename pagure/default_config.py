# -*- coding: utf-8 -*-

"""
 (c) 2014-2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import os
from datetime import timedelta


# Set the time after which the admin session expires
ADMIN_SESSION_LIFETIME = timedelta(minutes=20)

# secret key used to generate unique csrf token
SECRET_KEY = '<insert here your own key>'

# url to the database server:
DB_URL = 'sqlite:////var/tmp/pagure_dev.sqlite'

# url to datagrepper (optional):
#DATAGREPPER_URL = 'https://apps.fedoraproject.org/datagrepper'
#DATAGREPPER_CATEGORY = 'pagure'

# The FAS group in which the admin of pagure are
ADMIN_GROUP = 'sysadmin-main'

# Hard-code a list of users that are global admins
PAGURE_ADMIN_USERS = []

# Whether or not to send emails
EMAIL_SEND = False

# The email address to which the flask.log will send the errors (tracebacks)
EMAIL_ERROR = 'pingou@pingoured.fr'

# The URL at which the project is available.
APP_URL = 'https://pagure.org/'


# Enables / Disables tickets for project for the entire pagure instance
ENABLE_TICKETS = True

# Enables / Disables creating projects on this pagure instance
ENABLE_NEW_PROJECTS = True

# Enables / Disables deleting projects on this pagure instance
ENABLE_DEL_PROJECTS = True

# Enables / Disables managing access to the repos
ENABLE_USER_MNGT = True

# Enables / Disables managing groups via the UI
ENABLE_GROUP_MNGT = True

# Enables / Disables showing all the projects by default on the front page
SHOW_PROJECTS_INDEX = ['repos', 'myrepos', 'myforks']

# The URL to use to clone the git repositories.
GIT_URL_SSH = 'ssh://git@pagure.org/'
GIT_URL_GIT = 'git://pagure.org/'


# Number of items displayed per page
ITEM_PER_PAGE = 48

# Maximum size of the uploaded content
MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 megabytes

# IP addresses allowed to access the internal endpoints
IP_ALLOWED_INTERNAL = ['127.0.0.1', 'localhost', '::1']

# Redis configuration
EVENTSOURCE_SOURCE = None
WEBHOOK = False
REDIS_HOST = '0.0.0.0'
REDIS_PORT = 6379
REDIS_DB = 0
EVENTSOURCE_PORT = 8080

# Folder containing to the git repos
GIT_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'repos'
)

# Folder containing the forks repos
FORK_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'forks'
)

# Folder containing the docs repos
DOCS_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'docs'
)

# Folder containing the tickets repos
TICKETS_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'tickets'
)

# Folder containing the pull-requests repos
REQUESTS_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'requests'
)

# Folder containing the clones for the remote pull-requests
REMOTE_GIT_FOLDER = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'remotes'
)


# Configuration file for gitolite
GITOLITE_CONFIG = os.path.join(
    os.path.abspath(os.path.dirname(__file__)),
    '..',
    'gitolite.conf'
)

# Configuration keys to specify where the upload folder is and what is its
# name
UPLOAD_FOLDER = 'releases/'
UPLOAD_FOLDER_PATH = './' + UPLOAD_FOLDER

# Home folder of the gitolite user -- Folder where to run gl-compile-conf from
GITOLITE_HOME = None

# Version of gitolite used: 2 or 3?
GITOLITE_VERSION = 3

# Folder containing all the public ssh keys for gitolite
GITOLITE_KEYDIR = None

# Path to the gitolite.rc file
GL_RC = None
# Path to the /bin directory where the gitolite tools can be found
GL_BINDIR = None


#SMTP settings
SMTP_SERVER = 'localhost'
SMTP_PORT = 25
SMTP_SSL = False

# Specify both for enabling SMTP auth
SMTP_USERNAME = None
SMTP_PASSWORD = None


# Email used to sent emails
FROM_EMAIL = 'pagure@pagure.org'

DOMAIN_EMAIL_NOTIFICATIONS = 'pagure.org'
SALT_EMAIL = '<secret key to be changed>'

# Specify which authentication method to use, defaults to `fas` can be or
# `local`
# Default: ``fas``.
PAGURE_AUTH = 'fas'

# When this is set to True, the session cookie will only be returned to the
# server via ssl (https). If you connect to the server via plain http, the
# cookie will not be sent. This prevents sniffing of the cookie contents.
# This may be set to False when testing your application but should always
# be set to True in production.
# Default: ``True``.
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_NAME = 'pagure'

# Boolean specifying wether to check the user's IP address when retrieving
# its session. This make things more secure (thus is on by default) but
# under certain setup it might not work (for example is there are proxies
# in front of the application).
CHECK_SESSION_IP = True

# Lenght for short commits ids or file hex
SHORT_LENGTH = 6

# Used by SESSION_COOKIE_PATH
APPLICATION_ROOT = '/'

# List of blacklisted project names
BLACKLISTED_PROJECTS = [
    'static', 'pv', 'releases', 'new', 'api', 'settings',
    'logout', 'login', 'users', 'groups', 'projects', 'ssh_info']

# List of prefix allowed in project names
ALLOWED_PREFIX = []

# List of blacklisted group names
BLACKLISTED_GROUPS = ['forks']


ACLS = {
    'create_project': 'Create a new project',
    'fork_project': 'Fork a project',
    'issue_assign': 'Assign issue to someone',
    'issue_create': 'Create a new ticket against this project',
    'issue_change_status': 'Change the status of a ticket of this project',
    'issue_comment': 'Comment on a ticket of this project',
    'pull_request_close': 'Close a pull-request of this project',
    'pull_request_comment': 'Comment on a pull-request of this project',
    'pull_request_flag': 'Flag a pull-request of this project',
    'pull_request_merge': 'Merge a pull-request of this project',
}
