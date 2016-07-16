Upgrading Pagure
================

From 2.2 to 2.3
---------------

2.3 brings a few changes impacting the database scheme, including a new
`duplicate` status for tickets, a feature allowing one to `watch` or
`unwatch` a project and notifications on tickets as exist on pull-requests.

Therefore, when upgrading from 2.2.x to 2.3, you will have to :

* Create the new DB tables and the new status field using the ``createdb.py`` script.

* Update the database schame using alembic: ``alembic upgrade head``

This update also brings a new configuration key:

* ``PAGURE_ADMIN_USERS`` allows to mark some users as instance-wide admins, giving
  them full access to every projects, private or not. This feature can then be
  used as a way to clean spams.
* ``SMTP_PORT`` allows to specify the port to use when contacting the SMTP
  server
* ``SMTP_SSL`` allows to specify whether to use SSL when contacting the SMTP
  server
* ``SMTP_USERNAME`` and ``SMTP_PASSWORD`` if provided together allow to contact
  an SMTP requiring authentication.

In this update is also added the script ``api_key_expire_mail.py`` meant to be
run by a daily cron job and warning users when their API token is nearing its
expiration date.



2.2.2
-----

Release 2.2.2 contains an important security fix, blocking a source of XSS
attack.



From 2.1 to 2.2
---------------

2.2 brings a number of bug fixes and a few improvements.

One of the major changes impacts the databases where we must change some of the
table so that the foreign key cascade on delete (fixes deleting a project when a
few plugins were activated).

When upgrading for 2.1 to 2.2 all you will have to do is:

* Update the database scheme using alembic: ``alembic upgrade head``

.. note:: If you run another database system than PostgreSQL the alembic
  revision ``317a285e04a8_delete_hooks.py`` will require adjustment as the
  foreign key constraints are named and the names are driver dependant.



From 2.0 to 2.1
---------------

2.1 brings its usual flow of improvements and bug fixes.

When upgrading from 2.0.x to 2.1 all you will have to:

* Update the database schame using alembic: ``alembic upgrade head``



From 1.x to 2.0
---------------

As the version change indicates, 2.0 brings quite a number of changes,
including some that are not backward compatible.

When upgrading to 2.0 you will have to:

* Update the database schema using alembic: ``alembic upgrade head``

* Create the new DB tables so that the new plugins work using the
  ``createdb.py`` script

* Move the forks git repo

Forked git repos are now located under the same folder as the regular git
repos, just under a ``forks/`` subfolder.
So the structure changes from: ::

    repos/
    ├── foo.git
    └── bar.git

    forks/
    ├── patrick/
    │   ├── test.git
    │   └── ipsilon.git
    └── pingou/
        ├── foo.git
        └── bar.git

to: ::

    repos/
    ├── foo.git
    ├── bar.git
    └── forks/
        ├── patrick/
        │   ├── test.git
        │   └── ipsilon.git
        └── pingou/
            ├── foo.git
            └── bar.git

So the entire ``forks`` folder is moved under the ``repos`` folder where
the other repositories are, containing the sources of the projects.


Git repos for ``tickets``, ``requests`` and ``docs`` will be trickier to
move as the structure changes from: ::

    tickets/
    ├── foo.git
    ├── bar.git
    ├── patrick/
    │   ├── test.git
    │   └── ipsilon.git
    └── pingou/
        ├── foo.git
        └── bar.git

to: ::

    tickets/
    ├── foo.git
    ├── bar.git
    └── forks/
        ├── patrick/
        │   ├── test.git
        │   └── ipsilon.git
        └── pingou/
            ├── foo.git
            └── bar.git

Same for the ``requests`` and the ``docs`` git repos.

As you can see in the ``tickets``, ``requests`` and ``docs`` folders there
are two types of folders, git repos which are folder with a name ending
with ``.git``, and folder corresponding to usernames. These last ones are
the ones to be moved into a subfolder ``forks/``.

This can be done using something like: ::

    mkdir forks
    for i in `ls -1 |grep -v '\.git'`; do mv $i forks/; done

* Re-generate the gitolite configuration.

This can be done via the ``Re-generate gitolite ACLs file`` button in the
admin page.

* Keep URLs backward compatible

The support of pseudo-namespace in pagure 2.0 has required some changes
to the URL schema:
https://pagure.io/pagure/053d8cc95fcd50c23a8b0a7f70e55f8d1cc7aebb
became:
https://pagure.io/pagure/c/053d8cc95fcd50c23a8b0a7f70e55f8d1cc7aebb
(Note the added /c/ in it)

We introduced a backward compatibility fix for this.

This fix is however *disabled* by default so if you wish to keep the URLs
valid, you will need to adjust you configuration file to include: ::

    OLD_VIEW_COMMIT_ENABLED = True
