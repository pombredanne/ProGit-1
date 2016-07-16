# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

Internal endpoints.

"""

import shutil
import tempfile
import os

import flask
import pygit2

from functools import wraps
from sqlalchemy.exc import SQLAlchemyError

PV = flask.Blueprint('internal_ns', __name__, url_prefix='/pv')

import pagure
import pagure.forms
import pagure.lib
import pagure.lib.git
import pagure.ui.fork
from pagure import is_repo_admin, authenticated


MERGE_OPTIONS = {
    'NO_CHANGE': {
        'short_code': 'No changes',
        'message': 'Nothing to change, git is up to date'
    },
    'FFORWARD': {
        'short_code': 'Ok',
        'message': 'The pull-request can be merged and fast-forwarded'
    },
    'CONFLICTS': {
        'short_code': 'Conflicts',
        'message': 'The pull-request cannot be merged due to conflicts'
    },
    'MERGE': {
        'short_code': 'With merge',
        'message': 'The pull-request can be merged with a merge commit'
    }
}

# pylint: disable=E1101


def localonly(function):
    ''' Decorator used to check if the request is local or not.
    '''
    @wraps(function)
    def decorated_function(*args, **kwargs):
        ''' Wrapped function actually checking if the request is local.
        '''
        ip_allowed = pagure.APP.config.get(
            'IP_ALLOWED_INTERNAL', ['127.0.0.1', 'localhost', '::1'])
        if flask.request.remote_addr not in ip_allowed:
            flask.abort(403)
        else:
            return function(*args, **kwargs)
    return decorated_function


@PV.route('/pull-request/comment/', methods=['PUT'])
@localonly
def pull_request_add_comment():
    """ Add a comment to a pull-request.
    """
    pform = pagure.forms.ProjectCommentForm(csrf_enabled=False)
    if not pform.validate_on_submit():
        flask.abort(400, 'Invalid request')

    objid = pform.objid.data
    useremail = pform.useremail.data

    request = pagure.lib.get_request_by_uid(
        pagure.SESSION,
        request_uid=objid,
    )

    if not request:
        flask.abort(404, 'Pull-request not found')

    form = pagure.forms.AddPullRequestCommentForm(csrf_enabled=False)

    if not form.validate_on_submit():
        flask.abort(400, 'Invalid request')

    commit = form.commit.data or None
    tree_id = form.tree_id.data or None
    filename = form.filename.data or None
    row = form.row.data or None
    comment = form.comment.data

    try:
        message = pagure.lib.add_pull_request_comment(
            pagure.SESSION,
            request=request,
            commit=commit,
            tree_id=tree_id,
            filename=filename,
            row=row,
            comment=comment,
            user=useremail,
            requestfolder=pagure.APP.config['REQUESTS_FOLDER'],
        )
        pagure.SESSION.commit()
    except SQLAlchemyError as err:  # pragma: no cover
        pagure.SESSION.rollback()
        pagure.APP.logger.exception(err)
        flask.abort(500, 'Error when saving the request to the database')

    return flask.jsonify({'message': message})


@PV.route('/ticket/comment/', methods=['PUT'])
@localonly
def ticket_add_comment():
    """ Add a comment to a pull-request.
    """
    pform = pagure.forms.ProjectCommentForm(csrf_enabled=False)
    if not pform.validate_on_submit():
        flask.abort(400, 'Invalid request')

    objid = pform.objid.data
    useremail = pform.useremail.data

    issue = pagure.lib.get_issue_by_uid(
        pagure.SESSION,
        issue_uid=objid
    )

    if issue is None:
        flask.abort(404, 'Issue not found')

    user_obj = pagure.lib.search_user(pagure.SESSION, email=useremail)
    admin = False
    if user_obj:
        admin = user_obj == issue.project.user.user or (
            user_obj in [user.user for user in issue.project.users])

    if issue.private and user_obj and not admin \
            and not issue.user.user == user_obj.username:
        flask.abort(
            403, 'This issue is private and you are not allowed to view it')

    form = pagure.forms.CommentForm(csrf_enabled=False)

    if not form.validate_on_submit():
        flask.abort(400, 'Invalid request')

    comment = form.comment.data

    try:
        message = pagure.lib.add_issue_comment(
            pagure.SESSION,
            issue=issue,
            comment=comment,
            user=useremail,
            ticketfolder=pagure.APP.config['TICKETS_FOLDER'],
            notify=True)
        pagure.SESSION.commit()
    except SQLAlchemyError as err:  # pragma: no cover
        pagure.SESSION.rollback()
        pagure.APP.logger.exception(err)
        flask.abort(500, 'Error when saving the request to the database')

    return flask.jsonify({'message': message})


@PV.route('/pull-request/merge', methods=['POST'])
def mergeable_request_pull():
    """ Returns if the specified pull-request can be merged or not.
    """
    force = flask.request.form.get('force', False)
    if force is not False:
        force = True

    form = pagure.forms.ConfirmationForm()
    if not form.validate_on_submit():
        response = flask.jsonify({
            'code': 'CONFLICTS',
            'message': 'Invalid input submitted',
        })
        response.status_code = 400
        return response

    requestid = flask.request.form.get('requestid')

    request = pagure.lib.get_request_by_uid(
        pagure.SESSION, request_uid=requestid)

    if not request:
        response = flask.jsonify({
            'code': 'CONFLICTS',
            'message': 'Pull-request not found',
        })
        response.status_code = 404
        return response

    if request.merge_status and not force:
        return flask.jsonify({
            'code': request.merge_status,
            'short_code': MERGE_OPTIONS[request.merge_status]['short_code'],
            'message': MERGE_OPTIONS[request.merge_status]['message']})

    try:
        merge_status = pagure.lib.git.merge_pull_request(
            session=pagure.SESSION,
            request=request,
            username=None,
            request_folder=None,
            domerge=False)
    except pygit2.GitError as err:
        response = flask.jsonify({
            'code': 'CONFLICTS', 'message': err.message})
        response.status_code = 409
        return response
    except pagure.exceptions.PagureException as err:
        response = flask.jsonify({
            'code': 'CONFLICTS', 'message': err.message})
        response.status_code = 500
        return response

    return flask.jsonify({
        'code': merge_status,
        'short_code': MERGE_OPTIONS[merge_status]['short_code'],
        'message': MERGE_OPTIONS[merge_status]['message']})


@PV.route('/pull-request/ready', methods=['POST'])
def get_pull_request_ready_branch():
    """ Return the list of branches that have commits not in the main
    branch/repo (thus for which one could open a PR) and the number of
    commits that differ.
    """
    form = pagure.forms.ConfirmationForm()
    if not form.validate_on_submit():
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'Invalid input submitted',
        })
        response.status_code = 400
        return response

    repo = pagure.lib.get_project(
        pagure.SESSION,
        flask.request.form.get('repo', '').strip() or None,
        user=flask.request.form.get('repouser', '').strip() or None)

    if not repo:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No repo found with the information provided',
        })
        response.status_code = 404
        return response

    reponame = pagure.get_repo_path(repo)
    repo_obj = pygit2.Repository(reponame)

    branches = {}

    for branchname in repo_obj.listall_branches():
        branch = repo_obj.lookup_branch(branchname)

        diff_commits = []
        if repo.is_fork:
            parentpath = os.path.join(
                pagure.APP.config['GIT_FOLDER'], repo.parent.path)
            if repo.parent.is_fork:
                parentpath = os.path.join(
                    pagure.APP.config['FORK_FOLDER'], repo.parent.path)
        else:
            parentpath = os.path.join(
                pagure.APP.config['GIT_FOLDER'], repo.path)

        orig_repo = pygit2.Repository(parentpath)

        if not repo_obj.is_empty and not orig_repo.is_empty \
                and repo_obj.listall_branches() > 1:

            if not orig_repo.head_is_unborn:
                compare_branch = orig_repo.lookup_branch(
                    orig_repo.head.shorthand)
            else:
                compare_branch = None

            compare_commits = []

            if compare_branch:
                compare_commits = [
                    commit.oid.hex
                    for commit in orig_repo.walk(
                        compare_branch.get_object().hex,
                        pygit2.GIT_SORT_TIME)
                ]

            repo_commit = repo_obj[branch.get_object().hex]

            for commit in repo_obj.walk(
                    repo_commit.oid.hex, pygit2.GIT_SORT_TIME):
                if commit.oid.hex in compare_commits:
                    break
                diff_commits.append(commit.oid.hex)

        if diff_commits:
            branches[branchname] = diff_commits

    prs = pagure.lib.search_pull_requests(
        pagure.SESSION,
        project_id=repo.id,
        status='Open'
    )
    for pr in prs:
        if pr.branch_from in branches:
            del(branches[pr.branch_from])

    return flask.jsonify(
        {
            'code': 'OK',
            'message': branches,
        }
    )


@PV.route('/<repo>/issue/template', methods=['POST'])
@PV.route('/fork/<username>/<repo>/issue/template',
           methods=['POST'])
def get_ticket_template(repo, username=None):
    """ Return the template asked for the specified project
    """

    form = pagure.forms.ConfirmationForm()
    if not form.validate_on_submit():
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'Invalid input submitted',
        })
        response.status_code = 400
        return response

    template = flask.request.args.get('template', None)
    if not template:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No template provided',
        })
        response.status_code = 400
        return response

    repo = pagure.lib.get_project(pagure.SESSION, repo, user=username)

    if repo is None:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'Project not found',
        })
        response.status_code = 404
        return response

    if not repo.settings.get('issue_tracker', True):
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No issue tracker found for this project',
        })
        response.status_code = 404
        return response

    ticketrepopath = os.path.join(
        pagure.APP.config['TICKETS_FOLDER'], repo.path)
    content = None
    if os.path.exists(ticketrepopath):
        ticketrepo = pygit2.Repository(ticketrepopath)
        if not ticketrepo.is_empty and not ticketrepo.head_is_unborn:
            commit = ticketrepo[ticketrepo.head.target]
            # Get the asked template
            content_file = pagure.__get_file_in_tree(
                ticketrepo, commit.tree, ['templates', '%s.md' % template],
                bail_on_tree=True)
            if content_file:
                content, _ = pagure.doc_utils.convert_readme(
                        content_file.data, 'md')
    if content:
        response = flask.jsonify({
            'code': 'OK',
            'message': content,
        })
    else:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No such template found',
        })
        response.status_code = 404
    return response


@PV.route('/branches/commit/', methods=['POST'])
@localonly
def get_branches_of_commit():
    """ Return the list of branches that have the specified commit in
    """
    form = pagure.forms.ConfirmationForm()
    if not form.validate_on_submit():
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'Invalid input submitted',
        })
        response.status_code = 400
        return response

    commit_id = flask.request.form.get('commit_id', '').strip() or None
    if not commit_id:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No commit id submitted',
        })
        response.status_code = 400
        return response

    repo = pagure.lib.get_project(
        pagure.SESSION,
        flask.request.form.get('repo', '').strip() or None,
        user=flask.request.form.get('repouser', '').strip() or None)

    if not repo:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No repo found with the information provided',
        })
        response.status_code = 404
        return response

    repopath = os.path.join(pagure.APP.config['GIT_FOLDER'], repo.path)

    if not os.path.exists(repopath):
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'No git repo found with the information provided',
        })
        response.status_code = 404
        return response

    repo_obj = pygit2.Repository(repopath)

    try:
        commit_id in repo_obj
    except:
        response = flask.jsonify({
            'code': 'ERROR',
            'message': 'This commit could not be found in this repo',
        })
        response.status_code = 404
        return response

    branches = []
    if not repo_obj.head_is_unborn:
        compare_branch = repo_obj.lookup_branch(
            repo_obj.head.shorthand)
    else:
        compare_branch = None

    for branchname in repo_obj.listall_branches():
        branch = repo_obj.lookup_branch(branchname)

        if not repo_obj.is_empty and len(repo_obj.listall_branches()) > 1:

            merge_commit = None

            if compare_branch:
                merge_commit = repo_obj.merge_base(
                    compare_branch.get_object().hex,
                    branch.get_object().hex
                ).hex

            repo_commit = repo_obj[branch.get_object().hex]

            for commit in repo_obj.walk(
                    repo_commit.oid.hex, pygit2.GIT_SORT_TIME):
                if commit.oid.hex == merge_commit:
                    break
                if commit.oid.hex == commit_id:
                    branches.append(branchname)
                    break

    # If we didn't find the commit in any branch and there is one, then it
    # is in the default branch.
    if not branches and compare_branch:
        branches.append(compare_branch.branch_name)

    return flask.jsonify(
        {
            'code': 'OK',
            'branches': branches,
        }
    )
