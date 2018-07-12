import click
import os
import p9admin
import p9admin.user
import sys

@click.group()
def saml():
    """Manage SAML users and groups"""
    pass

@saml.command("show-group")
@click.argument("email")
def show_group(email):
    """Show a group"""
    p9admin.OpenStackClient().saml().show_group(email)

@saml.command("delete-groups")
@click.argument("emails", nargs=-1)
def delete_groups(emails):
    """Delete groups"""
    p9admin.OpenStackClient().saml().delete_groups(emails)

@saml.command("ensure-user")
@click.argument("name")
@click.argument("email")
def ensure_user(name, email):
    """Ensure that an SAML user is all set up"""
    client = p9admin.OpenStackClient()

    user = p9admin.User(name, email)
    client.saml().ensure_group(user)
    client.saml().ensure_mappings([user])
    project = p9admin.project.ensure_project(client, user.name)
    client.grant_project_access(project, group=user.group)

@saml.command("ensure-ldap-users")
@click.argument("filter", metavar="LDAP-FILTER")
@click.option("--uid", "-u", envvar='puppetpass_username')
@click.option("--password", "-p",
    prompt=not os.environ.has_key('puppetpass_password'),
    hide_input=True,
    default=os.environ.get('puppetpass_password', None))
def ensure_ldap_users(filter, uid, password):
    """Ensure that SAML users are set up based on an LDAP filter"""
    if not uid:
        sys.exit("You must specify --uid USER to connect to LDAP")

    users = p9admin.user.get_ldap_users(filter, uid, password)
    if not users:
        return

    client = p9admin.OpenStackClient()
    for user in users:
        client.saml().ensure_group(user)

    client.saml().ensure_mappings(users)

    for user in users:
        project = p9admin.project.ensure_project(client, user.name)
        client.grant_project_access(project, group=user.group)
