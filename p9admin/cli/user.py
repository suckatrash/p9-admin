from __future__ import print_function
import click
import logging
import os
import p9admin
import p9admin.user
import sys

@click.group()
def user():
    """Manage local users"""
    pass

@user.command("ensure-user")
@click.argument("name")
@click.argument("email")
def ensure_user(name, email):
    """Ensure that a local user is all set up"""
    client = p9admin.OpenStackClient()

    user = p9admin.User(name, email)
    project = p9admin.project.ensure_project(client, user.name)
    client.ensure_user(user, default_project=project)
    client.grant_project_access(project, user=user.user)

@user.command("ensure-ldap-users")
@click.argument("filter", metavar="LDAP-FILTER")
@click.option("--uid", "-u", envvar='puppetpass_username')
@click.option("--password", "-p",
    prompt=not os.environ.has_key('puppetpass_password'),
    hide_input=True,
    default=os.environ.get('puppetpass_password', None))
def ensure_ldap_users(filter, uid, password):
    """Ensure that local users are set up based on an LDAP filter"""
    if not uid:
        sys.exit("You must specify --uid USER to connect to LDAP")

    users = p9admin.user.get_ldap_users(filter, uid, password)
    if not users:
        return

    client = p9admin.OpenStackClient()

    for user in users:
        project = p9admin.project.ensure_project(client, user.name)
        client.ensure_user(user, default_project=project)
        client.grant_project_access(project, user=user.user)

@user.command("ensure-group")
@click.argument("name")
@click.argument("emails", nargs=-1)
@click.option("--keep-others/--remove-others", default=True)
def ensure_group(name, emails, keep_others):
    """Ensure that a group exists"""

    client = p9admin.OpenStackClient()
    group = client.ensure_group(name)

    users = []
    bad_emails = []
    for email in emails:
        user = client.find_user(email)
        if user is None:
            bad_emails.append(email)
        else:
            users.append(user)

    if bad_emails:
        sys.exit("Could not find the following users: {}".format(
            ", ".join(bad_emails)))

    client.ensure_group_members(group, users, keep_others=keep_others)

@user.command("grant-user")
@click.argument("email")
@click.argument("project")
@click.option("--admin/--member", default=False)
def grant_user(email, project, admin):
    """Grant a local user access to a project"""
    client = p9admin.OpenStackClient()

    user = client.find_user(email)
    if not user:
        sys.exit('User "{}" not found'.format(email))

    if admin:
        role_name = "admin"
    else:
        role_name = "_member_"

    client.grant_project_access(
        client.find_project(project), user=user, role_name=role_name)

@user.command("revoke-user")
@click.argument("email")
@click.argument("project")
@click.option("--admin/--member", default=False)
def revoke_user(email, project, admin):
    """Revoke a local user's access to a project"""
    client = p9admin.OpenStackClient()

    user = client.find_user(email)
    if not user:
        sys.exit('User "{}" not found'.format(email))

    if admin:
        role_name = "admin"
    else:
        role_name = "_member_"

    client.revoke_project_access(
        client.find_project(project), user=user, role_name=role_name)

@user.command("grant-group")
@click.argument("name")
@click.argument("project")
@click.option("--admin/--member", default=False)
def grant_group(name, project, admin):
    """Grant a group access to a project"""
    client = p9admin.OpenStackClient()

    group = client.find_group(name)
    if not group:
        sys.exit('Group "{}" not found'.format(name))

    if admin:
        role_name = "admin"
    else:
        role_name = "_member_"

    client.grant_project_access(
        client.find_project(project), group=group, role_name=role_name)

@user.command("revoke-group")
@click.argument("name")
@click.argument("project")
@click.option("--admin/--member", default=False)
def revoke_group(name, project, admin):
    """Revoke a group's access to a project"""
    client = p9admin.OpenStackClient()

    group = client.find_group(name)
    if not group:
        sys.exit('Group "{}" not found'.format(name))

    if admin:
        role_name = "admin"
    else:
        role_name = "_member_"

    client.revoke_project_access(
        client.find_project(project), group=group, role_name=role_name)


