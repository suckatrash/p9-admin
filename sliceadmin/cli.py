from __future__ import print_function
import click
from datetime import datetime
import json
import logging
import keystoneclient.v3
import keystoneauth1
import openstack
import os
import pf9_saml_auth
import sys

def set_up_logging(level=logging.WARNING):
    logging.captureWarnings(True)

    handler = logging.StreamHandler(stream=sys.stdout)
    try:
        import colorlog
        handler.setFormatter(colorlog.ColoredFormatter(
            "%(log_color)s%(name)s[%(processName)s]: %(message)s"))
    except ImportError:
        handler.setFormatter(logging.Formatter("%(name)s[%(processName)s]: %(message)s"))

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

@click.command()
@click.option("--verbose", "-v", default=False, is_flag=True)
@click.option("--debug", "-d", default=False, is_flag=True)
@click.argument("name")
@click.argument("email")
@click.version_option()
def cli(verbose, debug, name, email):
    if debug:
        set_up_logging(logging.DEBUG)
        openstack.enable_logging(debug=True)
    elif verbose:
        set_up_logging(logging.INFO)
        openstack.enable_logging()
    else:
        set_up_logging(logging.WARNING)

    auth = pf9_saml_auth.V3Pf9SamlOkta(
        auth_url=os.environ["OS_AUTH_URL"],
        username=os.environ["OS_USERNAME"],
        password=os.environ["OS_PASSWORD"],
        protocol="saml2",
        identity_provider="IDP1",
        project_name=os.environ["OS_PROJECT_NAME"],
        project_domain_name=os.environ["OS_PROJECT_DOMAIN_ID"],
    )

    session = keystoneauth1.session.Session(auth=auth)
    keystone = keystoneclient.v3.client.Client(session=session)
    conn = openstack.connect(session=session)

    ### FIXME
    ROLE_ID = "9fe2ff9ee4384b1894a90878d3e92bab"
    MAPPING_NAME = "idp1_mapping"
    DOMAIN = "default"

    # Create project
    try:
        project = keystone.projects.find(name=name)
        logging.info('Found project "%s" [%s]', project.name, project.id)
    except keystoneauth1.exceptions.NotFound:
        project = keystone.projects.create(name=name, domain=DOMAIN)
        logging.info('Created project "%s" [%s]', project.name, project.id)

    # Create group
    group_name = "User: {}".format(email)
    try:
        group = keystone.groups.find(name=group_name)
        logging.info('Found group "%s" [%s]', group.name, group.id)
    except keystoneauth1.exceptions.NotFound:
        group = keystone.groups.create(name=group_name, description=name)
        logging.info('Created group "%s" [%s]', group.name, group.id)

    # Assign group to project with role
    def role_check(keystone, role, group, project):
        try:
            if keystone.roles.check(ROLE_ID, group=group, project=project):
                return True
        except keystoneauth1.exceptions.http.NotFound:
            pass
        return False

    if role_check(keystone, ROLE_ID, group=group, project=project):
        logging.info("Found role assignment")
    else:
        keystone.roles.grant(ROLE_ID, group=group, project=project)
        logging.info("Granted access to role [%s]", ROLE_ID)

    # Map SAML email attribute to group
    mapping = keystone.federation.mappings.get(MAPPING_NAME)
    rules = mapping.rules

    for rule in rules:
        if check_rule(rule, email, group.id):
            logging.info("Found mapping of email to group")
            break
    else:
        backup = datetime.now().strftime("/tmp/rules_%Y-%m-%d_%H:%M:%S.json")
        with open(backup, "w") as file:
            file.write(json.dumps(rules, indent=2))

        rules.append(create_rule(email, group.id))
        logging.info("Adding mapping of email to group."
            " Old mappings backed up to %s", backup)

        keystone.federation.mappings.update(MAPPING_NAME, rules=rules)

def create_rule(email, group_id):
    return {
        'remote': [
            {'type': 'FirstName'},
            {'type': 'LastName'},
            {'type': 'Email', 'regex': False, 'any_one_of': [email]}
        ],
        'local': [
            {
                'group': {'id': group_id},
                'user': {'name': '{0} {1}'}
            }
        ]
    }

def check_rule(rule, email, group_id):
    """
    Check if a rule matches and email and group

    See create_rule() for an example of what a rule looks like.
    """

    for match in rule["remote"]:
        if match.get("type") == "Email" and email in match.get("any_one_of"):
            break
    else:
        return False

    for match in rule["local"]:
        if match.get("group", dict()).get("id") == group_id:
            return True

    return False
