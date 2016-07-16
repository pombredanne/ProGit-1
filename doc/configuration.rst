Configuration
=============

Pagure offers a wide varieties of options that must or can be used to
adjust its behavior.


Must options
------------

Here are the options you must set up in order to get pagure running.


SECRET_KEY
~~~~~~~~~~

This key is used by flask to create the session. It should be kept secret
and set as a long and random string.


SALT_EMAIL
~~~~~~~~~~

This key is used for when sending notification to ensure that when sending
notifications to different users, each one of them has a different, unique
and un-fakable ``Reply-To`` header that is then used by the milter to find
out if the response received is a real one or a fake/invalid one.


DB_URL
~~~~~~

This key indicates to the framework how and where to connect to the database
server. Pagure using `SQLAchemy <http://www.sqlalchemy.org/>`_ it can connect
to a wide range of database server including MySQL, PostgreSQL and SQLite.

Examples values:

::

    DB_URL=mysql://user:pass@host/db_name
    DB_URL=postgres://user:pass@host/db_name
    DB_URL = 'sqlite:////var/tmp/pagure_dev.sqlite'

Defaults to ``sqlite:////var/tmp/pagure_dev.sqlite``


APP_URL
~~~~~~~

This key indicates the URL at which this pagure instance will be made available.

Defaults to: ``https://pagure.org/``


EMAIL_ERROR
~~~~~~~~~~~

Pagure sends email when it caches an un-expected error (which saves you from
having to monitor the logs regularly but if you like, the error is still
present in the logs).
This setting allows you to specify to which email address to send these error
reports.


GIT_URL_SSH
~~~~~~~~~~~

This configuration key provides the information to the user on how to clone
the git repos hosted on pagure via `SSH <https://en.wikipedia.org/wiki/Secure_Shell>`_.

The URL should end with a slash ``/``.

Defaults to: ``'ssh://git@pagure.org/'``


GIT_URL_GIT
~~~~~~~~~~~
This configuration key provides the information to the user on how to clone
the git repos hosted on pagure anonymously. This access can be granted via
the ``git://`` or ``http(s)://`` protocols.

The URL should end with a slash ``/``.

Defaults to: ``'git://pagure.org/'``


GIT_FOLDER
~~~~~~~~~~

This configuration key points to where the folders containing the git repos
of the projects are located.

Each project in pagure has 4 git repositories:

- the main repo for the code
- the doc repo showed in the doc server
- the ticket and request repos storing the metadata of the
  tickets/pull-requests

There are then another 2 folders specifying the locations of the forks and
remote git repo used for the remotes pull-requests (ie: pull-request coming
from a project not hosted on this instance of pagure).


FORK_FOLDER
~~~~~~~~~~~

This configuration key points to the folder where the git repos of forks of
the projects are stored.


DOCS_FOLDER
~~~~~~~~~~~

This configuration key points to the folder where the git repos for the
documentation of the projects are stored.


TICKETS_FOLDER
~~~~~~~~~~~~~~

This configuration key points to the folder where the git repos storing the
metadata of the tickets opened against the project are stored .


REQUESTS_FOLDER
~~~~~~~~~~~~~~~

This configuration key points to the folder where the git repos storing the
metadata of the pull-requests opened against the project are stored.


REMOTE_GIT_FOLDER
~~~~~~~~~~~~~~~~~

This configuration key points to the folder where the remote git repos (ie:
not hosted on pagure) that someone used to open a pull-request against a
project hosted on pagure are stored.


SESSION_COOKIE_SECURE
~~~~~~~~~~~~~~~~~~~~~

When this is set to True, the session cookie will only be returned to the
server via ssl (https). If you connect to the server via plain http, the
cookie will not be sent. This prevents sniffing of the cookie contents.
This may be set to False when testing your application but should always
be set to True in production.

Defaults to: ``False`` for development, must be ``True`` in production with
https.


FROM_EMAIL
~~~~~~~~~~

This setting allows to specify the email address used by this pagure instance
when sending emails (notifications).

Defaults to: ``pagure@pagure.org``


DOMAIN_EMAIL_NOTIFICATIONS
~~~~~~~~~~~~~~~~~~~~~~~~~~

This setting allows to specify the domain used by this pagure instance
when sending emails (notifications). More precisely, this setting is used
when building the ``msg-id`` header of the emails sent.

Defaults to: ``pagure.org``


Configure Gitolite
------------------

Pagure uses `gitolite <http://gitolite.com/>`_ as an authorization layer.
Gitolite relies on `SSH <https://en.wikipedia.org/wiki/Secure_Shell>`_ for
the authentication. In other words, SSH let you in and gitolite check if you
are allowed to do what you are trying to do once you are inside.


GITOLITE_HOME
~~~~~~~~~~~~~

This configuration key should point to the home of the user under which
gitolite is ran.


GITOLITE_VERSION
~~~~~~~~~~~~~~~~

This configuration key allows to specify which version of gitolite you are
using, it can be either ``2`` or ``3``.

Defaults to: ``3``.


GITOLITE_KEYDIR
~~~~~~~~~~~~~~~

This configuration key points to the folder where gitolite stores and accesses
the public SSH keys of all the user have access to the server.

Since pagure is the user interface, it is pagure that writes down the files
in this directory effectively setting up the users to be able to use gitolite.


GL_RC
~~~~~

This configuration key must point to the file ``gitolite.rc`` used by gitolite
to record who has access to what (ie: who has access to which repo/branch).


GL_BINDIR
~~~~~~~~~

This configuration key indicates the folder in which the gitolite tools can
be found. It can be as simple as ``/usr/bin/`` if the tools have been installed
using a package manager or something like ``/opt/bin/`` for a more custom
install.


EventSource options
-------------------

EVENTSOURCE_SOURCE
~~~~~~~~~~~~~~~~~~

This configuration key indicates the URL at which the EventSource server is
available. If not defined, pagure will behave as if there are no EventSource
server running.

EVENTSOURCE_PORT
~~~~~~~~~~~~~~~~

This configuration key indicates the port at which the EventSource server is
running. This allows adjusting the port via the configuration file instead
of hard-coding it in the code.

.. note:: The EventSource server requires a redis server (see ``Redis options``
         below)


Web-hooks notifications
-----------------------

WEBHOOK
~~~~~~~

This configuration key allows turning on or off web-hooks notifications for
this pagure instance.

Defaults to: ``False``.

.. note:: The Web-hooks server requires a redis server (see ``Redis options``
         below)


Redis options
-------------

REDIS_HOST
~~~~~~~~~~

This configuration key indicates the host at which the `redis <http://redis.io/>`_
server is running.

Defaults to: ``0.0.0.0``.

REDIS_PORT
~~~~~~~~~~

This configuration key indicates the port at which the reds server can be
contacted.

Defaults to: ``6379``.

REDIS_DB
~~~~~~~~

This configuration key indicates the name of the redis database to use to
communicate with the EventSource server.

Defaults to: ``0``.


Authentication options
----------------------

ADMIN_GROUP
~~~~~~~~~~~

List of groups, local or remotes (if the openid server used supports the
group extension), that are site admin. These admins can regenerate the
gitolite configuration, the ssh key files, the hook-token for every project
as well as manage users and groups.


PAGURE_ADMIN_USERS
~~~~~~~~~~~~~~~~~~

List of usernames that are site admin. These admins have the same rights as
the user in the admin groups (listed above) as well as admin rights to
every projects hosted on this pagure instance.


Optional options
----------------

SSH_KEYS
~~~~~~~~

It is a good pratice to publish the fingerprint and public SSH key of a
server you provide access to.
Pagure offers the possibility to expose this information based on the values
set in the configuration file, in the ``SSH_KEYS`` configuration key.

See the `SSH hostkeys/Fingerprints page on pagure.io <https://pagure.io/ssh_info>`_.

.. warning: The format is important

    SSH_KEYS = {'RSA': {'fingerprint': '<foo>', 'pubkey': '<bar>'}}

Where `<foo>` and `<bar>` must be replaced by your values.


ITEM_PER_PAGE
~~~~~~~~~~~~~
This configuration key allows you to configure the length of a page by
setting the number of items on the page. Items can be commits, users, groups
or projects for example.

Defaults to: ``50``.


SMTP_SERVER
~~~~~~~~~~~

This configuration key allows to configure the SMTP server to use when
sending emails.

Defaults to: ``localhost``.

SMTP_PORT
~~~~~~~~~

This configuration key allow to define the SMTP server port.

SMTP by default uses TCP port 25. The protocol for mail submission is
the same, but uses port 587.
SMTP connections secured by SSL, known as SMTPS, default to port 465
(nonstandard, but sometimes used for legacy reasons).

Defaults to: ``25``

SMTP_SSL
~~~~~~~~

This configuration key allows to specify whether the SMTP connections
should secured over SSL

Defaults to: ``False``

SMTP_USERNAME
~~~~~~~~~~~~~

This configuration key allows usage of SMTP with auth

Note: Specify SMTP_USERNAME and SMTP_PASSWORD for using SMTP auth

Defaults to: ``None``

SMTP_PASSWORD
~~~~~~~~~~~~~

This configuration key allows usage of SMTP with auth

Note: Specify SMTP_USERNAME and SMTP_PASSWORD for using SMTP auth

Defaults to: ``None``

SHORT_LENGTH
~~~~~~~~~~~~

This configuration key allows to configure the length of the commit ids or
file hex displayed in the user interface.

Defaults to: ``6``.


BLACKLISTED_PROJECTS
~~~~~~~~~~~~~~~~~~~~

This configuration key allows to set a list of project name that are forbidden.
This list is used for example to avoid conflicts at the URL level between the
static files located under ``/static/`` and a project that would be named
``static`` and thus be located at ``/static``.

Defaults to:

::

    [
        'static', 'pv', 'releases', 'new', 'api', 'settings',
        'logout', 'login', 'users', 'groups'
    ]



CHECK_SESSION_IP
~~~~~~~~~~~~~~~~

This configuration key allows to configure whether to check the user's IP
address when retrieving its session. This makes things more secure but
under certain setup it might not work (for example if there are proxies
in front of the application).

Defaults to: ``True``.


PAGURE_AUTH
~~~~~~~~~~~~

This configuration key allows to specify which authentication method to use.
Pagure supports currently two authentication methods, one relying on the
Fedora Account System `FAS <https://admin.fedoraproject.org/accounts>`_,
the other relying on local user accounts.
It can therefore be either ``fas`` or ``local``.

Defaults to: ``fas``.


IP_ALLOWED_INTERNAL
~~~~~~~~~~~~~~~~~~~

This configuration key allows to specify which IP addresses are allowed
to access the internal API endpoint. These endpoints are accessed by the
milters for example and allow to perform action in the name of someone else.
So they are sensitive, thus the check for the origin of the request using
these endpoints.

Defaults to: ``['127.0.0.1', 'localhost', '::1']``.


MAX_CONTENT_LENGTH
~~~~~~~~~~~~~~~~~~

This configuration key allows to specify the maximum size allowed when
uploading content to pagure (for example, screenshots to a ticket).

Defaults to: ``4 * 1024 * 1024`` which corresponds to 4 megabytes.


ENABLE_TICKETS
~~~~~~~~~~~~~~

This configuration key allows to activate or de-activate the ticketing system
for all the projects hosted on this pagure instance.

Defaults to: ``True``


ENABLE_NEW_PROJECTS
~~~~~~~~~~~~~~~~~~~

This configuration key allows to create or forbids creating new projects in
the user interface of this pagure instance.

Defaults to: ``True``


ENABLE_DEL_PROJECTS
~~~~~~~~~~~~~~~~~~~

This configuration key allows to delete or forbids deleting projects in
the user interface of this pagure instance.

Defaults to: ``True``


EMAIL_SEND
~~~~~~~~~~

This configuration key allows turning on or off all email notification for
this pagure instance. This can be useful to turn off when developing on
pagure, or for test or pre-production instances.

Defaults to: ``True``.


OLD_VIEW_COMMIT_ENABLED
~~~~~~~~~~~~~~~~~~~~~~~

In version 1.3, pagure changed its URL scheme to view the commit of a
project in order to add support for pseudo-namespaced projects.

For pagure instances older than 1.3, who care about backward compatibility,
we added an endpoint ``view_commit_old`` that brings URL backward
compatibility for URLs using the complete git hash (the 40 characters).
For URLs using a shorter hash, the URLs will remain broken.

This configuration key allows turning on or off this backward compatibility
which is useful for pagure instances running since before 1.3 but is not
for newer instances.

Defaults to: ``False``.
