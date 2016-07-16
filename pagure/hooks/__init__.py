# -*- coding: utf-8 -*-

"""
 (c) 2014 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import os
import shutil
import wtforms

from pagure.exceptions import FileNotFoundException
from pagure import APP, get_repo_path


class RequiredIf(wtforms.validators.Required):
    """ Wtforms validator setting a field as required if another field
    has a value.
    """

    def __init__(self, fields, *args, **kwargs):
        if isinstance(fields, basestring):
            fields = [fields]
        self.fields = fields
        super(RequiredIf, self).__init__(*args, **kwargs)

    def __call__(self, form, field):
        for fieldname in self.fields:
            nfield = form._fields.get(fieldname)
            if nfield is None:
                raise Exception(
                    'no field named "%s" in form' % fieldname)
            if bool(nfield.data):
                super(RequiredIf, self).__call__(form, field)


class BaseHook(object):
    ''' Base class for pagure's hooks. '''

    name = None
    form = None
    description = None
    hook_type = 'post-receive'

    @classmethod
    def set_up(cls, project):
        ''' Install the generic post-receive hook that allow us to call
        multiple post-receive hooks as set per plugin.
        '''
        repopaths = [get_repo_path(project)]
        for folder in [
                APP.config.get('DOCS_FOLDER'),
                APP.config.get('REQUESTS_FOLDER')]:
            repopaths.append(
                os.path.join(folder, project.path)
            )

        hook_files = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'files')

        for repopath in repopaths:
            # Make sure the hooks folder exists
            hookfolder = os.path.join(repopath, 'hooks')
            if not os.path.exists(hookfolder):
                os.makedirs(hookfolder)

            # Install the main post-receive file
            postreceive = os.path.join(hookfolder, cls.hook_type)
            if not os.path.exists(postreceive):
                os.symlink(os.path.join(hook_files, cls.hook_type),
                           postreceive)

    @classmethod
    def base_install(cls, repopaths, dbobj, hook_name, filein):
        ''' Method called to install the hook for a project.

        :arg project: a ``pagure.model.Project`` object to which the hook
            should be installed
        :arg dbobj: the DB object the hook uses to store the settings
            information.

        '''
        for repopath in repopaths:
            if not os.path.exists(repopath):
                raise FileNotFoundException('Repo %s not found' % repopath)

            hook_files = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), 'files')

            # Make sure the hooks folder exists
            hookfolder = os.path.join(repopath, 'hooks')
            if not os.path.exists(hookfolder):
                os.makedirs(hookfolder)

            # Install the hook itself
            hook_file = os.path.join(repopath, 'hooks', cls.hook_type + '.'
                                     + hook_name)

            if not os.path.exists(hook_file):
                os.symlink(
                    os.path.join(hook_files, filein),
                    hook_file
                )

    @classmethod
    def base_remove(cls, repopaths, hook_name):
        ''' Method called to remove the hook of a project.

        :arg project: a ``pagure.model.Project`` object to which the hook
            should be installed

        '''
        for repopath in repopaths:
            if not os.path.exists(repopath):
                raise FileNotFoundException('Repo %s not found' % repopath)

            hook_path = os.path.join(repopath, 'hooks', cls.hook_type + '.'
                                     + hook_name)
            if os.path.exists(hook_path):
                os.unlink(hook_path)
