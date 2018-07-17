from __future__ import print_function
import click
import os
import p9admin
import pprint
import sys


@click.group()
def project():
    """Manage projects"""
    pass


@project.command()
@click.argument("name")
def ensure(name):
    """Ensure a project exists"""
    client = p9admin.OpenStackClient()
    project = p9admin.project.ensure_project(client, name)
    print('Project "{}" [{}]'.format(project.name, project.id))


@project.command()
@click.argument("name")
def show(name):
    """Show a project and the objects within"""
    p9admin.project.show_project(p9admin.OpenStackClient(), name)


@project.command("apply-quota")
@click.option("--project_name", "-p")
@click.option("--quota_name", "-n")
@click.option("--quota_value", "-v")
def apply_quota(project_name, quota_name, quota_value):
    """

    Apply a quota to a project

    quota_name is one of:

    instances
    ram
    cores
    fixed_ips
    floating_ips
    injected_file_content_bytes
    injected_file_path_bytes
    injected_files
    key_pairs
    metadata_items
    security_groups
    security_group_rules
    server_groups
    server_group_members
    networks
    subnets
    routers
    root_gb

    quota_value is a number, -1 for unlimited


    """
    client = p9admin.OpenStackClient()
    project = client.project_by_name(project_name)
    token = client.api_token()

    p9admin.validators.quota_name(quota_name)
    p9admin.validators.quota_value(quota_name, quota_value)

    p9admin.project.apply_quota(token, project.id, quota_name, quota_value)


@project.command("get-quota")
@click.option("--project_name", "-p")
def get_quota(project_name):
    """ Get a list of quotas for a project """
    client = p9admin.OpenStackClient()
    project = client.project_by_name(project_name)
    token = client.api_token()

    p9admin.project.get_quota(token, project.id)


@project.command()
def list():
    """ Get a list of projects """
    client = p9admin.OpenStackClient()
    projects = client.projects()

    for project in projects:
        print(project.name)


@project.command()
@click.argument("names", metavar="NAME [NAME ...]", nargs=-1)
def delete(names):
    """Delete project(s) and the objects within"""
    client = p9admin.OpenStackClient()
    for name in names:
        p9admin.project.delete_project(client, name)

@project.command("ensure-ldap")
@click.argument("name")
@click.option("--group-cn", metavar="CN",
    help="The name of the group in LDAP. Defaults to NAME.")
@click.option("--uid", "-u", envvar='puppetpass_username')
@click.option("--password", "-p",
    prompt=not os.environ.has_key('puppetpass_password'),
    hide_input=True,
    default=os.environ.get('puppetpass_password', None))
def ensure_ldap(name, group_cn, uid, password):
    """Ensure a project exists based on an LDAP group"""

    if not uid:
        sys.exit("You must specify --uid USER to connect to LDAP")

    if group_cn is None:
        group_cn = name

    client = p9admin.OpenStackClient()
    client.logger.info("Ensuring all users exist and have their own projects")

    ### FIXME this is common code with user.ensure_users
    p9Users = p9admin.user.get_ldap_group_users(group_cn, uid, password)
    if not p9Users:
        sys.exit("LDAP group {} doesn't contain any users".format(group_cn))

    for p9User in p9Users:
        project = p9admin.project.ensure_project(client, p9User.name)
        client.ensure_user(p9User, default_project=project)
        client.grant_project_access(project, user=p9User.user)

    client.logger.info("Ensuring group exists and has the correct members")
    group = client.ensure_group(name)
    users = [p9User.user for p9User in p9Users]
    client.ensure_group_members(group, users, keep_others=False)

    client.logger.info("Ensuring actual project exists")
    project = p9admin.project.ensure_project(client, name)
    client.grant_project_access(project, group=group)

    print('Project "{}" [{}]'.format(project.name, project.id))
