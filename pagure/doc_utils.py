# -*- coding: utf-8 -*-

"""
 (c) 2014 - Copyright Red Hat Inc

 Authors:
   Ralph Bean <rbean@redhat.com>
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

import docutils
import docutils.core
import docutils.examples
import markupsafe
import markdown
import textwrap


def modify_rst(rst, view_file_url=None):
    """ Downgrade some of our rst directives if docutils is too old. """
    if view_file_url:
        rst = rst.replace(
            '.. image:: ',
            '.. image:: %s' % view_file_url
        )

    # We catch Exception if we want :-p
    # pylint: disable=W0703
    try:
        # The rst features we need were introduced in this version
        minimum = [0, 9]
        version = [int(cpt) for cpt in docutils.__version__.split('.')]

        # If we're at or later than that version, no need to downgrade
        if version >= minimum:
            return rst
    except Exception:  # pragma: no cover
        # If there was some error parsing or comparing versions, run the
        # substitutions just to be safe.
        pass

    # On Fedora this will never work as the docutils version is to recent
    # Otherwise, make code-blocks into just literal blocks.
    substitutions = {  # pragma: no cover
        '.. code-block:: javascript': '::',
    }

    for old, new in substitutions.items():  # pragma: no cover
        rst = rst.replace(old, new)

    return rst  # pragma: no cover


def modify_html(html):
    """ Perform style substitutions where docutils doesn't do what we want.
    """

    substitutions = {
        '<tt class="docutils literal">': '<code>',
        '</tt>': '</code>',
    }
    for old, new in substitutions.items():
        html = html.replace(old, new)

    return html


def convert_doc(rst_string, view_file_url=None):
    """ Utility to load an RST file and turn it into fancy HTML. """
    rst = modify_rst(rst_string, view_file_url)

    overrides = {'report_level': 'quiet'}
    try:
        html = docutils.core.publish_parts(
            source=rst,
            writer_name='html',
            settings_overrides=overrides)
    except:
        return '<pre>%s</pre>' % rst

    else:

        html_string = html['html_body']

        html_string = modify_html(html_string)

        html_string = markupsafe.Markup(html_string)
        return html_string


def convert_readme(content, ext, view_file_url=None):
    ''' Convert the provided content according to the extension of the file
    provided.
    '''
    output = content
    safe = False
    if ext and ext in ['.rst']:
        safe = True
        output = convert_doc(content.decode('utf-8'), view_file_url)
    elif ext and ext in ['.mk', '.md', '.markdown']:
        output = markdown.markdown(content.decode('utf-8'))
        safe = True
    elif not ext or (ext and ext in ['.text', '.txt']):
        safe = True
        output = '<pre>%s</pre>' % content
    return output, safe


def load_doc(endpoint):
    """ Utility to load an RST file and turn it into fancy HTML. """

    rst = unicode(textwrap.dedent(endpoint.__doc__))

    rst = modify_rst(rst)

    api_docs = docutils.examples.html_body(rst)

    api_docs = modify_html(api_docs)

    api_docs = markupsafe.Markup(api_docs)
    return api_docs
