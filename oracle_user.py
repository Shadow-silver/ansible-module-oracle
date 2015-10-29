#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = '''
---
module: oracle_user
short_description: Manage Oracle user accounts
description:
- Create, modify and drop Oracle user accounts
options:
  name:
    description: Account name
    required: true
  password:
    description: Password hash as in SYS.USER$.PASSWORD
  state:
    description: Account state
    required: False
    default: present
    choices: ["present", "absent", "locked", "unlocked"]
  oracle_host:
    description: Hostname or IP address of Oracle DB
    required: False
    default: 127.0.0.1
  oracle_port:
    description: Listener Port
    required: False
    default: 1521
  oracle_user:
    description: Account to connect as
    required: False
    default: SYSTEM
  oracle_pass:
    description: Password to be used to authenticate
    required: False
    default: manager
  oracle_service:
    description: Service name to connect to
    required: False
    default: ORCL
notes:
- Requires cx_Oracle
#version_added: "2.0"
author: "Thomas Krahn (@nosmoht)"
'''

try:
    import cx_Oracle
except ImportError:
    oracleclient_found = False
else:
    oracleclient_found = True


def createConnection(username, userpass, host, port, service):
    return cx_Oracle.connect('{username}/{userpass}@{host}:{port}/{service}'.format(username=username, userpass=userpass, host=host, port=port, service=service))


def executeSQL(con, sql):
    cur = con.cursor()
    try:
        cur.execute(sql)
    except cx_Oracle.DatabaseError as e:
        module.fail_json(msg='{sql}: {err}'.format(sql=sql, err=e))
    cur.close()


def getUser(con, name):
    data = None
    cur = con.cursor()
    try:
        cur.prepare('select u.default_tablespace,u.temporary_tablespace,s.password,u.account_status from dba_users u join sys.user$ s on (s.name = u.username) where s.name = :name')
        cur.execute(None, dict(name=name))
        row = cur.fetchone()
        if row:
            data = dict()
            data['name'] = name
            data['default_tablespace'] = row[0]
            data['temporary_tablespace'] = row[1]
            data['password'] = row[2]
            data['account_status'] = row[3]
        cur.close()
        return data
    except cx_Oracle.DatabaseError as e:
        module.fail_json(msg='Error: {err}'.format(err=str(e)))


def getCreateUserSQL(name, userpass, default_tablespace=None, temporary_tablespace=None, account_status=None):
    sql = "CREATE USER {name} IDENTIFIED BY VALUES '{userpass}'".format(
        name=name, userpass=userpass)
    if default_tablespace:
        sql = '{sql} DEFAULT TABLESPACE {default_tablespace}'.format(
            sql=sql, default_tablespace=default_tablespace)
    if temporary_tablespace:
        sql = '{sql} TEMPORARY TABLESPACE {temporary_tablespace}'.format(
            sql=sql, temporary_tablespace=temporary_tablespace)
    if account_status:
        sql = '{sql} ACCOUNT {account_status}'.format(
            sql=sql, account_status=account_status)
    return sql


def getDropUserSQL(name):
    sql = 'DROP USER "{name}" CASCADE'.format(name=name)
    return sql


def getUpdateUserSQL(name, userpass=None, default_tablespace=None, temporary_tablespace=None, account_status=None):
    sql = 'ALTER USER {name}'.format(name=name)
    if userpass:
        sql = "{sql} IDENTIFIED BY VALUES '{userpass}'".format(
            sql=sql, userpass=userpass)
    if default_tablespace:
        sql = '{sql} DEFAULT TABLESPACE {default_tablespace}'.format(
            sql=sql, default_tablespace=default_tablespace)
    if temporary_tablespace:
        sql = '{sql} TEMPORARY TABLESPACE {temporary_tablespace}'.format(
            sql=sql, temporary_tablespace=temporary_tablespace)
    return sql


def mapState(state):
    if state in ['present', 'unlocked']:
        return 'UNLOCK'
    return 'LOCK'


def mapAccountStatus(account_status):
    if account_status == 'OPEN':
        return ['present', 'unlocked']
    return 'locked'


def ensure(module, conn):
    changed = False
    sql = None

    name = module.params['name'].upper()
    password = module.params['password']
    state = module.params['state']
    default_tablespace = module.params['default_tablespace']
    temporary_tablespace = module.params['temporary_tablespace']

    user = getUser(conn, name)

    if not user:
        if state != 'absent':
            sql = getCreateUserSQL(name=name,
                                   userpass=password,
                                   default_tablespace=default_tablespace,
                                   temporary_tablespace=temporary_tablespace,
                                   account_status=mapState(state))
    else:
        if state == 'absent':
            sql = getDropUserSQL(name=name)
        elif state not in mapAccountStatus(user.get('account_status')):
            sql = getUpdateUserSQL(name=name, account_status=mapState(state))
        if password and user.get('password') != password:
            sql = getUpdateUserSQL(name=name, userpass=password)
        if default_tablespace and user.get('default_tablespace') != default_tablespace:
            sql = getUpdateUserSQL(
                name=name, default_tablespace=default_tablespace)
        if temporary_tablespace and user.get('temporary_tablespace') != temporary_tablespace:
            sql = getUpdateUserSQL(
                name=name, temporary_tablespace=temporary_tablespace)
    if sql:
        executeSQL(conn, sql)
        changed = True
    return changed, getUser(conn, name)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            password=dict(type='str', required=False),
            default_tablespace=dict(type='str', required=False),
            temporary_tablespace=dict(type='str', required=False),
            state=dict(type='str', default='present', choices=[
                       'present', 'absent', 'locked', 'unlocked']),
            oracle_host=dict(type='str', default='127.0.0.1'),
            oracle_port=dict(type='str', default='1521'),
            oracle_user=dict(type='str', default='SYSTEM'),
            oracle_pass=dict(type='str', default='manager'),
            oracle_service=dict(type='str', default='ORCL'),
        ),
    )

    if not oracleclient_found:
        module.fail_json(
            msg='cx_Oracle not found. Needs to be installed. See http://cx-oracle.sourceforge.net/')

    oracle_host = module.params['oracle_host']
    oracle_port = module.params['oracle_port']
    oracle_user = module.params['oracle_user']
    oracle_pass = module.params['oracle_pass']
    oracle_service = module.params['oracle_service']

    try:
        conn = createConnection(username=oracle_user, userpass=oracle_pass,
                                host=oracle_host, port=oracle_port, service=oracle_service)
    except cx_Oracle.DatabaseError as e:
        module.fail_json(msg='{0}'.format(str(e)))

    changed, user = ensure(module, conn)
    module.exit_json(changed=changed, user=user)

# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
