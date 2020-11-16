#!/usr/bin/env python

# Copyright (c) 2015, Thomas Oulevey <thomas.oulevey@cern.ch>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND  ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# This script reads from a file, group information generated by FAS and sync
# it with koji
# No command line argument, options are hardcoded at this time.

import koji
import os.path
import sys
from collections import defaultdict

KOJI_URL = '{{ koji_hub_url }}'
CLIENT_CERT = os.path.expanduser('/etc/pki/koji/{{ koji_admin_pem }}')
CLIENTCA_CERT = os.path.expanduser('/etc/pki/koji/{{ koji_hub_cacert }}')
SERVERCA_CERT = os.path.expanduser('/etc/pki/ca-trust/extracted/openssl/ca-bundle.trust.crt')
USER = '{{ koji_admin_user }}'
FASDUMP = '/etc/bsadmin/groups'
SYSTEM_USERS = ['{{ koji_admin_user }}', 'kojira']
IMAGE_PERM = ['virt', 'cloud', 'atomic', 'cloudinstance']

def get_user_list():
    users = [(x['name'], x['id']) for x in kojiclient.listUsers()]
    return users if len(users) else None

def get_user(user):
    user = kojiclient.getUser(user)
    return user

def get_user_perms(user):
    perms = kojiclient.getUserPerms(user[1])
    return perms

def get_users_perms():
    userlist = defaultdict(list)
    for user in get_user_list():
        userlist[user[0]] = get_user_perms(user)

    return userlist if len(userlist) else None

def get_user_perms_from_file(user):
    perms = get_users_perms_from_file()
    return perms[user]

def get_all_defined_perms():
    perms = []
    for perm in kojiclient.getAllPerms():
        perms.append(perm['name'])
    return perms

def get_users_perms_from_file():
    userlist = defaultdict(list)
    try:
        groups = open(FASDUMP, 'r')
    except:
        return None

    for line in groups.readlines():
        sig, users = line.strip('\n').split(':')
        for user in users.replace(" ", "").split(','):
            perm = "build-"+sig
            userlist[user].append(perm)
            userlist[user].append('build')
            if sig in IMAGE_PERM:
                userlist[user].append('image')

    return userlist if len(userlist) else None

def fix_permissions(new, old):
    usernames = list(set(new)|set(old))
    # Do not touch system users
    usernames = [u for u in usernames if u not in SYSTEM_USERS]
    for username in usernames:
        togrant = list(set(new[username]) - set(old[username]))
        torevoke = list(set(old[username]) - set(new[username]))
        user = get_user(username)
        if togrant or torevoke:
            print "\n# user:%s\n# NEW perms:%s\n# OLD perms:%s \
                  \n# To grant:%s\n# To revoke:%s" \
                  % (user, new[username], old[username], togrant, torevoke)
        if not user:
            # Create user if it doesn't exist yet
            user = kojiclient.createUser(username)
            # Always grant "build" permission for building from srpm
            kojiclient.grantPermission(username, 'build')
        for perm in togrant:
            if perm in get_all_defined_perms():
                kojiclient.grantPermission(username, perm)
        for perm in torevoke:
            if perm in get_all_defined_perms():
                kojiclient.revokePermission(username, perm)

if __name__ == '__main__':
    try:
        kojiclient = koji.ClientSession(KOJI_URL)
        kojiclient.ssl_login(CLIENT_CERT, CLIENTCA_CERT, SERVERCA_CERT)
    except:
        print "Could not connect to koji API"
        sys.exit(2)

    fas_perms = get_users_perms_from_file()
    koji_perms = get_users_perms()

    if not fas_perms:
        print "Could not read %s file." % FASDUMP
        sys.exit(1)

    if not koji_perms:
        print "Could not read koji's user database"
        sys.exit(2)

    fix_permissions(fas_perms, koji_perms)
    sys.exit(0)
