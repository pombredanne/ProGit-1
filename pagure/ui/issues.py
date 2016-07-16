# -*- coding: utf-8 -*-

"""
 (c) 2014-2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import flask
import os
from collections import defaultdict

import pygit2
from sqlalchemy.exc import SQLAlchemyError

import chardet
import kitchen.text.converters as ktc
import mimetypes

import pagure.doc_utils
import pagure.lib
import pagure.forms
from pagure import (APP, SESSION, LOG, __get_file_in_tree,
                    login_required, is_repo_admin, authenticated)


# pylint: disable=E1101

# URLs

@APP.route('/<repo:repo>/issue/<int:issueid>/update/', methods=['GET', 'POST'])
@APP.route('/<repo:repo>/issue/<int:issueid>/update', methods=['GET', 'POST'])
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/update/',
           methods=['GET', 'POST'])
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/update',
           methods=['GET', 'POST'])
@login_required
def update_issue(repo, issueid, username=None):
    ''' Add a comment to an issue. '''
    is_js = flask.request.args.get('js', False)

    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if flask.request.method == 'GET':
        if not is_js:
            flask.flash('Invalid method: GET', 'error')
        return flask.redirect(flask.url_for(
            'view_issue', username=username, repo=repo.name, issueid=issueid))

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    issue = pagure.lib.search_issues(SESSION, repo, issueid=issueid)

    if issue is None or issue.project != repo:
        flask.abort(404, 'Issue not found')

    if issue.private and not is_repo_admin(repo) \
            and (not authenticated() or
                 not issue.user.user == flask.g.fas_user.username):
        flask.abort(
            403, 'This issue is private and you are not allowed to view it')

    if flask.request.form.get('edit_comment'):
        commentid = flask.request.form.get('edit_comment')
        form = pagure.forms.EditCommentForm()
        if form.validate_on_submit():
            return edit_comment_issue(
                repo.name, issueid, commentid, username=username)

    status = pagure.lib.get_issue_statuses(SESSION)
    form = pagure.forms.UpdateIssueForm(
        status=status, priorities=repo.priorities)

    if form.validate_on_submit():
        repo_admin = is_repo_admin(repo)

        if flask.request.form.get('drop_comment'):
            commentid = flask.request.form.get('drop_comment')

            comment = pagure.lib.get_issue_comment(
                SESSION, issue.uid, commentid)
            if comment is None or comment.issue.project != repo:
                flask.abort(404, 'Comment not found')

            if (flask.g.fas_user.username != comment.user.username
                    or comment.parent.status != 'Open') \
                    and not is_repo_admin(repo):
                flask.abort(
                    403,
                    'You are not allowed to remove this comment from '
                    'this issue')

            SESSION.delete(comment)
            try:
                SESSION.commit()
                if not is_js:
                    flask.flash('Comment removed')
            except SQLAlchemyError as err:  # pragma: no cover
                is_js = False
                SESSION.rollback()
                LOG.error(err)
                if not is_js:
                    flask.flash(
                        'Could not remove the comment: %s' % commentid,
                        'error')
            if is_js:
                return 'ok'
            else:
                return flask.redirect(flask.url_for(
                    'view_issue', username=username, repo=repo.name,
                    issueid=issueid))

        comment = form.comment.data
        depends = []
        for depend in form.depends.data.split(','):
            if depend.strip():
                try:
                    depends.append(int(depend.strip()))
                except ValueError:
                    pass

        blocks = []
        for block in form.blocks.data.split(','):
            if block.strip():
                try:
                    blocks.append(int(block.strip()))
                except ValueError:
                    pass

        assignee = form.assignee.data
        new_status = form.status.data
        new_priority = None
        try:
            new_priority = int(form.priority.data)
        except:
            pass
        tags = [
            tag.strip()
            for tag in form.tag.data.split(',')
            if tag.strip()]

        try:

            # New comment
            if comment:
                message = pagure.lib.add_issue_comment(
                    SESSION,
                    issue=issue,
                    comment=comment,
                    user=flask.g.fas_user.username,
                    ticketfolder=APP.config['TICKETS_FOLDER'],
                )
                SESSION.commit()
                if message and not is_js:
                    flask.flash(message)

            if repo_admin:
                # Adjust (add/remove) tags
                messages = pagure.lib.update_tags(
                    SESSION, issue, tags,
                    username=flask.g.fas_user.username,
                    ticketfolder=APP.config['TICKETS_FOLDER']
                )
                if not is_js:
                    for message in messages:
                        flask.flash(message)

            # The meta-data can only be changed by admins, which means they
            # will be missing for non-admin and thus reset if we let them
            if repo_admin:
                # Assign or update assignee of the ticket
                message = pagure.lib.add_issue_assignee(
                    SESSION,
                    issue=issue,
                    assignee=assignee or None,
                    user=flask.g.fas_user.username,
                    ticketfolder=APP.config['TICKETS_FOLDER'],
                )
                SESSION.commit()
                if message and not is_js:
                    flask.flash(message)

                # Update status
                if new_status in status:
                    message = pagure.lib.edit_issue(
                        SESSION,
                        issue=issue,
                        status=new_status,
                        private=issue.private,
                        user=flask.g.fas_user.username,
                        ticketfolder=APP.config['TICKETS_FOLDER'],
                    )
                    SESSION.commit()
                    if message:
                        flask.flash(message)

                # Update priority
                if str(new_priority) in repo.priorities:
                    message = pagure.lib.edit_issue(
                        SESSION,
                        issue=issue,
                        priority=new_priority,
                        private=issue.private,
                        user=flask.g.fas_user.username,
                        ticketfolder=APP.config['TICKETS_FOLDER'],
                    )
                    SESSION.commit()
                    if message:
                        flask.flash(message)

            # Update ticket this one depends on
            messages = pagure.lib.update_dependency_issue(
                SESSION, repo, issue, depends,
                username=flask.g.fas_user.username,
                ticketfolder=APP.config['TICKETS_FOLDER'],
            )
            if not is_js:
                for message in messages:
                    flask.flash(message)

            # Update ticket(s) depending on this one
            messages = pagure.lib.update_blocked_issue(
                SESSION, repo, issue, blocks,
                username=flask.g.fas_user.username,
                ticketfolder=APP.config['TICKETS_FOLDER'],
            )
            if not is_js:
                for message in messages:
                    flask.flash(message)

        except pagure.exceptions.PagureException as err:
            is_js = False
            SESSION.rollback()
            if not is_js:
                flask.flash(err.message, 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            is_js = False
            SESSION.rollback()
            APP.logger.exception(err)
            if not is_js:
                flask.flash(str(err), 'error')

    if is_js:
        return 'ok'
    else:
        return flask.redirect(flask.url_for(
            'view_issue', username=username, repo=repo.name, issueid=issueid))


@APP.route('/<repo:repo>/tag/<tag>/edit/', methods=('GET', 'POST'))
@APP.route('/<repo:repo>/tag/<tag>/edit', methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/tag/<tag>/edit/', methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/tag/<tag>/edit', methods=('GET', 'POST'))
@login_required
def edit_tag(repo, tag, username=None):
    """ Edit the specified tag associated with the issues of a project.
    """
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if not repo:
        flask.abort(404, 'Project not found')

    if not is_repo_admin(repo):
        flask.abort(
            403,
            'You are not allowed to edit tags associated with the issues of \
            this project')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    tags = pagure.lib.get_tags_of_project(SESSION, repo)

    if not tags or tag not in [t.tag for t in tags]:
        flask.abort(404, 'Tag %s not found in this project' % tag )

    form = pagure.forms.AddIssueTagForm()
    if form.validate_on_submit():
        new_tag = form.tag.data

        msgs = pagure.lib.edit_issue_tags(
            SESSION, repo, tag, new_tag,
            user=flask.g.fas_user.username,
            ticketfolder=APP.config['TICKETS_FOLDER']
        )

        try:
            SESSION.commit()
            for msg in msgs:
                flask.flash(msg)
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            LOG.error(err)
            flask.flash('Could not edit tag: %s' % tag, 'error')

        return flask.redirect(flask.url_for(
            '.view_settings', repo=repo.name, username=username))

    return flask.render_template(
        'edit_tag.html',
        form=form,
        username=username,
        repo=repo,
        edit_tag=tag,
    )


@APP.route('/<repo:repo>/droptag/', methods=['POST'])
@APP.route('/fork/<username>/<repo:repo>/droptag/', methods=['POST'])
@login_required
def remove_tag(repo, username=None):
    """ Remove the specified tag, associated with the issues, from the project.
    """
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if not repo:
        flask.abort(404, 'Project not found')

    if not is_repo_admin(repo):
        flask.abort(
            403,
            'You are not allowed to remove tags associated with the issues \
            of this project')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    form = pagure.forms.AddIssueTagForm()
    if form.validate_on_submit():
        tags = form.tag.data
        tags = [tag.strip() for tag in tags.split(',')]

        msgs = pagure.lib.remove_tags(
            SESSION, repo, tags,
            user=flask.g.fas_user.username,
            ticketfolder=APP.config['TICKETS_FOLDER']
        )

        try:
            SESSION.commit()
            for msg in msgs:
                flask.flash(msg)
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            LOG.error(err)
            flask.flash(
                'Could not remove tag: %s' % ','.join(tags), 'error')

    return flask.redirect(
        flask.url_for('.view_settings', repo=repo.name, username=username)
    )


@APP.route('/<repo:repo>/issues/')
@APP.route('/<repo:repo>/issues')
@APP.route('/fork/<username>/<repo:repo>/issues/')
@APP.route('/fork/<username>/<repo:repo>/issues')
def view_issues(repo, username=None):
    """ List all issues associated to a repo
    """
    status = flask.request.args.get('status', None)
    priority = flask.request.args.get('priority', None)
    tags = flask.request.args.getlist('tags')
    tags = [tag.strip() for tag in tags if tag.strip()]
    assignee = flask.request.args.get('assignee', None)
    author = flask.request.args.get('author', None)

    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    try:
        priority = int(priority)
    except:
        priority = None

    # Hide private tickets
    private = False
    # If user is authenticated, show him/her his/her private tickets
    if authenticated():
        private = flask.g.fas_user.username
    # If user is repo admin, show all tickets included the private ones
    if is_repo_admin(repo):
        private = None

    oth_issues = None
    if status is not None:
        if status.lower() == 'closed':
            issues = pagure.lib.search_issues(
                SESSION,
                repo,
                closed=True,
                tags=tags,
                assignee=assignee,
                author=author,
                private=private,
                priority=priority,
            )
            oth_issues = pagure.lib.search_issues(
                SESSION,
                repo,
                status='Open',
                tags=tags,
                assignee=assignee,
                author=author,
                private=private,
                priority=priority,
                count=True,
            )
        else:
            issues = pagure.lib.search_issues(
                SESSION,
                repo,
                status=status,
                tags=tags,
                assignee=assignee,
                author=author,
                private=private,
                priority=priority,
            )

    else:
        issues = pagure.lib.search_issues(
            SESSION, repo, status='Open', tags=tags, assignee=assignee,
            author=author, private=private, priority=priority)
        oth_issues = pagure.lib.search_issues(
            SESSION, repo, closed=True, tags=tags, assignee=assignee,
            author=author, private=private, priority=priority, count=True)

    tag_list = pagure.lib.get_tags_of_project(SESSION, repo)

    reponame = pagure.get_repo_path(repo)
    repo_obj = pygit2.Repository(reponame)

    return flask.render_template(
        'issues.html',
        select='issues',
        repo=repo,
        username=username,
        tag_list=tag_list,
        status=status,
        issues=issues,
        oth_issues=oth_issues,
        tags=tags,
        assignee=assignee,
        author=author,
        priority=priority,
        repo_admin=is_repo_admin(repo),
        repo_obj=repo_obj,
    )


@APP.route('/<repo:repo>/roadmap/')
@APP.route('/<repo:repo>/roadmap')
@APP.route('/fork/<username>/<repo:repo>/roadmap/')
@APP.route('/fork/<username>/<repo:repo>/roadmap')
def view_roadmap(repo, username=None):
    """ List all issues associated to a repo as roadmap
    """
    status = flask.request.args.get('status', 'Open')
    if status.lower() == 'all':
        status = None
    milestone = flask.request.args.getlist('milestone', None)

    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    # Hide private tickets
    private = False
    # If user is authenticated, show him/her his/her private tickets
    if authenticated():
        private = flask.g.fas_user.username
    # If user is repo admin, show all tickets included the private ones
    if is_repo_admin(repo):
        private = None

    milestones = milestone or list(repo.milestones.keys())
    tags = ['roadmap'] + milestones

    issues = pagure.lib.search_issues(
        SESSION,
        repo,
        tags=tags,
        private=private,
    )

    # Change from a list of issues to a dict of milestone/issues
    milestone_issues = defaultdict(list)
    for cnt in range(len(issues)):
        saved = False
        for mlstone in sorted(milestones):
            if mlstone in issues[cnt].tags_text:
                milestone_issues[mlstone].append(issues[cnt])
                saved = True
                break
        if saved:
            continue
        if not milestone:
            milestone_issues['unplanned'].append(issues[cnt])

    if status:
        for key in milestone_issues.keys():
            active = False
            for issue in milestone_issues[key]:
                if issue.status == 'Open':
                    active = True
                    break
            if not active:
                del(milestone_issues[key])

    if milestone:
        for mlstone in milestone:
            if mlstone not in milestone_issues:
                milestone_issues[mlstone] = []

    tag_list = pagure.lib.get_tags_of_project(SESSION, repo)

    reponame = pagure.get_repo_path(repo)
    repo_obj = pygit2.Repository(reponame)
    milestones_ordered = sorted(list(milestone_issues.keys()))
    if 'unplanned' in milestones_ordered:
        index = milestones_ordered.index('unplanned')
        cnt = len(milestones_ordered)
        milestones_ordered.insert(cnt, milestones_ordered.pop(index))

    return flask.render_template(
        'roadmap.html',
        select='issues',
        repo=repo,
        username=username,
        tag_list=tag_list,
        status=status,
        milestones=milestones_ordered,
        issues=milestone_issues,
        tags=milestone,
        repo_admin=is_repo_admin(repo),
        repo_obj=repo_obj,
    )



@APP.route('/<repo:repo>/new_issue/', methods=('GET', 'POST'))
@APP.route('/<repo:repo>/new_issue', methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/new_issue/', methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/new_issue', methods=('GET', 'POST'))
@login_required
def new_issue(repo, username=None):
    """ Create a new issue
    """
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    form = pagure.forms.IssueFormSimplied()
    if form.validate_on_submit():
        title = form.title.data
        content = form.issue_content.data
        private = form.private.data

        try:
            issue = pagure.lib.new_issue(
                SESSION,
                repo=repo,
                title=title,
                content=content,
                private=private or False,
                user=flask.g.fas_user.username,
                ticketfolder=APP.config['TICKETS_FOLDER'],
            )
            SESSION.commit()
            # If there is a file attached, attach it.
            filestream = flask.request.files.get('filestream')
            if filestream and '<!!image>' in issue.content:
                new_filename = pagure.lib.git.add_file_to_git(
                    repo=repo,
                    issue=issue,
                    ticketfolder=APP.config['TICKETS_FOLDER'],
                    user=flask.g.fas_user,
                    filename=filestream.filename,
                    filestream=filestream.stream,
                )
                # Replace the <!!image> tag in the comment with the link
                # to the actual image
                filelocation = flask.url_for(
                    'view_issue_raw_file',
                    repo=repo.name,
                    username=username,
                    filename=new_filename,
                )
                new_filename = new_filename.split('-', 1)[1]
                url = '[![%s](%s)](%s)' % (
                    new_filename, filelocation, filelocation)
                issue.content = issue.content.replace('<!!image>', url)
                SESSION.add(issue)
                SESSION.commit()

            return flask.redirect(flask.url_for(
                '.view_issue', username=username, repo=repo.name,
                issueid=issue.id))
        except pagure.exceptions.PagureException as err:
            flask.flash(str(err), 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            flask.flash(str(err), 'error')

    types = None
    default = None
    ticketrepopath = os.path.join(APP.config['TICKETS_FOLDER'], repo.path)
    if os.path.exists(ticketrepopath):
        ticketrepo = pygit2.Repository(ticketrepopath)
        if not ticketrepo.is_empty and not ticketrepo.head_is_unborn:
            commit = ticketrepo[ticketrepo.head.target]
            # Get the different ticket types
            files = __get_file_in_tree(
                ticketrepo, commit.tree, ['templates'],
                bail_on_tree=True)
            if files:
                types = [f.name.rstrip('.md') for f in files]
            # Get the default template
            default_file = __get_file_in_tree(
                ticketrepo, commit.tree, ['templates', 'default.md'],
                bail_on_tree=True)
            if default_file:
                default, _ = pagure.doc_utils.convert_readme(
                        default_file.data, 'md')

    return flask.render_template(
        'new_issue.html',
        select='issues',
        form=form,
        repo=repo,
        username=username,
        repo_admin=is_repo_admin(repo),
        types=types,
        default=default,
    )


@APP.route('/<repo:repo>/issue/<int:issueid>/')
@APP.route('/<repo:repo>/issue/<int:issueid>')
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/')
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>')
def view_issue(repo, issueid, username=None):
    """ List all issues associated to a repo
    """

    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    issue = pagure.lib.search_issues(SESSION, repo, issueid=issueid)

    if issue is None or issue.project != repo:
        flask.abort(404, 'Issue not found')

    if issue.private and not is_repo_admin(repo) \
            and (not authenticated() or
                 not issue.user.user == flask.g.fas_user.username):
        flask.abort(
            403, 'This issue is private and you are not allowed to view it')

    reponame = pagure.get_repo_path(repo)
    repo_obj = pygit2.Repository(reponame)

    status = pagure.lib.get_issue_statuses(SESSION)

    form = pagure.forms.UpdateIssueForm(
        status=status, priorities=repo.priorities)
    form.status.data = issue.status
    form.priority.data = str(issue.priority)
    tag_list = pagure.lib.get_tags_of_project(SESSION, repo)
    return flask.render_template(
        'issue.html',
        select='issues',
        repo=repo,
        username=username,
        repo_obj=repo_obj,
        tag_list=tag_list,
        issue=issue,
        issueid=issueid,
        form=form,
        repo_admin=is_repo_admin(repo),
    )


@APP.route('/<repo:repo>/issue/<int:issueid>/drop', methods=['POST'])
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/drop',
           methods=['POST'])
def delete_issue(repo, issueid, username=None):
    """ Delete the specified issue
    """

    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    issue = pagure.lib.search_issues(SESSION, repo, issueid=issueid)

    if issue is None or issue.project != repo:
        flask.abort(404, 'Issue not found')

    if not is_repo_admin(repo):
        flask.abort(
            403,
            'You are not allowed to remove tickets of this project')

    form = pagure.forms.ConfirmationForm()
    if form.validate_on_submit():
        try:
            pagure.lib.drop_issue(
                SESSION, issue,
                user=flask.g.fas_user.username,
                ticketfolder=APP.config['TICKETS_FOLDER'],
            )
            SESSION.commit()
            flask.flash('Issue deleted')
            return flask.redirect(flask.url_for(
                'view_issues', username=username, repo=repo.name))
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            APP.logger.exception(err)
            flask.flash('Could not delete the issue', 'error')

    return flask.redirect(flask.url_for(
        'view_issue', username=username, repo=repo.name, issueid=issueid))


@APP.route('/<repo:repo>/issue/<int:issueid>/edit/', methods=('GET', 'POST'))
@APP.route('/<repo:repo>/issue/<int:issueid>/edit', methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/edit/',
           methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/edit',
           methods=('GET', 'POST'))
@login_required
def edit_issue(repo, issueid, username=None):
    """ Edit the specified issue
    """
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    issue = pagure.lib.search_issues(SESSION, repo, issueid=issueid)

    if issue is None or issue.project != repo:
        flask.abort(404, 'Issue not found')

    if not (is_repo_admin(repo)
            or flask.g.fas_user.username == issue.user.username):
        flask.abort(
            403, 'You are not allowed to edit issues for this project')

    status = pagure.lib.get_issue_statuses(SESSION)
    form = pagure.forms.IssueForm(status=status)
    if form.validate_on_submit():
        title = form.title.data
        content = form.issue_content.data
        status = form.status.data
        private = form.private.data

        try:
            message = pagure.lib.edit_issue(
                SESSION,
                issue=issue,
                title=title,
                content=content,
                status=status,
                user=flask.g.fas_user.username,
                ticketfolder=APP.config['TICKETS_FOLDER'],
                private=private,
            )
            SESSION.commit()

            # If there is a file attached, attach it.
            filestream = flask.request.files.get('filestream')
            if filestream and '<!!image>' in issue.content:
                new_filename = pagure.lib.git.add_file_to_git(
                    repo=repo,
                    issue=issue,
                    ticketfolder=APP.config['TICKETS_FOLDER'],
                    user=flask.g.fas_user,
                    filename=filestream.filename,
                    filestream=filestream.stream,
                )
                # Replace the <!!image> tag in the comment with the link
                # to the actual image
                filelocation = flask.url_for(
                    'view_issue_raw_file',
                    repo=repo.name,
                    username=username,
                    filename=new_filename,
                )
                new_filename = new_filename.split('-', 1)[1]
                url = '[![%s](%s)](%s)' % (
                    new_filename, filelocation, filelocation)
                issue.content = issue.content.replace('<!!image>', url)
                SESSION.add(issue)
                SESSION.commit()
            flask.flash(message)
            url = flask.url_for(
                'view_issue', username=username,
                repo=repo.name, issueid=issueid)
            return flask.redirect(url)
        except pagure.exceptions.PagureException as err:
            flask.flash(str(err), 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            SESSION.rollback()
            flask.flash(str(err), 'error')
    elif flask.request.method == 'GET':
        form.title.data = issue.title
        form.issue_content.data = issue.content
        form.status.data = issue.status
        form.private.data = issue.private

    return flask.render_template(
        'new_issue.html',
        select='issues',
        type='edit',
        form=form,
        repo=repo,
        username=username,
        issue=issue,
        issueid=issueid,
        repo_admin=is_repo_admin(repo),
    )


@APP.route('/<repo:repo>/issue/<int:issueid>/upload', methods=['POST'])
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/upload',
           methods=['POST'])
@login_required
def upload_issue(repo, issueid, username=None):
    ''' Upload a file to a ticket.
    '''
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    issue = pagure.lib.search_issues(SESSION, repo, issueid=issueid)

    if issue is None or issue.project != repo:
        flask.abort(404, 'Issue not found')

    form = pagure.forms.UploadFileForm()
    # pylint: disable=E1101
    if form.validate_on_submit():
        filestream = flask.request.files['filestream']
        new_filename = pagure.lib.git.add_file_to_git(
            repo=repo,
            issue=issue,
            ticketfolder=APP.config['TICKETS_FOLDER'],
            user=flask.g.fas_user,
            filename=filestream.filename,
            filestream=filestream.stream,
        )
        return flask.jsonify({
            'output': 'ok',
            'filename': new_filename.split('-', 1)[1],
            'filelocation': flask.url_for(
                'view_issue_raw_file',
                repo=repo.name,
                username=username,
                filename=new_filename,
            )
        })
    else:
        return flask.jsonify({'output': 'notok'})


@APP.route('/<repo:repo>/issue/raw/<path:filename>')
@APP.route('/fork/<username>/<repo:repo>/issue/raw/<path:filename>')
def view_issue_raw_file(repo, filename=None, username=None):
    """ Displays the raw content of a file of a commit for the specified
    ticket repo.
    """
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if not repo:
        flask.abort(404, 'Project not found')

    if not repo.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    reponame = os.path.join(APP.config['TICKETS_FOLDER'], repo.path)

    repo_obj = pygit2.Repository(reponame)

    if repo_obj.is_empty:
        flask.abort(404, 'Empty repo cannot have a file')

    branch = repo_obj.lookup_branch('master')
    commit = branch.get_object()

    mimetype = None
    encoding = None

    content = __get_file_in_tree(
        repo_obj, commit.tree, filename.split('/'), bail_on_tree=True)
    if not content or isinstance(content, pygit2.Tree):
        flask.abort(404, 'File not found')

    mimetype, encoding = mimetypes.guess_type(filename)
    data = repo_obj[content.oid].data

    if not data:
        flask.abort(404, 'No content found')

    if not mimetype and data[:2] == '#!':
        mimetype = 'text/plain'

    if not mimetype:
        if '\0' in data:
            mimetype = 'application/octet-stream'
        else:
            mimetype = 'text/plain'

    if mimetype.startswith('text/') and not encoding:
        encoding = chardet.detect(ktc.to_bytes(data))['encoding']

    headers = {'Content-Type': mimetype}
    if encoding:
        headers['Content-Encoding'] = encoding

    return (data, 200, headers)


@APP.route('/<repo:repo>/issue/<int:issueid>/comment/<int:commentid>/edit',
           methods=('GET', 'POST'))
@APP.route('/fork/<username>/<repo:repo>/issue/<int:issueid>/comment'
           '/<int:commentid>/edit', methods=('GET', 'POST'))
@login_required
def edit_comment_issue(repo, issueid, commentid, username=None):
    """Edit comment of an issue
    """
    is_js = flask.request.args.get('js', False)

    project = pagure.lib.get_project(SESSION, repo, user=username)

    if not project:
        flask.abort(404, 'Project not found')

    if not project.settings.get('issue_tracker', True):
        flask.abort(404, 'No issue tracker found for this project')

    issue = pagure.lib.search_issues(SESSION, project, issueid=issueid)

    if issue is None or issue.project != project:
        flask.abort(404, 'Issue not found')

    comment = pagure.lib.get_issue_comment(
        SESSION, issue.uid, commentid)

    if comment is None or comment.parent.project != project:
        flask.abort(404, 'Comment not found')

    if (flask.g.fas_user.username != comment.user.username
            or comment.parent.status != 'Open') \
            and not is_repo_admin(project):
        flask.abort(403, 'You are not allowed to edit this comment')

    form = pagure.forms.EditCommentForm()

    if form.validate_on_submit():

        updated_comment = form.update_comment.data
        try:
            message = pagure.lib.edit_comment(
                SESSION,
                parent=issue,
                comment=comment,
                user=flask.g.fas_user.username,
                updated_comment=updated_comment,
                folder=APP.config['TICKETS_FOLDER'],
            )
            SESSION.commit()
            if not is_js:
                flask.flash(message)
        except SQLAlchemyError, err:  # pragma: no cover
            SESSION.rollback()
            LOG.error(err)
            if is_js:
                return 'error'
            flask.flash(
                'Could not edit the comment: %s' % commentid, 'error')

        if is_js:
            return 'ok'

        return flask.redirect(flask.url_for(
            'view_issue', username=username,
            repo=project.name, issueid=issueid))

    if is_js and flask.request.method == 'POST':
        return 'failed'

    return flask.render_template(
        'comment_update.html',
        select='issues',
        requestid=issueid,
        repo=project,
        username=username,
        form=form,
        comment=comment,
        is_js=is_js,
        repo_admin=is_repo_admin(project),
    )
