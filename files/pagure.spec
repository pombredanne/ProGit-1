%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from
%distutils.sysconfig import get_python_lib; print (get_python_lib())")}

Name:           pagure
Version:        2.3.3
Release:        1%{?dist}
Summary:        A git-centered forge

License:        GPLv2+
URL:            https://pagure.io/pagure
Source0:        https://pagure.io/releases/pagure/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python2-devel
BuildRequires:  python-setuptools
BuildRequires:  python-nose

BuildRequires:  py-bcrypt
BuildRequires:  python-alembic
BuildRequires:  python-arrow
BuildRequires:  python-binaryornot
BuildRequires:  python-bleach
BuildRequires:  python-blinker
BuildRequires:  python-chardet
BuildRequires:  python-cryptography
BuildRequires:  python-docutils
BuildRequires:  python-flask
BuildRequires:  python-flask-wtf
BuildRequires:  python-flask-multistatic
BuildRequires:  python-markdown
BuildRequires:  python-psutil
BuildRequires:  python-pygit2 >= 0.20.1
BuildRequires:  python-pygments
BuildRequires:  python-fedora
BuildRequires:  python-openid
BuildRequires:  python-openid-cla
BuildRequires:  python-openid-teams
BuildRequires:  python-straight-plugin
BuildRequires:  python-wtforms
BuildRequires:  python-munch
BuildRequires:  python-enum34
BuildRequires:  python-redis

# EPEL6
%if ( 0%{?rhel} && 0%{?rhel} == 6 )
BuildRequires:  python-sqlalchemy0.8
Requires:  python-sqlalchemy0.8
%else
BuildRequires:  python-sqlalchemy > 0.8
Requires:  python-sqlalchemy > 0.8
BuildRequires:  systemd
%endif

Requires:  py-bcrypt
Requires:  python-alembic
Requires:  python-arrow
Requires:  python-binaryornot
Requires:  python-bleach
Requires:  python-blinker
Requires:  python-chardet
Requires:  python-cryptography
Requires:  python-docutils
Requires:  python-enum34
Requires:  python-flask
Requires:  python-flask-wtf
Requires:  python-flask-multistatic
Requires:  python-markdown
Requires:  python-psutil
Requires:  python-pygit2 >= 0.20.1
Requires:  python-pygments
Requires:  python-fedora
Requires:  python-openid
Requires:  python-openid-cla
Requires:  python-openid-teams
Requires:  python-straight-plugin
Requires:  python-wtforms
Requires:  python-munch
Requires:  python-redis
Requires:  mod_wsgi

# No dependency of the app per se, but required to make it working.
Requires:  gitolite3

%description
Pagure is a light-weight git-centered forge based on pygit2.

Currently, Pagure offers a web-interface for git repositories, a ticket
system and possibilities to create new projects, fork existing ones and
create/merge pull-requests across or within projects.


%package milters
Summary:            Milter to integrate pagure with emails
BuildArch:          noarch
BuildRequires:      systemd-devel
Requires:           python-pymilter
Requires(post):     systemd
Requires(preun):    systemd
Requires(postun):   systemd
# It would work with sendmail but we configure things (like the tempfile)
# to work with postfix
Requires:           postfix
%description milters
Milters (Mail filters) allowing the integration of pagure and emails.
This is useful for example to allow commenting on a ticket by email.


%package ev
Summary:   EventSource server for pagure
BuildArch: noarch

BuildRequires:      systemd-devel
Requires:  python-redis
Requires:  python-trollius
Requires:  python-trollius-redis
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%description ev
Pagure comes with an eventsource server allowing live update of the pages
supporting it. This package provides it.


%package webhook
Summary:   Web-Hook server for pagure
BuildArch: noarch

BuildRequires:      systemd-devel
Requires:  python-redis
Requires:  python-trollius
Requires:  python-trollius-redis
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd
%description webhook
Pagure comes with an webhook server allowing http callbacks for any action
done on a project. This package provides it.


%prep
%setup -q


%build
%{__python2} setup.py build


%install
%{__python2} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT

# Install apache configuration file
mkdir -p $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d/
install -m 644 files/pagure.conf $RPM_BUILD_ROOT/%{_sysconfdir}/httpd/conf.d/pagure.conf

# Install configuration file
mkdir -p $RPM_BUILD_ROOT/%{_sysconfdir}/pagure
install -m 644 files/pagure.cfg.sample $RPM_BUILD_ROOT/%{_sysconfdir}/pagure/pagure.cfg

# Install WSGI file
mkdir -p $RPM_BUILD_ROOT/%{_datadir}/pagure
install -m 644 files/pagure.wsgi $RPM_BUILD_ROOT/%{_datadir}/pagure/pagure.wsgi
install -m 644 files/doc_pagure.wsgi $RPM_BUILD_ROOT/%{_datadir}/pagure/doc_pagure.wsgi

# Install the createdb script
install -m 644 createdb.py $RPM_BUILD_ROOT/%{_datadir}/pagure/pagure_createdb.py

# Install the api_key_expire_mail.py script
install -m 644 createdb.py $RPM_BUILD_ROOT/%{_datadir}/pagure/api_key_expire_mail.py

# Install the alembic configuration file
install -m 644 files/alembic.ini $RPM_BUILD_ROOT/%{_sysconfdir}/pagure/alembic.ini

# Install the alembic revisions
cp -r alembic $RPM_BUILD_ROOT/%{_datadir}/pagure


# Install the milter files
mkdir -p $RPM_BUILD_ROOT/%{_localstatedir}/run/pagure
mkdir -p $RPM_BUILD_ROOT/%{_tmpfilesdir}
mkdir -p $RPM_BUILD_ROOT/%{_unitdir}
install -m 0644 milters/milter_tempfile.conf \
    $RPM_BUILD_ROOT/%{_tmpfilesdir}/%{name}-milter.conf
install -m 644 milters/pagure_milter.service \
    $RPM_BUILD_ROOT/%{_unitdir}/pagure_milter.service
install -m 644 milters/comment_email_milter.py \
    $RPM_BUILD_ROOT/%{_datadir}/pagure/comment_email_milter.py

# Install the eventsource
mkdir -p $RPM_BUILD_ROOT/%{_libexecdir}/pagure-ev
install -m 755 ev-server/pagure-stream-server.py \
    $RPM_BUILD_ROOT/%{_libexecdir}/pagure-ev/pagure-stream-server.py
install -m 644 ev-server/pagure_ev.service \
    $RPM_BUILD_ROOT/%{_unitdir}/pagure_ev.service

# Install the web-hook
mkdir -p $RPM_BUILD_ROOT/%{_libexecdir}/pagure-webhook
install -m 755 webhook-server/pagure-webhook-server.py \
    $RPM_BUILD_ROOT/%{_libexecdir}/pagure-webhook/pagure-webhook-server.py
install -m 644 webhook-server/pagure_webhook.service \
    $RPM_BUILD_ROOT/%{_unitdir}/pagure_webhook.service

%post milters
%systemd_post pagure_milter.service
%post ev
%systemd_post pagure_ev.service
%post webhook
%systemd_post pagure_webhook.service

%preun milters
%systemd_preun pagure_milter.service
%preun ev
%systemd_preun pagure_ev.service
%preun webhook
%systemd_preun pagure_webhook.service

%postun milters
%systemd_postun_with_restart pagure_milter.service
%postun ev
%systemd_postun_with_restart pagure_ev.service
%postun webhook
%systemd_postun_with_restart pagure_webhook.service


%files
%doc README.rst UPGRADING.rst
%license LICENSE
%config(noreplace) %{_sysconfdir}/httpd/conf.d/pagure.conf
%config(noreplace) %{_sysconfdir}/pagure/pagure.cfg
%config(noreplace) %{_sysconfdir}/pagure/alembic.ini
%dir %{_sysconfdir}/pagure/
%dir %{_datadir}/pagure/
%config(noreplace) %{_datadir}/pagure/*.wsgi
%{_datadir}/pagure/*.py*
%{_datadir}/pagure/alembic/
%{python_sitelib}/pagure/
%{python_sitelib}/pagure*.egg-info


%files milters
%license LICENSE
%attr(755,postfix,postfix) %dir %{_localstatedir}/run/pagure
%dir %{_datadir}/pagure/
%{_tmpfilesdir}/%{name}-milter.conf
%{_unitdir}/pagure_milter.service
%{_datadir}/pagure/comment_email_milter.py*


%files ev
%license LICENSE
%{_libexecdir}/pagure-ev/
%{_unitdir}/pagure_ev.service


%files webhook
%license LICENSE
%{_libexecdir}/pagure-webhook/
%{_unitdir}/pagure_webhook.service


%changelog
* Fri Jul 15 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.3.3-1
- Update to 2.3.3
- Fix redering the release page when the tag message contain only spaces (Vivek
  Anand)
- Fix the search in @<username> (Eric Barbour)
- Displays link and git sub-modules in the tree with a dedicated icon

* Tue Jul 12 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.3.2-1
- Update to 2.3.2
- Do not mark as local only some of the internal API endpoints since they are
  called via ajax and thus with the user's IP

* Mon Jul 11 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.3.1-1
- Update to 2.3.1
- Fix sending notifications to users watching a project
- Fix displaying if you are watching the project or not

* Mon Jul 11 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.3-1
- Update to 2.3
- Fix typos in pr_custom_page.rst (Lubomír Sedlář)
- Improve the unit-test suite (Vivek Anand)
- Remove the branch chooser from the repoheader and rework the fork button (Ryan
  Lerch)
- Add support for non utf-8 file names (Ryan Lerch)
- Add a 'Duplicate' status for issues (Vivek Anand)
- Add title attribute for replying to comment and editing the comment in issues
  and PRs (Vivek Anand)
- Include the user when reporting error by email
- Add an API endpoint to create projects
- Add an API endpoint to assign someone to a ticket
- Add small script to be ran as cron to send reminder of expiring tokens (Vivek
  Anand)
- Do not show the PR button on branches for which a PR is already opened
- Add an API endpoint to fork projects
- Add the possibility to watch/unwatch a project (Gaurav Kumar)
- Add a 'Take' button on the issue page (Ryan Lerch and I)
- Add a dev-data script to input some test data in the DB for testing/dev
  purposes (skrzepto)
- Fix links to ticket/pull-request in the preview of a new ticket
- Add the possibility to diff two or more commits (Oliver Gutierrez)
- Fix viewing a file having a non-ascii name
- Fix viewing the diff between two commits having a file with a non-ascii name
- On the commit detail page, specify on which branch(es) the commit is
- Add the possibility to have instance-wide admins will full access to every
  projects (set in the configuration file)
- Drop the hash to the blob of the file when listing the files in the repo
- Add autocomple/suggestion on typing @<username> on a ticket or a pull-request
  (Eric Barbour)
- Fix the edit link when adding a comment to a ticket via SSE
- Add notifications to issues as we have for pull-requests
- Record in the db the date at which a ticket was closed (Vivek Anand)
- Add the possibility for pagure to rely on external groups provided by the auth
  service
- Add the possibility for pagure to use an SMTP server requiring auth
  (Vyacheslav Anzhiganov)
- Add autocomple/suggestion on typing #<id> for tickets and pull-requests (Eric
  Barbour)
- With creating a README when project's description has non-ascii characters
  (vanzhiganov)
- Add colored label for duplicate status of issues (Vivek Anand)
- Ship working wsgi files so that they can be used directly from the RPM
- Mark the wsgi files provided with the RPM as %%config(noreplace)
- Install the api_key_expire_mail.py script next to the createdb one

* Wed Jun 01 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.2.1-1
- Update to 2.2.1
- Fix showing the inital comment on PR having only one commit (Ryan Lerch)
- Fix diffs not showing for additions/deletions for files under 1000 lines (Ryan
  Lerch)
- Split out the commits page to a template of its own (Ryan Lerch)
- Fix hightlighting the commits tab on commit view
- Fix the fact that the no readme box show on empty repo (Ryan Lerch)

* Tue May 31 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.2-1
- Update to 2.2
- Fix retrieving the log level from the configuration file (Nuno Maltez)
- Rework the labels used when sorting projects (Ankush Behl)
- Fix spelling error in sample config (Bruno)
- Hide the URL to the git repo for issues if these are disabled
- Do not notify about tickets being assigned when loaded from the issue git repo
  (Clément Verna)
- Adjust get_revs_between so that if the push is in the main branch we still get
  the list of changes (Clément Verna)
- Fix display of files moved on both old and new pygit2 (Ryan Lerch)
- Fix changes summary sidebar for older versions of pygit (Ryan Lerch)
- Fix the label on the button to add a new milestone to a project (Lubomír
  Sedlář)
- Allow the roadmap feature to have multiple milestone without dates (Lubomír
  Sedlář)
- Fix the link to switch the roadmap/list views (Lubomír Sedlář)
- Render the emoji when adding a comment to a ticket or PR via SSE (Clément
  Verna)
- Always allow adming to edit/delete comments on issues
- Build Require systemd to get macros defined in the spec file (Bruno)
- Upon creating a ticket if the form already has data, show that data
- Add a readme placeholder for projects without a readme (Ryan Lerch)
- Enable markdown preview on create pull request (Ryan Lerch)
- Make bottom pagination links on project list respect the sorting filter (Ryan
  Lerch)
- Add the ability to create a README when creating a project (Ryan Lerch)
- Try to prevent pushing commits without a parent when there should be one
- Fix the configuration keys to turn off ticket or user/group management for an
  entire instance (Vivek Anand)
- Fix deleting project (propagate the deletion to the plugins tables)
- Do not render the diffs of large added and removed files (more than 1000
  lines) (Ryan Lerch)
- Adjust the UI on the template to add/remove a group or an user to a project in
  the settings page (Ryan Lerch)
- Check if a tag exists on a project before allowing to edit it (skrzepto)

* Fri May 13 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.1.1-1
- Update to 2.1.1
- Do not render the comment as markdown when importing tickets via the ticket
  git repo
- Revert get_revs_between changes made in
  https://pagure.io/pagure/pull-request/941 (Clement Verna)

* Fri May 13 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.1-1
- Update to 2.1
- Fix the milter to get it working (hotfixed in prod)
- Fix the fedmsg hook so that it works fine (hotfixed in prod)
- Fix the path of one of the internal API endpoint
- Pass client_encoding utf8 when connecting to the DB (Richard Marko)
- Do not use client_encoding if using sqlite (Ryan Lerch)
- Allow project names up to 255 characters (Richard Marko)
- Add a spinner showing we're working on retrieve the PR status on the PR page
  (farhaanbukhsh)
- Rework installing and removing git hooks (Clement Verna)
- Rework the summary of the changes on the PR page (Ryan Lerch)
- Improve the description of the priority system (Lubomír Sedlář)
- Fix commit url in the pagure hook (Mike McLean)
- Improve the regex when fixing/relating a commit to a ticket or a PR (Mike
  McLean)
- Improve the description of the pagure hook (Mike McLean)
- Fix the priority system to support tickets without priority
- Fix the ordering of the priority in the drop-down list of priorities
- Ensure the drop-down list of priorities defaults to the current priority
- Adjust the runserver.py script to setup PAGURE_CONFIG before importing pagure
- Remove flashed message when creating a new project
- Add markdown support for making of PR# a link to the corresponding PR
- Include the priority in the JSON representation of a ticket
- Include the priorities in the JSON representation of a project
- Do not update the assignee if the person who commented isn't an admin
- When adding a comment fails, include the comment text in the form if there was
  one
- Add support to remove a group from a project
- Add a roadmap feature with corresponding documentation
- Allow 'kbd' and 'var' html tags to render properly
- Fix deleting a project on disk as well as in the DB
- Allow setting the date_created field when importing ticket from git (Clement
  Verna)
- Strip GPG signature from the release message on the release page (Jan Pokorný)
- Make comment on PR diffs fit the parent, and not overflow horiz (Ryan Lerch)

* Sun Apr 24 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.0.1-1
- Update to 2.0.1
- Fixes to the UPGRADING documentation
- Fix URLs to the git repos shown in the overview page for forks
- Fix the project titles in the html to not start with `forks/`

* Fri Apr 22 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 2.0-1
- Update to 2.0
- Rework the initial comment of a PR, making it less a comment and more
  something that belong to the PR itself
- Fix showing or not the fork button when editing a comment on an issue or a PR
  and fix the highlighted tab when editing comment of an issue (Oliver
  Gutierrez)
- Fix the count of comments shown on the page listing all the PRs to include
  only the comments and not the notifications (farhaanbukhsh)
- In the settings page explain that API keys are personal (Lubomír Sedlář)
- Rework the fedmsg message sent upon pushing commits, one message per push
  instead of one message per commit
- Mark the page next/previous as disabled when they are (on browse pages)
- Avoid the logout/login loop when logging out
- Support rendering file with a `.markdown` extension
- Fix the layout of the password change branch
- Improve the documentation, add overview graphs, expand the usage section,
  improve the overview description
- Fix checking if the user is an admin of a project or not (which was making the
  user experience confusing as they sometime had the fork button and sometime
  not)
- Fix the pagination on the browse pages when the results are sorted
- Disable the Commit and Files tabs if a repo is new
- Update the pagure logo to look better (Ryan Lerch)
- Allow anyone to fork any project (Ryan Lerch)
- Fix searching on the browse pages by preventing submission of the 'enter' key
  (Ryan Lerch)
- Rework the issue page to be a single, large form allowing to update the
  meta-data and comment in one action and fixing updating the page via SSE
- Turn off the project's documentation by default to empty `Docs` tab leading to
  nothing
- Fill the initial comment with the body of the commit message if the PR only
  has one commit (Ryan Lerch)
- Add a plugin/git hook allowing to disable non fast-forward pushes on a branch
  basis
- Fix asynchronous inline comments in PR by fixing the URL to which the form is
  submitted
- Add a plugin/git hook allowing to trigger build on readthedocs.org upon git
  push, with the possibility to restrict the trigger to only certain branches
- Automatically scroll to the highlighted range when viewing a file with a
  selection (Lubomír Sedlář)
- Indicate the project's creation date in the overview page (Anthony Lackey)
- Clear the `preview` field after adding a comment via SSE
- Adjust the unit-tests for the change in behavior in pygments 2.1.3
- Fix listing all the request when the status is True and do not convert to text
  request.closed_at if it is in fact None
- Improved documentation
- Attempt to fix the error `too many open files` on the EventSource Server
- Add a new param to runserver.py to set the host (Ryan Lerch)
- Fix the of the Docs tab and the Fork button with rounded corners (Pedro Lima)
- Expand the information in the notifications message when a PR is updated (Ryan
  Lerch)
- Fix hidding the reply buttons when users are not authenticated (Paul W. Frields)
- Improve the description of the git hooks (Lubomír Sedlář)
- Allow reply to a notification of pagure and setting the reply email address as
  Cc
- In the fedmsg git hook, publish the username of all the users who authored the
  commits pushed
- Add an activity page/feed for each project using the information retrieved
  from datagrepper (Ryan Lerch)
- Fix showing lightweight tags in the releases page (Ryan Lerch)
- Fix showing the list of branches when viewing a file
- Add priorities to issues, with the possibility to filter or sort them by it in
  the page listing them.
- Add support for pseudo-namespace to pagure (ie: allow one '/' in project name
  with a limited set of prefix allowed)
- Add a new plugin/hook to block push containing commits missing the
  'Signed-off-by' line
- Ensure we always use the default email address when sending notification to
  avoid potentially sending twice a notification
- Add support for using the keyword Merge(s|d) to close a ticket or pull-request
  via a commit message (Patrick Uiterwijk)
- Add an UPGRADING.rst documentation file explaining how to upgrade between
  pagure releases

* Tue Mar 01 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 1.2-1
- Update to 1.2
- Add the possibility to create a comment when opening a pull-request (Clement
  Verna)
- Fix creating PR from a fork directly from the page listing all the PR on the
  main project (Ryan Lerch)
- Color the label showing the issues' status on the issue page and the page
  listing them (Ryan Lerch)
- Add a small padding at the bottom of the blockquote (Ryan Lerch)
- In the list of closed PR, replace the column of the assignee with the date of
  closing (Ryan Lerch)
- Drop font awesome since we no longer use it and compress the png of the 
  current logo (Ryan Lerch)
- Drop the svg of the old logo from the source (Ryan Lerch)
- Add descriptions to the git hooks in the settings page (farhaanbukhsh)
- Fix the pagure git hook

* Wed Feb 24 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 1.1.1-1
- Update to 1.1.1
- Fix showing some files where decoding to UTF-8 was failing
- Avoid adding a notification to a PR for nothing
- Show notifications correctly on the PR page when received via SSE

* Tue Feb 23 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 1.1-1
- Update to 1.1
- Sort the release by commit time rather than name (Clerment Verna)
- Add a link to the markdown syntax we support
- Add the possibility to display custom info when creating a new PR
- Improve the title of the issue page
- Make the ssh_info page more flexible so that we can add new info more easily
- Add the possibility to resend a confirmation email when adding a new email
  address
- Encode the email in UTF-8 for domain name supporting it
- Add a button to easily change your avatar in your settings' page (Clement
  Verna)
- Expand our markdown processor to support implicit linking to both PR and
  issues
- Fix running the unit-tests on F23
- Fix deleting in the UI branches containing a slash ('/') in their name
- Add the possibility to always have a merge commit when merging a PR
- Add the project's avatar to the list in front page when authenticated
- Make the dependency on flask-fas-openid (part of python-fedora) optional
- Prevent our customized markdown to create link on foo.com if it doesn't start
  with {f,ht}tp(s) (Clement Verna)
- Bring back the delete ticket button (Ryan Lerch)
- Add the possibility to notify someone when it is mentioned in a comment via
  @username
- Fix setting the default value of the web-hook setting and its display in the
  settings page
- Add the possibility to have templates for the issues
- Add a button on the doc page to open it in a new tab
- Add the concept of notifications on PR allowing to indicate when a PR is
  updated or rebased
- Fix allowing people with non-ascii username to merge PR with a merge commit
- Add the possibility to theme your pagure instance and customized its layout at
  will
- Add the possibility to always see inline-comments even if the file was changed
  since
- Improve the error message given to the user upon error 500 (Patrick Uiterwijk)
- Stop relying on pygit2 to determine if a file is a binary file or not and
  instead use the python library binaryornot
- Store in the DB the identifier of the tree when an inline comment is made to a
  PR, this way it will be simpler to figure out a way to add the context of this
  comment either by email on in the UI
- Add styling to blockquotes so that we see what is the quote and what is the
  answer when replying to someone
- Prevent users from adding again an email pending confirmation
- Fix the preview box for long comment (Ryan Lerch)
- Add the possibility to sort the projects when browsing them (Ryan Lerch)

* Thu Feb 04 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 1.0.2-1
- Update to 1.0.2
- Rework the PR page (Ryan Lerch)
- Add ssh_info to blacklist in default config (Ryan Lerch)
- Restyle the ssh_info page (Ryan Lerch)
- Fix hiding the preview pane when creating an issue (Ryan Lerch)
- Indicate the number of comments on the PR when listing them (Ryan Lerch)
- Fix showing the links to issues when previewing a comment
- Ensure some more that the page number isn't below 1
- Do not show the edit and delete buttons to everyone when adding a comment via
  SSE
- Update the requirements.txt for a missing dependency on Ubuntu (vanzhiganov)
- Improving sorting the release tags in the release page (Clement Verna)

* Mon Feb 01 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 1.0.1-1
- Update to 1.0.1
- Improve the fork list (Ryan Lerch)
- Make sure the images on comments do not exceed the size of the comment
  box/area (Ryan Lerch)
- Improve the page listing all issues (Ryan Lerch)
- Include the project information when sending a fedmsg message about editing a
  comment
- Allow <span> tags in rst files so that the README shows fine
- Fix linking directly to a specific comment in a PR
- Fix adding comment in a PR via SSE
- Fix updating issue information via SSE
- Fix the reply buttons on the issue page
- Remove the choice for a status when creating a new ticket (Farhaandukhsh)
- Fix deleting a branch from the UI
- Make the cards have rounded corners (Sayan Chowdhury)
- Fix showing the description of form field (Vivek Anand)
- Fix checking if the passwords added are the same (for local accounts)
  (Vivek Anand)
- Fix displaying emojis when previewing a comment on a ticket (Clement Verna)
- Add support for emojis when creating a new ticket (Clement Verna)

* Wed Jan 27 2016 Pierre-Yves Chibon <pingou@pingoured.fr> - 1.0-1
- Update to 1.0
- Entirely new UI thanks to the hard work on Ryan Lerch
- Add the possibility to edit comments on PR/Tickets (and the option to disable
  this) (farhaanbukhsh)
- Add the number of open Tickets/PR on the project's menu
- Also allow PRs to be closed via a git commit message (Patrick Uiterwijk)
- Disable issues and PR on forks by default (Vivek Anand)
- Fix deleting the temporary folders we create
- Un-bundle flask_fas_openid (requires python-fedora 0.7.0 or higher
- Add support for an openid backend (ie same thing as FAS but w/o the FPCA
  enforcing)
- Add support to view rst/markdown files as html directly inline (default) or as
  text (Yves Martin)
- Change the encryption system when using pagure with local auth to not be
  time-sensitive and be stronger in general (farhaanbukhsh)
- Change the size of the varchar from 256 to 255 for a better MySQL support
- Add support for pagure to work behind a reverse proxy
- Rename the cla_required decorator to a more appropriate login_required
- Show the in the front page and the page listing all the pull-requests the
  branch for which a PR can be opened
- Rework the avatar to not rely on the ones associated with id.fedoraproject.org
- Add support to high-light a section of code in a PR and show the diff
  automatically if there is such selection

* Mon Dec 14 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.36-1
- Update to 0.1.36
- Add the ssh info on the front page if the repo is empty
- Make the code handling exception be python3 compatible
- Make pagure compatible with F23 (ie: pygit2 0.23.0)
- Fix pagination when rendering the repo blocks (Gaurav Kumar)
- Make the SHOW_PROJECTS_INDEX list what should be showing in the index page
- Adjust pagure to work on recent version of psutils as well as the old one
- Added 'projects' to the blacklisted list of projects (Gaurav Kumar)
- Removed delete icons for non group members on the group info page (Gaurav
  Kumar)
- Fixed forbidden error for PR title editing (Gaurav Kumar)

* Mon Nov 30 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.35-1
- Update to 0.1.35
- Fix the web-hook server by preventing it to raise any exception (rather log
  the errors)

* Mon Nov 30 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.34-1
- Update to 0.1.34
- Fix the encoding of the files we're displaying on the UI
- Fix commenting on the last line of a diff
- Fix returning error message from the internal API (shows the PR as conflicting
  then)
- Fix stacktrace encountered in some repo if the content of a folder is empty
  (or is a git submodule)
- Split the web-hooks into their own server
- If you try to fork a forked project, redirect the user to the fork
- Show the repo from and repo to when opening a new PR
- Add the pagination links at the bottom of the repo list as well
- Add the groups to the pool of users to notify upon changes to a project
- Hide private repo from user who do not have commit access

* Fri Nov 20 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.33-1
- Update to 0.1.33
- Prevent project with a name starting with a non-alphanumerical character
  (Farhaanbukhsh)
- Ensure we appropriately set the private flag when creating an issue
- Add an activity graph on the user profile using datagrepper
- Sometime the identified we get is a Tag, not a commit (fixes traceback
  received by email)
- Order the PR from the most recent to the oldest
- Fix the patch view of a PR when we cannot find one of the commit (fixes
  traceback received by email)
- Allow user that are not admin to create a remote pull-request
- Fix closing the EV server by calling the appropriate variable
- Fix generating the diff of remote pull-request

* Fri Nov 13 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.32-1
- Update to 0.1.32
- Fix the example configuration file
- Make pagure work on MySQL
- Hide sections on the front page only if the user is logged out
- Fix the release page where sometime tags are commits
- Escape the raw html in markdown
- Decode the bytes returned by pygit2 to try to guess if the content is a text
  or not
- Fix the 'Clear' button on the pull-request page (farhaanbukhsh)
- Fix installing pagure in a venv
- Fix uploading images when editing the first comment of a ticket
- Let the author of the merge commit be the user doing the merge
- Suggest the title of the PR only if it has one and only one commit in
- Do not hide sections on the user page if we set some to be hidden on the front
  page
- Forward the head to the commits page to fix the pull-request button
- Ensure we create the git-daemon-export-ok when forking a repo (fixes cloning
  over https)
- Add instructions on how to get pagure working in a venv (Daniel Mach)
- Improve the way we retrieve and check pygit2's version (Daniel Mach)

* Tue Oct 13 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.31-1
- Forward the bail_on_tree boolean when iterating so that we know how to behave
  when we run into a git tree (where we expected a git blob)
  -> fixes error received by email

* Tue Oct 13 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.30-1
- Fix error received by email by checking the right variable if it is a git tree
  or a git blob
- Unless we explicitly accept all images tag, always filter them (fixes
  attaching images to a ticket)

* Tue Oct 13 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.29-1
- Use monospace fonts for online editing as well as comment on tickets and
  pull-requests
- Fix online editing of symlinked files (such as the README)
- Handle potential error when converting from rst to html

* Mon Oct 12 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.28-1
- Update to 0.1.28
- Fix the call to noJS() in the pull-request template to avoid crashing
- Improve the runserver script in the sources
- Fix the projects pagination on the index page
- Create the git-daemon-export-ok file upon creating a new project/git
- Use first line of commit message for PR title when only one commit (Maciej
  Lasyk)
- Show the tag message near the tag in the release page
- Set the default_email when creating a local user account

* Mon Oct 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.27-1
- Update to 0.1.27
- Skip writing empty ssh keys on disc
- Regenerate authorized_keys file on ssh key change (Patrick Uiterwijk)

* Mon Oct 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.26-1
- Update to 0.1.26
- Let admins close PRs as well

* Mon Oct 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.25-1
- Update to 0.1.25
- Improve the documentation (especially the part about configuring pagure and
  all the options the configuration file supports)
- Remove the two trailing empty lines when showing a file online
- Add a link on the issue list to be able to filter all the unassigned issues
- Rework the layout of the pull-request page
- Rework the commit list in the PR page to allow showing the entire commit
  message
- Let any user create remote pull-request otherwise what's the point?
- Add the possibility to edit the title of a pull-request
- Add a page listing all the pull-requests of an user (opened by or against)
- Add support for multiple ssh-keys (Patrick Uiterwijk)
- Ensure the authorized_keys file is generated by gitolite (Patrick Uiterwijk)
- Fix the regex for @<username>
- Improve the display of renamed files in PR
- Add option to disable entirely the user/group management from the UI
- Add an updated_on field to Pull-Request
- Add an closed_at field to Pull-Request
- Allow the submitter of a PR to close it (w/o merging it)
- Disable editing a pull-request when that one is closed/merged
- Add option to hide by default a part of the index page (ie: all the repos, the
  user's repos or the user's forks)
- Drop the csrf_token from the error emails sent to the admins

* Tue Sep 08 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.24-1
- Update to 0.1.24
- Fix changelog to add the -release
- Block the <img> tag on titles
- Better fedmsg notifications (for example for new branches or rebase)
- Support uploading multiple files at once
- Add a load_from_disk utility script to the sources
- Fix indentation to the right on very long pull-request

* Sun Aug 30 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.23-1
- Update to 0.1.23
- Return a 404 error if we can't find the doc repo asked
- Fix for #106 Allow setting the default branch of the git repo and in the UI
  (Ghost-script)
- Improve unit-tests suite
- Add a global boolean to disable entirely tickets on all projects of a pagure
  instance (with no way to re-set them per project)
- Do display uploading a tarball if it is not entirely configured
- Ensure we do not offer to reply by email if the milter is not set up
- Ensure there is no new line character on the msg-id and improve logging in the
  milter
- Add a configuration key to globally disable creating projects
- Add a configuration key to globally disable deleting projects
- Add the possibility to search projects/users
- Drop links to the individual commits in a remote pull-request
- Input that are cleaned via the noJS filter are safe to be displayed (avoid
  double HTML escaping)
- When writing the authorized_key file, encode the data in UTF-8
- Makes page title easier to find in multi-tab cases (dhrish20)
- Fix authorized_keys file creation (Patrick Uiterwijk)
- Honor also symlinked README's in repo overview (Jan Pakorný)
- Fix the patch generation for remote PR
- Fix showing the comment's preview on the pull-request page
- Fix bug in checking if a PR can be merged

* Fri Aug 07 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.22-1
- Update to 0.1.22
- Adjust the README to the current state of pagure
- Rework how we integrate our custom tags into markdown to avoid the infinite
  loop we run into once in a while

* Wed Aug 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.21-1
- Update to 0.1.21
- Make SSH protocol explicit for SSH URLs (Till Maas)
- Adjust the documentation (layout and content)
- Rework the doc server to allow showing html files directly
- Fix installing the pagure hook correctly (tickets and requests)
- Give proper attribution to the pagure logo to Micah Deen in the documentation
- Increase pull request text field lengths to 80 (Till Maas)
- Fix who can open a remote PR and the check that the repo allows PR
- If there is no commit and no content, it means we didn't find the file: 404

* Wed Jul 29 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.20-1
- Update to 0.1.20
- Include the tags in the JSON representation of a project
- Add the ability to open a pull-request from a git repo not hosted on pagure
- Fix pagination when browsing the list of commits
- Fix the fork button when viewing the Settings of a project
- Adjust the example apache configuration file
- Add a favicon with pagure's logo
- Fix asynchronous commentting on pull-requests
- Start working on some documentation on how to install pagure
- Do no flash messages when a comment is submitted via javascript (ie: async)
- Do not blink the tittle of the page if the page is already on focus
- Retrieve ssh key from FAS and set it up in pagure if none is currently set-up
- Fix anchors for comments on the pull-request pages
- Fix checking the merge status of a PR when user is not logged in

* Mon Jul 20 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.19-1
- Update to 0.1.19
- Prettify the JSON stored in the git for tickets/requests... (Simo Sorce)
- Use the project name as subject tag in the notifications sent (Simo Sorce)
- Add an X-pagure header with either the pagure instance or the project name
- Reset the merge status of all the open PR when one is merged
- Add a second server listing the number of connections opened on the first
  eventsource server
- Log the info instead of printing them in the eventsource server
- Split the documentation to a different wsgi application to avoid any risk of
  cross-site forgery
- Fix the JS logic when adding a tag or a dependency to avoid having duplicates
  in the input field
- Allow deleting a git branch of a project via the UI
- Include the font-awesome in the source rather than relying on an external cdn
- Do not try to connect to the eventsource server if we're not viewing a
  pull-request
- Fix showing the first comment made on a PR via the eventsource server
- Fix showing the git URLs in the doc server
- Much better API documentation (Lei Yang)
- Handle showing closed PR that were not merged
- Fix refreshing the UI of private tickets via the eventsource (making calls to
  the API to get the info while only getting what changed via the SSE)
- Fix the anchor links in the API documentation
- Blink the tab upon changes in the page
- Ensure we close both SSE server when stopping pagure_ev
- Let the HTML form trigger if we did not connect to the EV server successfully
- The admins of a repo are anyone with commit access to the repo, directly or
  via a group
- Order the project by names in the front page (instead of creation date)
- Add the ability to tag a project
- Fix the fedmsg_hook when there are only deletions or only additions
- Add a new API endpoint allowing to search projects (by name, author, tag ...)
- Make pagure compatible with pygit 0.22.0
- Adjust unit-tests for all these changes

* Mon Jun 22 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.18-1
- Update to 0.1.18
- Fix the eventsource server for CORS
- Fix showing/checking the merge status of a PR

* Mon Jun 22 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.17-1
- Update to 0.1.17
- Fix for missing docs of API issue add comment (Kunaal Jain)
- Fix the systemd init file
- Be more careful about the URL specified, it may be of the wrong format in the
  eventsource server
- Allow configuring the port where the event source server runs in the
  configuration
- Fix bug in filter_img_src introduced with its moved to the backend library

* Thu Jun 18 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.16-1
- Update to 0.1.16
- Clone all the remote branches when cloning a project
- Allow online editing to a new branch or any of the existing ones
- Allow the <hr /> html tags in markdown
- Add eventsource support in the ticket and pull-request pages

* Tue Jun 16 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.15-1
- Update 0.1.15
- Use a monospace font for the commit hash
- Remove duplicated "commit" id in the HTML (causing a graphical bug in the
  commit page)
- Secure the input using the no_js filter instead of relying on a restrictive
  regex for PR and issue titles
- Support ',' in the tags field since it's required to specify multiple tags

* Fri Jun 12 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.14-1
- Update to 0.1.14
- Remove all new lines characters from the ssh key uploaded
- Adjust the URL in the footer to point to https://pagure.io/pagure
- Fix displaying the time of a comment
- Forbid the use of spaces in group name
- Do not get the list of not-merged commits if there is only 1 branch in the
  repo
- Display the error message if pagure.lib.add_group raises an exception
- Add a new setting enforcing that all commits in a PR are signed-off by their
  author
- Enforce that all commits are signed-off by the author if the repo is
  configured for this
- Also check for the signed-off status before merging a pull-request
- Adjust online-editing to allow specifying which email address to use in the
  commit
- Add an avatar_email field to projects
- Change the PullRequest's status from a Boolean to a Text restricted at the DB
  level (Allows to distinguish Open/Merged/Closed)
- Show in the pull-request view who merged the pull-request
- Specify who closed the pull-request in the API output
- Catch GitError when merging and checking merge status of a PR
- Hide the form to create pull-requests if the user is not an admin of the repo
- Replace the Pull-Request button by a Compare button if the user it not a repo
  admin
- Set the title of the tab as URL hash to allow directly linking to it
- Adjust the API to be able to distinguish API authentication and UI
  authentication
- Fix API documentation to create new issues
- Drop the status from the requirements to open a new issue via the API
- Expand the list of blacklisted project names
- Have the code tags behave like pre tags (html tags)
- Allow project to specify an URL and display it on their page
- Strip the ssh keys when writing them to the authorized_keys file
- Disable javascript in all the markdown fields
- Validate early the input submitted in the forms (using more or less strict
  regex)
- If the session timed-out, redirect to the setting page after authentication
  and inform the user that the action was canceled
- Catch PagureException when adjusting the project's settings
- Redirect the /api endpoint to the api documentation place
- Fix how is retrieved the list of emails to send the notification to
- Sanitize the html using bleach to avoid potential XSS exploit
- Do not give READ access to everyone on the tickets and pull-requests repos to
  avoid leaking private tickets
- Adjust the unit-tests for all these changes

* Fri Jun 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.13-1
- Update to 0.1.13
- Do not show the edit button if the user cannot edit the file
- Fix who is allowed to drop comments
- Fix showing the drop comment button on issue comments
- Fix creating the pull-request for fast people like @lmacken
- Display the target of the PR as well as the origin in the PR page
- Limit the size of the lists on the front page

* Fri Jun 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.12-1
- Update to 0.1.12
- Fix the URL where the sources upload are done
- Upload the new sources under the project's name (be it project or
  user/project)

* Fri Jun 05 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.11-1
- Update to 0.1.11
- Another fix for the fedmsg_hook git hook
- Adjust how we display the README page to avoid XSS there as well
- Add the possibility to disable plugins via the configuration file
- Present the git tags in the UI
- As soon as the API user present a token, validate it or not, even if the
  endpoint would work without token
- Integrate alembic for DB scheme migration
- Cache the PR's merge status into the DB
- Only people with access to the project can add/remove API token
- Make the unit-tests run on bare repos as in prod
- First stab at online editing
- Simplify the API output to drop the project's settings where it doesn't
  make sense
- First stag at allowing upstream to upload their release to pagure
- Fix merging a PR into another branch than master
- Reduce code duplication when checking if a PR can be merged or merging it
- Code style clean-up

* Tue Jun 02 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.10-1
- Update to 0.1.10
- Add support for URL ending with a trailing slash where it makes sense (so
  we support both with and without trailing slash)
- Fix XSS issue by disabling <script> tags in the documentation pages
- Expend the unit-test suite for the api.project controller
- Add the possibility for 3rd party apps to 'flag' a pull-request with for
  example the result of a build
- Handle the situation where there are multiple branch of the same name in
  the same repo
- Fix the color of the link on hover when displayed within a tab view
  (for example in the PR pages)
- Redirect the user to the pull-request created after its the creation
- Do not leak emails over fedmsg
- Fix the fedmsg_hook plugin

* Fri May 29 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.9-1
- Update to 0.1.9
- Initial API work
- Document the initial API
- Fix the CSS to present the links correctly
- Add new API endpoint to list the git tags of a project
- Ensure the DB is updated regarding the start and stop commits before merging

* Wed May 27 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.8-1
- Update 0.1.8
- Add the possibility to do Asynchronous in-line comment posting
  (Patrick Uiterwijk)
- Handle the situation where the branch asked is not found in the git repo
- Handle the situation where we cannot find a desired commit
- Do not display a value in the settings page if there are none
- Rework the pull-request view to move the list of commits into a tab
- Make email sending optional (Patrick Uiterwijk)

* Fri May 22 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.7-1
- Update to 0.1.7
- Drop debugging code on the milter and the hooks
- Adjust the search_issues method to support filter for some tags, excluding
  some others (for example ?tags=easfix&tags=!0.2)
- Support groups when searching an user's projects (ie: finding the projects an
  user has access to via the group their are in)
- Do not load the git repo from the FS when loading an user's page
- Present and document the SSH keys in a dedicated documentation page

* Wed May 20 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.6-1
- Update to 0.1.6
- Fix sending notification emails to multiple users, avoid sending private into
  to all of them

* Tue May 19 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.5-1
- Update to 0.1.5
- Bug fix on the milter and the internal API endpoint

* Tue May 19 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.4-1
- Update to 0.1.4
- Fix loading requests and tickets from git (allows syncing projects between
  pagure instances)
- Add to the template .wsgi file a way to re-locate the tmp folder to work
  around a bug in libgit2
- Fix unit-tests suite
- Adjust the spec file to install all the files required for the milters
- Fix the `View` button on the pull-request pages

* Wed May 13 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.3-1
- Update to 0.1.3
- Add support for gitolite3
- Fix unit-tests suite to work on jenkins

* Sat May 09 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.2-2
- Fix the Requires on the milter subpackage (adding: post, preun and postun)
- Add systemd scriptlet to restart the service gracefully
- Use versioned python macro (py2)
- Ship the license in the milter subpackage as well
- Use the %%license macro

* Thu May 07 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.2-1
- Update to 0.1.2
- Fix bug in the fedmsg hook file (Thanks Zbigniew Jędrzejewski-Szmek)

* Wed May 06 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1.1-1
- Update to 0.1.1
- Port to python-munch and list it in the dependencies
- Fix exporting patch when they contain unicode characters or accent
- After creating an issue, user is brought back to the new issue page
- Fix unit-tests
- Stop the pagure hook if the user is deleting a branch (no need to run through
  all the commits of that branch)
- Fix the requirements.txt file (Sayan Chowdhury)
- Fix the tree page to show the commit sha on its proper line (Sayan Chowdhury)
- Fix typo in the form of some of the plugin (Sayan Chowdhury)
- Improve the README (Sayan Chowdhury)
- Fix highlighting the commits tab when accessing it (Sayan Chowdhury)

* Mon May 04 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.1-1
- First official release: 0.1

* Thu Apr 02 2015 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.0-1.20150402
- Cut a RPM for testing on Thu Apr 2nd 2015

* Wed Oct 08 2014 Pierre-Yves Chibon <pingou@pingoured.fr> - 0.0-1.20141008
- Initial packaging work for Fedora
