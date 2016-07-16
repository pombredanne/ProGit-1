#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Milter calls methods of your class at milter events.
# Return REJECT,TEMPFAIL,ACCEPT to short circuit processing for a message.
# You can also add/del recipients, replacebody, add/del headers, etc.

import base64
import email
import hashlib
import os
import urlparse
import StringIO
import sys
import time
from socket import AF_INET, AF_INET6
from multiprocessing import Process as Thread, Queue

import Milter
import requests

from Milter.utils import parse_addr

logq = Queue(maxsize=4)


if 'PAGURE_CONFIG' not in os.environ \
        and os.path.exists('/etc/pagure/pagure.cfg'):
    os.environ['PAGURE_CONFIG'] = '/etc/pagure/pagure.cfg'


import pagure


def get_email_body(emailobj):
    ''' Return the body of the email, preferably in text.
    '''
    body = None
    if emailobj.is_multipart():
        for payload in emailobj.get_payload():
            body = payload.get_payload()
            if payload.get_content_type() == 'text/plain':
                break
    else:
        body = emailobj.get_payload()

    enc = emailobj['Content-Transfer-Encoding']
    if enc == 'base64':
        body = base64.decodestring(body)

    return body


def clean_item(item):
    ''' For an item provided as <item> return the content, if there are no
    <> then return the string.
    '''
    if '<' in item:
        item = item.split('<')[1]
    if '>' in item:
        item = item.split('>')[0]

    return item


class PagureMilter(Milter.Base):

    def __init__(self):  # A new instance with each new connection.
        self.id = Milter.uniqueID()  # Integer incremented with each call.
        self.fp = None

    def log(self, message):
        print(message)
        sys.stdout.flush()

    def envfrom(self, mailfrom, *str):
        self.log("mail from: %s  -  %s" % (mailfrom, str))
        self.fromparms = Milter.dictfromlist(str)
        # NOTE: self.fp is only an *internal* copy of message data.  You
        # must use addheader, chgheader, replacebody to change the message
        # on the MTA.
        self.fp = StringIO.StringIO()
        self.canon_from = '@'.join(parse_addr(mailfrom))
        self.fp.write('From %s %s\n' % (self.canon_from, time.ctime()))
        return Milter.CONTINUE

    @Milter.noreply
    def header(self, name, hval):
        ''' Headers '''
        # add header to buffer
        self.fp.write("%s: %s\n" % (name, hval))
        return Milter.CONTINUE

    @Milter.noreply
    def eoh(self):
        ''' End of Headers '''
        self.fp.write("\n")
        return Milter.CONTINUE

    @Milter.noreply
    def body(self, chunk):
        ''' Body '''
        self.fp.write(chunk)
        return Milter.CONTINUE

    @Milter.noreply
    def envrcpt(self, to, *str):
        rcptinfo = to, Milter.dictfromlist(str)
        print rcptinfo

        return Milter.CONTINUE

    def eom(self):
        ''' End of Message '''
        self.fp.seek(0)
        msg = email.message_from_file(self.fp)

        msg_id = msg.get('In-Reply-To', None)
        if msg_id is None:
            self.log('No In-Reply-To, keep going')
            return Milter.CONTINUE

        # Ensure we don't get extra lines in the message-id
        msg_id = msg_id.split('\n')[0].strip()

        self.log('msg-ig %s' % msg_id)
        self.log('To %s' % msg['to'])
        self.log('Cc %s' % msg.get('cc'))
        self.log('From %s' % msg['From'])

        # Ensure the user replied to his/her own notification, not that
        # they are trying to forge their ID into someone else's
        salt = pagure.APP.config.get('SALT_EMAIL')
        m = hashlib.sha512('%s%s%s' % (msg_id, salt, clean_item(msg['From'])))
        email_address = msg['to']
        if 'reply+' in msg.get('cc', ''):
            email_address = msg['cc']
        if not 'reply+' in email_address:
            self.log(
                'No valid recipient email found in To/Cc: %s'
                % email_address)
        tohash = email_address.split('@')[0].split('+')[-1]
        if m.hexdigest() != tohash:
            self.log('hash: %s' % m.hexdigest())
            self.log('tohash:   %s' % tohash)
            self.log('Hash does not correspond to the destination')
            return Milter.CONTINUE

        if msg['From'] and msg['From'] == pagure.APP.config.get('FROM_EMAIL'):
            self.log("Let's not process the email we send")
            return Milter.CONTINUE

        msg_id = clean_item(msg_id)

        if msg_id and '-ticket-' in msg_id:
            self.log('Processing issue')
            return self.handle_ticket_email(msg, msg_id)
        elif msg_id and '-pull-request-' in msg_id:
            self.log('Processing pull-request')
            return self.handle_request_email(msg, msg_id)
        else:
            self.log('Not a pagure ticket or pull-request email, let it go')
            return Milter.CONTINUE


    def handle_ticket_email(self, emailobj, msg_id):
        ''' Add the email as a comment on a ticket. '''
        uid  = msg_id.split('-ticket-')[-1].split('@')[0]
        parent_id = None
        if '-' in uid:
            uid, parent_id = uid.rsplit('-', 1)
        if '/' in uid:
            uid = uid.split('/')[0]
        self.log('uid %s' % uid)
        self.log('parent_id %s' % parent_id)

        data = {
            'objid': uid,
            'comment': get_email_body(emailobj),
            'useremail': clean_item(emailobj['From']),
        }
        url = pagure.APP.config.get('APP_URL')

        if url.endswith('/'):
            url = url[:-1]
        url = '%s/pv/ticket/comment/' % url
        req = requests.put(url, data=data)
        if req.status_code == 200:
            self.log('Comment added')
            return Milter.ACCEPT
        self.log('Could not add the comment to pagure')
        return Milter.CONTINUE

    def handle_request_email(self, emailobj, msg_id):
        ''' Add the email as a comment on a request. '''
        uid  = msg_id.split('-pull-request-')[-1].split('@')[0]
        parent_id = None
        if '-' in uid:
            uid, parent_id = uid.rsplit('-', 1)
        if '/' in uid:
            uid = uid.split('/')[0]
        self.log('uid %s' % uid)
        self.log('parent_id %s' % parent_id)

        data = {
            'objid': uid,
            'comment': get_email_body(emailobj),
            'useremail': clean_item(emailobj['From']),
        }
        url = pagure.APP.config.get('APP_URL')

        if url.endswith('/'):
            url = url[:-1]
        url = '%s/pv/pull-request/comment/' % url
        req = requests.put(url, data=data)

        return Milter.ACCEPT


def background():
    while True:
        t = logq.get()
        if not t: break
        msg,id,ts = t
        print "%s [%d]" % (time.strftime('%Y%b%d %H:%M:%S',time.localtime(ts)),id),
        # 2005Oct13 02:34:11 [1] msg1 msg2 msg3 ...
        for i in msg: print i,
        print


def main():
    bt = Thread(target=background)
    bt.start()
    socketname = "/var/run/pagure/paguresock"
    timeout = 600
    # Register to have the Milter factory create instances of your class:
    Milter.factory = PagureMilter
    print "%s pagure milter startup" % time.strftime('%Y%b%d %H:%M:%S')
    sys.stdout.flush()
    Milter.runmilter("paguremilter", socketname, timeout)
    logq.put(None)
    bt.join()
    print "%s pagure milter shutdown" % time.strftime('%Y%b%d %H:%M:%S')


if __name__ == "__main__":
    main()
