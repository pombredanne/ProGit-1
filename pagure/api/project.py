# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import flask

from sqlalchemy.exc import SQLAlchemyError

import pagure
import pagure.exceptions
import pagure.lib
from pagure import SESSION, APP
from pagure.api import API, api_method, APIERROR, api_login_required


@API.route('/<repo>/git/tags')
@API.route('/fork/<username>/<repo>/git/tags')
@api_method
def api_git_tags(repo, username=None):
    """
    Project git tags
    ----------------
    List the tags made on the project Git repository.

    ::

        GET /api/0/<repo>/git/tags

    ::

        GET /api/0/fork/<username>/<repo>/git/tags

    Sample response
    ^^^^^^^^^^^^^^^

    ::

        {
          "total_tags": 2,
          "tags": ["0.0.1", "0.0.2"]
        }

    """
    repo = pagure.lib.get_project(SESSION, repo, user=username)

    if repo is None:
        raise pagure.exceptions.APIError(404, error_code=APIERROR.ENOPROJECT)

    tags = pagure.lib.git.get_git_tags(repo)

    jsonout = flask.jsonify({
        'total_tags': len(tags),
        'tags': tags
    })
    return jsonout


@API.route('/projects')
@api_method
def api_projects():
    """
    List projects
    --------------
    Search projects given the specified criterias.

    ::

        GET /api/0/projects

    ::

        GET /api/0/projects?tags=fedora-infra

    Parameters
    ^^^^^^^^^^

    +---------------+----------+---------------+--------------------------+
    | Key           | Type     | Optionality   | Description              |
    +===============+==========+===============+==========================+
    | ``tags``      | string   | Optional      | | Filters the projects   |
    |               |          |               |   returned by their tags |
    +---------------+----------+---------------+--------------------------+
    | ``pattern``   | string   | Optional      | | Filters the projects   |
    |               |          |               |   by the pattern string  |
    +---------------+----------+---------------+--------------------------+
    | ``username``  | string   | Optional      | | Filters the projects   |
    |               |          |               |   returned by the users  |
    |               |          |               |   having commit rights   |
    |               |          |               |   to it                  |
    +---------------+----------+---------------+--------------------------+
    | ``fork``      | boolean  | Optional      | | Filters the projects   |
    |               |          |               |   returned depending if  |
    |               |          |               |   they are forks or not  |
    +---------------+----------+---------------+--------------------------+

    Sample response
    ^^^^^^^^^^^^^^^

    ::

        {
          "total_projects": 2,
          "projects": [
            {
              "date_created": "1427441537",
              "description": "A web-based calendar for Fedora",
              "id": 7,
              "name": "fedocal",
              "parent": null,
              "user": {
                "fullname": "Pierre-Yves C",
                "name": "pingou"
              }
            },
            {
              "date_created": "1431666007",
              "description": "An awesome messaging servicefor everyone",
              "id": 12,
              "name": "fedmsg",
              "parent": {
                "date_created": "1433423298",
                "description": "An awesome messaging servicefor everyone",
                "id": 11,
                "name": "fedmsg",
                "parent": null,
                "user": {
                  "fullname": "Ralph B",
                  "name": "ralph"
                }
              },
              "user": {
                "fullname": "Pierre-Yves C",
                "name": "pingou"
              }
            }
          ]
        }

    """
    tags = flask.request.values.getlist('tags')
    username = flask.request.values.get('username', None)
    fork = flask.request.values.get('fork', None)
    pattern = flask.request.values.get('pattern', None)

    if str(fork).lower() in ['1', 'true']:
        fork = True
    elif str(fork).lower() in ['0', 'false']:
        fork = False

    projects = pagure.lib.search_projects(
        SESSION, username=username, fork=fork, tags=tags, pattern=pattern)

    if not projects:
        raise pagure.exceptions.APIError(
            404, error_code=APIERROR.ENOPROJECTS)

    jsonout = flask.jsonify({
        'total_projects': len(projects),
        'projects': [p.to_json(api=True, public=True) for p in projects]
    })
    return jsonout


@API.route('/new/', methods=['POST'])
@API.route('/new', methods=['POST'])
@api_login_required(acls=['create_project'])
@api_method
def api_new_project():
    """
    Create a new project
    --------------------
    Create a new project on this pagure instance.

    ::

        POST /api/0/<repo>/new


    Input
    ^^^^^

    +------------------+---------+--------------+---------------------------+
    | Key              | Type    | Optionality  | Description               |
    +==================+=========+==============+===========================+
    | ``name``         | string  | Mandatory    | | The name of the new     |
    |                  |         |              |   project.                |
    +------------------+---------+--------------+---------------------------+
    | ``description``  | string  | Mandatory    | | A short description of  |
    |                  |         |              |   the new project.        |
    +------------------+---------+--------------+---------------------------+
    | ``url``          | string  | Optional     | | An url providing more   |
    |                  |         |              |   information about the   |
    |                  |         |              |   project.                |
    +------------------+---------+--------------+---------------------------+
    | ``avatar_email`` | string  | Optional     | | An email address for the|
    |                  |         |              |   avatar of the project.  |
    +------------------+---------+--------------+---------------------------+
    | ``create_readme``| boolean | Optional     | | A boolean to specify if |
    |                  |         |              |   there should be a readme|
    |                  |         |              |   added to the project on |
    |                  |         |              |   creation.               |
    +------------------+---------+--------------+---------------------------+

    Sample response
    ^^^^^^^^^^^^^^^

    ::

        {
          'message': 'Project "foo" created'
        }

    """
    user = pagure.lib.search_user(SESSION, username=flask.g.fas_user.username)
    output = {}

    if not pagure.APP.config.get('ENABLE_NEW_PROJECTS', True):
        raise pagure.exceptions.APIError(
            404, error_code=APIERROR.ENEWPROJECTDISABLED)

    form = pagure.forms.ProjectForm(csrf_enabled=False)
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
            output['message'] = message
        except pagure.exceptions.PagureException as err:
            raise pagure.exceptions.APIError(
                400, error_code=APIERROR.ENOCODE, error=str(err))
        except SQLAlchemyError as err:  # pragma: no cover
            APP.logger.exception(err)
            SESSION.rollback()
            raise pagure.exceptions.APIError(400, error_code=APIERROR.EDBERROR)
    else:
        raise pagure.exceptions.APIError(400, error_code=APIERROR.EINVALIDREQ)

    jsonout = flask.jsonify(output)
    return jsonout


@API.route('/fork/', methods=['POST'])
@API.route('/fork', methods=['POST'])
@api_login_required(acls=['fork_project'])
@api_method
def api_fork_project():
    """
    Fork a project
    --------------------
    Fork a project on this pagure instance.

    ::

        POST /api/0/<repo>/fork


    Input
    ^^^^^

    +------------------+---------+--------------+---------------------------+
    | Key              | Type    | Optionality  | Description               |
    +==================+=========+==============+===========================+
    | ``repo``         | string  | Mandatory    | | The name of the project |
    |                  |         |              |   to fork.                |
    +------------------+---------+--------------+---------------------------+
    | ``username``     | string  | Optional     | | The username of the user|
    |                  |         |              |   of the fork.            |
    +------------------+---------+--------------+---------------------------+


    Sample response
    ^^^^^^^^^^^^^^^

    ::

        {
          "message": 'Repo "test" cloned to "pingou/test"'
        }

    """
    output = {}

    form = pagure.forms.ForkRepoForm(csrf_enabled=False)
    if form.validate_on_submit():
        repo = form.repo.data
        username = form.username.data or None

        repo = pagure.lib.get_project(SESSION, repo, user=username)
        if repo is None:
            raise pagure.exceptions.APIError(
                404, error_code=APIERROR.ENOPROJECT)

        try:
            message = pagure.lib.fork_project(
                SESSION,
                user=flask.g.fas_user.username,
                repo=repo,
                gitfolder=APP.config['GIT_FOLDER'],
                docfolder=APP.config['DOCS_FOLDER'],
                ticketfolder=APP.config['TICKETS_FOLDER'],
                requestfolder=APP.config['REQUESTS_FOLDER'],
            )
            SESSION.commit()
            pagure.lib.git.generate_gitolite_acls()
            output['message'] = message
        except pagure.exceptions.PagureException as err:
            raise pagure.exceptions.APIError(
                400, error_code=APIERROR.ENOCODE, error=str(err))
        except SQLAlchemyError as err:  # pragma: no cover
            APP.logger.exception(err)
            SESSION.rollback()
            raise pagure.exceptions.APIError(
                400, error_code=APIERROR.EDBERROR)
    else:
        raise pagure.exceptions.APIError(
            400, error_code=APIERROR.EINVALIDREQ)

    jsonout = flask.jsonify(output)
    return jsonout
