from __future__ import print_function
import click
import os
import p9admin
import p9admin.user
import sys


@click.group()
def user():
    """Manage local users"""
    pass


def role_name(is_admin):
    if is_admin:
        return "admin"
    return "_member_"


@user.command("ensure-user")
@click.argument("name")
@click.argument("email")
def ensure_user(name, email):
    """Ensure that a local user is all set up"""
    client = p9admin.OpenStackClient()
    client.ensure_users([p9admin.User(name, email)])


@user.command("ensure-ldap-users")
@click.argument("filter", metavar="LDAP-FILTER")
@click.option("--uid", "-u", envvar='puppetpass_username')
@click.option("--password", "-p",
              prompt='puppetpass_password' not in os.environ,
              hide_input=True,
              default=os.environ.get('puppetpass_password', None))
def ensure_ldap_users(filter, uid, password):
    """Ensure that local users are set up based on an LDAP filter"""
    if not uid:
        sys.exit("You must specify --uid USER to connect to LDAP")

    client = p9admin.OpenStackClient()

    users = p9admin.user.get_ldap_users(filter, uid, password)
    client.ensure_users(users)


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

    client.grant_project_access(
        client.find_project(project), user=user, role_name=role_name(admin))


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

    client.revoke_project_access(
        client.find_project(project), user=user, role_name=role_name(admin))
