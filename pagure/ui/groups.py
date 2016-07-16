# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import flask

from sqlalchemy.exc import SQLAlchemyError

import pagure
import pagure.forms
import pagure.lib
import pagure.lib.git


# pylint: disable=E1101

@pagure.APP.route('/groups/')
@pagure.APP.route('/groups')
def group_lists():
    ''' List all the groups associated with all the projects. '''
    if not pagure.APP.config.get('ENABLE_USER_MNGT', True):
        flask.abort(404)

    group_type = 'user'
    if pagure.is_admin():
        group_type = None
    groups = pagure.lib.search_groups(pagure.SESSION, group_type=group_type)

    group_types = ['user']
    if pagure.is_admin():
        group_types = [
            grp.group_type
            for grp in pagure.lib.get_group_types(pagure.SESSION)
        ]
        # Make sure the admin type is always the last one
        group_types.remove('admin')
        group_types.append('admin')

    form = pagure.forms.NewGroupForm(group_types=group_types)

    return flask.render_template(
        'group_list.html',
        groups=groups,
        form=form,
    )


@pagure.APP.route('/group/<group>/', methods=['GET', 'POST'])
@pagure.APP.route('/group/<group>', methods=['GET', 'POST'])
def view_group(group):
    ''' Displays information about this group. '''
    if not pagure.APP.config.get('ENABLE_USER_MNGT', True):
        flask.abort(404)

    group_type = 'user'
    if pagure.is_admin():
        group_type = None
    group = pagure.lib.search_groups(
        pagure.SESSION, group_name=group, group_type=group_type)

    if not group:
        flask.abort(404, 'Group not found')

    # Add new user to the group if asked
    form = pagure.forms.AddUserForm()
    if pagure.authenticated() and form.validate_on_submit() \
        and pagure.APP.config.get('ENABLE_GROUP_MNGT', False):

        username = form.user.data

        try:
            msg = pagure.lib.add_user_to_group(
                pagure.SESSION,
                username=username,
                group=group,
                user=flask.g.fas_user.username,
                is_admin=pagure.is_admin(),
            )
            pagure.SESSION.commit()
            pagure.lib.git.generate_gitolite_acls()
            flask.flash(msg)
        except pagure.exceptions.PagureException as err:
            pagure.SESSION.rollback()
            flask.flash(err.message, 'error')
            return flask.redirect(
                flask.url_for('.view_group', group=group.group_name))
        except SQLAlchemyError as err:  # pragma: no cover
            pagure.SESSION.rollback()
            flask.flash(
                'Could not add user `%s` to group `%s`.' % (
                    username, group.group_name),
                'error')
            pagure.APP.logger.debug(
                'Could not add user `%s` to group `%s`.' % (
                    username, group.group_name))
            pagure.APP.logger.exception(err)

    member = False
    if pagure.authenticated():
        member = pagure.lib.is_group_member(
            pagure.SESSION, flask.g.fas_user.username, group.group_name)

    return flask.render_template(
        'group_info.html',
        group=group,
        form=form,
        member=member,
    )


@pagure.APP.route('/group/<group>/<user>/delete', methods=['POST'])
@pagure.login_required
def group_user_delete(user, group):
    """ Delete an user from a certain group
    """
    if not pagure.APP.config.get('ENABLE_USER_MNGT', True):
        flask.abort(404)

    if not pagure.APP.config.get('ENABLE_GROUP_MNGT', False):
        flask.abort(404)

    form = pagure.forms.ConfirmationForm()
    if form.validate_on_submit():

        try:
            pagure.lib.delete_user_of_group(
                pagure.SESSION,
                username=user,
                groupname=group,
                user=flask.g.fas_user.username,
                is_admin=pagure.is_admin()
            )
            pagure.SESSION.commit()
            pagure.lib.git.generate_gitolite_acls()
            flask.flash(
                'User `%s` removed from the group `%s`' % (user, group))
        except pagure.exceptions.PagureException as err:
            pagure.SESSION.rollback()
            flask.flash(err.message, 'error')
            return flask.redirect(
                flask.url_for('.view_group', group=group))
        except SQLAlchemyError as err:  # pragma: no cover
            pagure.SESSION.rollback()
            flask.flash(
                'Could not remove user `%s` from the group `%s`.' % (
                    user.user, group),
                'error')
            pagure.APP.logger.debug(
                'Could not remove user `%s` from the group `%s`.' % (
                    user.user, group))
            pagure.APP.logger.exception(err)

    return flask.redirect(flask.url_for('.view_group', group=group))


@pagure.APP.route('/group/<group>/delete', methods=['POST'])
@pagure.login_required
def group_delete(group):
    """ Delete a certain group
    """
    if not pagure.APP.config.get('ENABLE_USER_MNGT', True):
        flask.abort(404)

    if not pagure.APP.config.get('ENABLE_GROUP_MNGT', False):
        flask.abort(404)

    form = pagure.forms.ConfirmationForm()
    if form.validate_on_submit():
        group_obj = pagure.lib.search_groups(
            pagure.SESSION, group_name=group)

        if not group_obj:
            flask.flash('No group `%s` found' % group, 'error')
            return flask.redirect(flask.url_for('.group_lists'))

        user = pagure.lib.search_user(
            pagure.SESSION, username=flask.g.fas_user.username)
        if not user:
            flask.abort(404, 'User not found')

        if group not in user.groups:
            flask.flash(
                'You are not allowed to delete the group %s' % group, 'error')
            return flask.redirect(flask.url_for('.group_lists'))

        pagure.SESSION.delete(group_obj)

        pagure.SESSION.commit()
        pagure.lib.git.generate_gitolite_acls()
        flask.flash(
            'Group `%s` has been deleted' % (group))

    return flask.redirect(flask.url_for('.group_lists'))


@pagure.APP.route('/group/add/', methods=['GET', 'POST'])
@pagure.APP.route('/group/add', methods=['GET', 'POST'])
@pagure.login_required
def add_group():
    """ Endpoint to create groups
    """
    if not pagure.APP.config.get('ENABLE_USER_MNGT', True):
        flask.abort(404)

    if not pagure.APP.config.get('ENABLE_GROUP_MNGT', False):
        flask.abort(404)

    user = pagure.lib.search_user(
        pagure.SESSION, username=flask.g.fas_user.username)
    if not user:  # pragma: no cover
        return flask.abort(403)

    group_types = ['user']
    if pagure.is_admin():
        group_types = [
            grp.group_type
            for grp in pagure.lib.get_group_types(pagure.SESSION)
        ]
        # Make sure the admin type is always the last one
        group_types.remove('admin')
        group_types.append('admin')

    form = pagure.forms.NewGroupForm(group_types=group_types)

    if not pagure.is_admin():
        form.group_type.data = 'user'

    if form.validate_on_submit():

        try:
            group_name = form.group_name.data
            msg = pagure.lib.add_group(
                session=pagure.SESSION,
                group_name=group_name,
                group_type=form.group_type.data,
                user=flask.g.fas_user.username,
                is_admin=pagure.is_admin(),
                blacklist=pagure.APP.config['BLACKLISTED_GROUPS'],
            )
            pagure.SESSION.commit()
            flask.flash('Group `%s` created.' % group_name)
            flask.flash(msg)
            return flask.redirect(flask.url_for('.group_lists'))
        except pagure.exceptions.PagureException as err:
            pagure.SESSION.rollback()
            flask.flash(err.message, 'error')
        except SQLAlchemyError as err:  # pragma: no cover
            pagure.SESSION.rollback()
            flask.flash('Could not create group.')
            pagure.APP.logger.debug('Could not create group.')
            pagure.APP.logger.exception(err)

    return flask.render_template(
        'add_group.html',
        form=form,
    )
