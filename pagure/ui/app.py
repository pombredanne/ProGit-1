# -*- coding: utf-8 -*-

"""
 (c) 2014-2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import flask
from math import ceil

from sqlalchemy.exc import SQLAlchemyError

import pagure.exceptions
import pagure.lib
import pagure.lib.git
import pagure.forms
import pagure.ui.filters
from pagure import (APP, SESSION, login_required,
                    authenticated,
                    admin_session_timedout)


# Application
# pylint: disable=E1101


@APP.route('/browse/projects', endpoint='browse_projects')
@APP.route('/browse/projects/', endpoint='browse_projects')
@APP.route('/')
def index():
    """ Front page of the application.
    """
    sorting = flask.request.args.get('sorting') or None
    page = flask.request.args.get('page', 1)
    try:
        page = int(page)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    limit = APP.config['ITEM_PER_PAGE']
    start = limit * (page - 1)

    repos = pagure.lib.search_projects(
        SESSION,
        fork=False,
        start=start,
        limit=limit,
        sort=sorting)

    num_repos = pagure.lib.search_projects(
        SESSION,
        fork=False,
        count=True)
    total_page = int(ceil(num_repos / float(limit)))

    if authenticated() and flask.request.path == '/':
        return index_auth()

    return flask.render_template(
        'index.html',
        select="projects",
        repos=repos,
        repos_length=num_repos,
        total_page=total_page,
        page=page,
        sorting=sorting,
    )


def index_auth():
    """ Front page for authenticated user.
    """
    user = pagure.lib.search_user(SESSION, username=flask.g.fas_user.username)
    if not user:
        flask.abort(404, 'No user `%s` found, re-login maybe?' % (
            flask.g.fas_user.username))

    repopage = flask.request.args.get('repopage', 1)
    try:
        repopage = int(repopage)
        if repopage < 1:
            page = 1
    except ValueError:
        repopage = 1

    forkpage = flask.request.args.get('forkpage', 1)
    try:
        forkpage = int(forkpage)
        if forkpage < 1:
            page = 1
    except ValueError:
        forkpage = 1

    repos = pagure.lib.search_projects(
        SESSION,
        username=flask.g.fas_user.username,
        fork=False)
    repos_length = pagure.lib.search_projects(
        SESSION,
        username=flask.g.fas_user.username,
        fork=False,
        count=True)

    forks = pagure.lib.search_projects(
        SESSION,
        username=flask.g.fas_user.username,
        fork=True)
    forks_length = pagure.lib.search_projects(
        SESSION,
        username=flask.g.fas_user.username,
        fork=True,
        count=True)

    return flask.render_template(
        'index_auth.html',
        username=flask.g.fas_user.username,
        user=user,
        forks=forks,
        repos=repos,
        repopage=repopage,
        forkpage=forkpage,
        repos_length=repos_length,
        forks_length=forks_length,
    )


@APP.route('/search/')
@APP.route('/search')
def search():
    """ Search this pagure instance for projects or users.
    """
    stype = flask.request.args.get('type', 'projects')
    term = flask.request.args.get('term')
    page = flask.request.args.get('page', 1)
    try:
        page = int(page)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    if stype == 'projects':
        return flask.redirect(flask.url_for('view_projects', pattern=term))
    elif stype == 'projects_forks':
        return flask.redirect(flask.url_for(
            'view_projects', pattern=term, forks=True))
    else:
        return flask.redirect(flask.url_for('view_users', username=term))


@APP.route('/users/')
@APP.route('/users')
@APP.route('/users/<username>')
def view_users(username=None):
    """ Present the list of users.
    """
    page = flask.request.args.get('page', 1)
    try:
        page = int(page)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    users = pagure.lib.search_user(SESSION, pattern=username)

    if len(users) == 1:
        flask.flash('Only one result found, redirecting you to it')
        return flask.redirect(
            flask.url_for('view_user', username=users[0].username))

    limit = APP.config['ITEM_PER_PAGE']
    start = limit * (page - 1)
    end = limit * page
    users_length = len(users)
    users = users[start:end]

    total_page = int(ceil(users_length / float(limit)))

    for user in users:
        repos_length = pagure.lib.search_projects(
            SESSION,
            username=user.user,
            fork=False,
            count=True)

        forks_length = pagure.lib.search_projects(
            SESSION,
            username=user.user,
            fork=True,
            count=True)
        user.repos_length = repos_length
        user.forks_length = forks_length

    return flask.render_template(
        'user_list.html',
        users=users,
        users_length=users_length,
        total_page=total_page,
        page=page,
        select='users',
    )


@APP.route('/projects/')
@APP.route('/projects')
@APP.route('/projects/<pattern>')
def view_projects(pattern=None):
    """ Present the list of projects.
    """
    forks = flask.request.args.get('forks')
    page = flask.request.args.get('page', 1)

    try:
        page = int(page)
        if page < 1:
            page = 1
    except ValueError:
        page = 1

    select = 'projects'
    # If forks is specified, we want both forks and projects
    if str(forks).lower() in ['true', '1']:
        forks = None
        select = 'projects_forks'
    else:
        forks = False

    limit = APP.config['ITEM_PER_PAGE']
    start = limit * (page - 1)

    projects = pagure.lib.search_projects(
        SESSION, pattern=pattern, fork=forks, start=start, limit=limit)

    if len(projects) == 1:
        flask.flash('Only one result found, redirecting you to it')
        return flask.redirect(flask.url_for(
            'view_repo', repo=projects[0].name,
            username=projects[0].user.username if projects[0].is_fork else None
        ))

    limit = APP.config['ITEM_PER_PAGE']
    start = limit * (page - 1)
    end = limit * page
    projects_length = len(projects)
    projects = projects[start:end]

    total_page = int(ceil(projects_length / float(limit)))

    return flask.render_template(
        'index.html',
        repos=projects,
        repos_length=projects_length,
        total_page=total_page,
        page=page,
        select=select,
    )


@APP.route('/user/<username>/')
@APP.route('/user/<username>')
def view_user(username):
    """ Front page of a specific user.
    """
    user = pagure.lib.search_user(SESSION, username=username)
    if not user:
        flask.abort(404, 'No user `%s` found' % username)

    repopage = flask.request.args.get('repopage', 1)
    try:
        repopage = int(repopage)
        if repopage < 1:
            repopage = 1
    except ValueError:
        repopage = 1

    forkpage = flask.request.args.get('forkpage', 1)
    try:
        forkpage = int(forkpage)
        if forkpage < 1:
            forkpage = 1
    except ValueError:
        forkpage = 1

    limit = APP.config['ITEM_PER_PAGE']
    repo_start = limit * (repopage - 1)
    fork_start = limit * (forkpage - 1)

    repos = pagure.lib.search_projects(
        SESSION,
        username=username,
        fork=False,
        start=repo_start,
        limit=limit)
    repos_length = pagure.lib.search_projects(
        SESSION,
        username=username,
        fork=False,
        count=True)

    forks = pagure.lib.search_projects(
        SESSION,
        username=username,
        fork=True,
        start=fork_start,
        limit=limit)
    forks_length = pagure.lib.search_projects(
        SESSION,
        username=username,
        fork=True,
        count=True)

    total_page_repos = int(ceil(repos_length / float(limit)))
    total_page_forks = int(ceil(forks_length / float(limit)))

    return flask.render_template(
        'user_info.html',
        username=username,
        user=user,
        repos=repos,
        total_page_repos=total_page_repos,
        forks=forks,
        total_page_forks=total_page_forks,
        repopage=repopage,
        forkpage=forkpage,
        repos_length=repos_length,
        forks_length=forks_length,
    )


@APP.route('/user/<username>/requests/')
@APP.route('/user/<username>/requests')
def view_user_requests(username):
    """ Shows the pull-requests for the specified user.
    """
    user = pagure.lib.search_user(SESSION, username=username)
    if not user:
        flask.abort(404, 'No user `%s` found' % username)

    requests = pagure.lib.get_pull_request_of_user(
        SESSION,
        username=username
    )

    return flask.render_template(
        'user_requests.html',
        username=username,
        user=user,
        requests=requests,
    )


@APP.route('/new/', methods=('GET', 'POST'))
@APP.route('/new', methods=('GET', 'POST'))
@login_required
def new_project():
    """ Form to create a new project.
    """
    user = pagure.lib.search_user(SESSION, username=flask.g.fas_user.username)

    if not pagure.APP.config.get('ENABLE_NEW_PROJECTS', True):
        flask.abort(404, 'Creation of new project is not allowed on this \
                pagure instance')

    form = pagure.forms.ProjectForm()
    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        url = form.url.data
        avatar_email = form.avatar_email.data
        create_readme = form.create_readme.data

        try:
            message = pagure.lib.new_project(
                SESSION,
                name=name,
                description=description,
                url=url,
                avatar_email=avatar_email,
                user=flask.g.fas_user.username,
                blacklist=APP.config['BLACKLISTED_PROJECTS'],
                allowed_prefix=APP.config['ALLOWED_PREFIX'],
                gitfolder=APP.config['GIT_FOLDER'],
                docfolder=APP.config['DOCS_FOLDER'],
                ticketfolder=APP.config['TICKETS_FOLDER'],
                requestfolder=APP.config['REQUESTS_FOLDER'],
                add_readme=create_readme,
                userobj=user,
            )
            SESSION.commit()
            pagure.lib.git.generate_gitolite_acls()
            return flask.redirect(flask.url_for('view_repo', repo=name))
        except pagure.exceptions.PagureException as err:
            flask.flash(str(err), 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            flask.flash(str(err), 'error')

    return flask.render_template(
        'new_project.html',
        form=form,
    )


@APP.route('/settings/', methods=('GET', 'POST'))
@APP.route('/settings', methods=('GET', 'POST'))
@login_required
def user_settings():
    """ Update the user settings.
    """
    if admin_session_timedout():
        return flask.redirect(
            flask.url_for('auth_login', next=flask.request.url))

    user = pagure.lib.search_user(
        SESSION, username=flask.g.fas_user.username)
    if not user:
        flask.abort(404, 'User not found')

    form = pagure.forms.UserSettingsForm()
    if form.validate_on_submit():
        ssh_key = form.ssh_key.data

        try:
            message = 'Nothing to update'
            if user.public_ssh_key != ssh_key:
                pagure.lib.update_user_ssh(
                    SESSION,
                    user=user,
                    ssh_key=ssh_key,
                    keydir=APP.config.get('GITOLITE_KEYDIR', None),
                )
                SESSION.commit()
                message = 'Public ssh key updated'
            flask.flash(message)
            return flask.redirect(
                flask.url_for('.user_settings'))
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            flask.flash(str(err), 'error')
    elif flask.request.method == 'GET':
        form.ssh_key.data = user.public_ssh_key

    return flask.render_template(
        'user_settings.html',
        user=user,
        form=form,
    )


@APP.route('/markdown/', methods=['POST'])
def markdown_preview():
    """ Return the provided markdown text in html.

    The text has to be provided via the parameter 'content' of a POST query.
    """
    form = pagure.forms.ConfirmationForm()
    if form.validate_on_submit():
        return pagure.ui.filters.markdown_filter(flask.request.form['content'])
    else:
        flask.abort(400, 'Invalid request')


@APP.route('/settings/email/drop', methods=['POST'])
@login_required
def remove_user_email():
    """ Remove the specified email from the logged in user.
    """
    if admin_session_timedout():
        return flask.redirect(
            flask.url_for('auth_login', next=flask.request.url))

    user = pagure.lib.search_user(
        SESSION, username=flask.g.fas_user.username)
    if not user:
        flask.abort(404, 'User not found')

    if len(user.emails) == 1:
        flask.flash(
            'You must always have at least one email', 'error')
        return flask.redirect(
            flask.url_for('.user_settings')
        )

    form = pagure.forms.UserEmailForm()

    if form.validate_on_submit():
        email = form.email.data
        useremails = [mail.email for mail in user.emails]

        if email not in useremails:
            flask.flash(
                'You do not have the email: %s, nothing to remove' % email,
                'error')
            return flask.redirect(
                flask.url_for('.user_settings')
            )

        for mail in user.emails:
            if mail.email == email:
                user.emails.remove(mail)
                break
        try:
            SESSION.commit()
            flask.flash('Email removed')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            APP.logger.exception(err)
            flask.flash('Email could not be removed', 'error')

    return flask.redirect(flask.url_for('.user_settings'))


@APP.route('/settings/email/add/', methods=['GET', 'POST'])
@APP.route('/settings/email/add', methods=['GET', 'POST'])
@login_required
def add_user_email():
    """ Add a new email for the logged in user.
    """
    if admin_session_timedout():
        return flask.redirect(
            flask.url_for('auth_login', next=flask.request.url))

    user = pagure.lib.search_user(
        SESSION, username=flask.g.fas_user.username)
    if not user:
        flask.abort(404, 'User not found')

    form = pagure.forms.UserEmailForm(
        emails=[mail.email for mail in user.emails])
    if form.validate_on_submit():
        email = form.email.data

        try:
            pagure.lib.add_user_pending_email(SESSION, user, email)
            SESSION.commit()
            flask.flash('Email pending validation')
            return flask.redirect(flask.url_for('.user_settings'))
        except pagure.exceptions.PagureException as err:
            flask.flash(str(err), 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            APP.logger.exception(err)
            flask.flash('Email could not be added', 'error')

    return flask.render_template(
        'user_emails.html',
        user=user,
        form=form,
    )


@APP.route('/settings/email/default', methods=['POST'])
@login_required
def set_default_email():
    """ Set the default email address of the user.
    """
    if admin_session_timedout():
        return flask.redirect(
            flask.url_for('auth_login', next=flask.request.url))

    user = pagure.lib.search_user(
        SESSION, username=flask.g.fas_user.username)
    if not user:
        flask.abort(404, 'User not found')

    form = pagure.forms.UserEmailForm()
    if form.validate_on_submit():
        email = form.email.data
        useremails = [mail.email for mail in user.emails]

        if email not in useremails:
            flask.flash(
                'You do not have the email: %s, nothing to set' % email,
                'error')

            return flask.redirect(
                flask.url_for('.user_settings')
            )

        user.default_email = email

        try:
            SESSION.commit()
            flask.flash('Default email set to: %s' % email)
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            APP.logger.exception(err)
            flask.flash('Default email could not be set', 'error')

    return flask.redirect(flask.url_for('.user_settings'))


@APP.route('/settings/email/resend', methods=['POST'])
@login_required
def reconfirm_email():
    """ Re-send the email address of the user.
    """
    if admin_session_timedout():
        return flask.redirect(
            flask.url_for('auth_login', next=flask.request.url))

    user = pagure.lib.search_user(
        SESSION, username=flask.g.fas_user.username)
    if not user:
        flask.abort(404, 'User not found')

    form = pagure.forms.UserEmailForm()
    if form.validate_on_submit():
        email = form.email.data

        try:
            pagure.lib.resend_pending_email(SESSION, user, email)
            SESSION.commit()
            flask.flash('Confirmation email re-sent')
        except pagure.exceptions.PagureException as err:
            flask.flash(str(err), 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            APP.logger.exception(err)
            flask.flash('Confirmation email could not be re-sent', 'error')

    return flask.redirect(flask.url_for('.user_settings'))


@APP.route('/settings/email/confirm/<token>/')
@APP.route('/settings/email/confirm/<token>')
def confirm_email(token):
    """ Confirm a new email.
    """
    if admin_session_timedout():
        return flask.redirect(
            flask.url_for('auth_login', next=flask.request.url))

    email = pagure.lib.search_pending_email(SESSION, token=token)
    if not email:
        flask.flash('No email associated with this token.', 'error')
    else:
        try:
            pagure.lib.add_email_to_user(SESSION, email.user, email.email)
            SESSION.delete(email)
            SESSION.commit()
            flask.flash('Email validated')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            flask.flash(
                'Could not set the account as active in the db, '
                'please report this error to an admin', 'error')
            APP.logger.exception(err)

    return flask.redirect(flask.url_for('.user_settings'))


@APP.route('/ssh_info/')
@APP.route('/ssh_info')
def ssh_hostkey():
    """ Endpoint returning information about the SSH hostkey and fingerprint
    of the current pagure instance.
    """
    return flask.render_template(
        'doc_ssh_keys.html',
    )
