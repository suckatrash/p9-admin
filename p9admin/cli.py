from __future__ import print_function
import click
import logging
import openstack
import os
import p9admin
import sys

def set_up_logging(level=logging.WARNING):
    logging.captureWarnings(True)

    format = "%(relativeCreated)7d %(name)s: %(message)s"

    handler = logging.StreamHandler(stream=sys.stdout)
    try:
        import colorlog
        handler.setFormatter(colorlog.ColoredFormatter("%(log_color)s" + format))
    except ImportError:
        handler.setFormatter(logging.Formatter(format))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

def main():
    try:
        cli(standalone_mode=False)
    except click.ClickException as e:
        e.show()
        sys.exit(e.exit_code)
    except click.Abort as e:
        sys.exit(e)

@click.group()
@click.option("--verbose", "-v", default=False, is_flag=True)
@click.option("--debug", "-d", default=False, is_flag=True)
@click.version_option()
def cli(verbose, debug, ):
    if debug:
        set_up_logging(logging.DEBUG)
        openstack.enable_logging(debug=True, http_debug=True)
    elif verbose:
        set_up_logging(logging.INFO)
        openstack.enable_logging()
    else:
        set_up_logging(logging.WARNING)

@cli.command("repl")
def repl():
    """Drop into interactive Python REPL"""
    client = p9admin.OpenStackClient()

    import code
    vars = globals().copy()
    vars.update(locals())
    code.interact(local=vars)

@cli.command("show-group")
@click.argument("email")
def show_group(email):
    """Show a group"""
    p9admin.OpenStackClient().show_group(email)

@cli.command("delete-group")
@click.argument("email")
def delete_group(email):
    """Delete a group"""
    p9admin.OpenStackClient().delete_group(email)

@cli.group()
def project():
    """Commands to manage projects"""
    pass

@project.command("ensure")
@click.argument("name")
def project_ensure(name):
    """Ensure a project exists"""
    client = p9admin.OpenStackClient()
    project = p9admin.project.ensure_project(client, name)
    print('Project "{}" [{}]'.format(project.name, project.id))

@project.command("show")
@click.argument("name")
def project_show(name):
    """Show a project and the objects within"""
    p9admin.project.show_project(p9admin.OpenStackClient(), name)

@project.command("delete")
@click.argument("name")
def project_delete(name):
    """Delete a project and the objects within"""
    p9admin.project.delete_project(p9admin.OpenStackClient(), name)

@cli.command("ensure-user")
@click.argument("name")
@click.argument("email")
def ensure_user(name, email):
    """Ensure that a local user is all set up"""
    client = p9admin.OpenStackClient()

    user = p9admin.User(name, email)
    project = p9admin.project.ensure_project(client, user.name)
    client.ensure_user(user, default_project=project)
    client.grant_project_access(project, user=user.user)

@cli.command("ensure-ldap-users")
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

    users = get_ldap_users(filter, uid, password)
    if not users:
        return

    client = p9admin.OpenStackClient()

    for user in users:
        project = p9admin.project.ensure_project(client, user.name)
        client.ensure_user(user, default_project=project)
        client.grant_project_access(project, user=user.user)

@cli.command()
@click.argument("email")
@click.argument("project")
@click.option("--admin/--member", default=False)
def grant(email, project, admin):
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

@cli.command()
@click.argument("email")
@click.argument("project")
@click.option("--admin/--member", default=False)
def revoke(email, project, admin):
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

@cli.command("ensure-okta-user")
@click.argument("name")
@click.argument("email")
def ensure_okta_user(name, email):
    """Ensure that an Okta user is all set up"""
    client = p9admin.OpenStackClient()

    user = p9admin.User(name, email)
    client.ensure_group(user)
    client.saml().ensure_mappings([user])
    project = p9admin.project.ensure_project(client, user.name)
    client.assign_group_to_project(user.group, project)

@cli.command("ensure-ldap-okta-users")
@click.argument("filter", metavar="LDAP-FILTER")
@click.option("--uid", "-u", envvar='puppetpass_username')
@click.option("--password", "-p",
    prompt=not os.environ.has_key('puppetpass_password'),
    hide_input=True,
    default=os.environ.get('puppetpass_password', None))
def ensure_ldap_okta_users(filter, uid, password):
    """Ensure that Okta users are set up based on an LDAP filter"""
    if not uid:
        sys.exit("You must specify --uid USER to connect to LDAP")

    users = get_ldap_users(filter, uid, password)
    if not users:
        return

    client = p9admin.OpenStackClient()
    for user in users:
        client.ensure_group(user)

    client.saml().ensure_mappings(users)

    for user in users:
        project = p9admin.project.ensure_project(client, user.name)
        client.assign_group_to_project(user.group, project)

def get_ldap_users(filter, uid, password):
    USERS_DN = "ou=users,dc=puppetlabs,dc=com"
    LDAP_URL = "ldap://ldap.puppetlabs.com"

    # LDAP is a pain to build. Don't fail unless we're actually using it.
    import ldap

    bind_dn = "uid={},{}".format(uid, USERS_DN)
    client = ldap.initialize(LDAP_URL)
    client.start_tls_s()
    count = 1

    try:
        try:
            client.simple_bind_s(bind_dn, password)
        except ldap.LDAPError as e:
            logging.critical("Could not bind to LDAP server '{}' as '{}': {}"
                .format(LDAP_URL, bind_dn, e))
            sys.exit(1)

        users = client.search_st(USERS_DN, ldap.SCOPE_SUBTREE, filter,
            attrlist=["cn", "mail"], timeout=60)
        if len(users) == 0:
            logging.warn('Found 0 users in LDAP for filter "%s"', filter)
            return []

        logging.info('Found %d users in LDAP for filter "%s"',
            len(users), filter)

        user_objects = []
        for dn, attrs in users:
            cns = attrs.get("cn", list())
            mails = attrs.get("mail", list())

            if not cns:
                logging.error("Skipping %s: no cn attribute", dn)
                continue
            if not mails:
                logging.error("Skipping %s: no mail attribute", dn)
                continue

            if len(cns) > 1:
                logging.warn("%s has %d cn values", dn, len(mails))
            if len(mails) > 1:
                logging.warn("%s has %d mail values", dn, len(mails))

            user_objects.append(p9admin.User(cns[0], mails[0], number=count))
            count += 1

        return user_objects
    finally:
        client.unbind()
