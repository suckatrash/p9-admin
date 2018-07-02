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

# Platform9 constants
ROLE_NAME = "_member_"
MAPPING_NAME = "idp1_mapping"
DOMAIN = "default"

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

    ROLE = keystone.roles.find(name=ROLE_NAME)

    # Puppet user default set up
    NETWORK_NAME = "network1"
    SUBNET_NAME = "subnet0"
    SUBNET_CIDR="192.168.0.0/24"
    ROUTER_NAME = "router0"
    SECURITY_GROUP_NAME = "default"

    try:
        service_project = keystone.projects.find(name="service")
    except keystoneauth1.exceptions.NotFound:
        logging.critical('Could not find project "service"')
        sys.exit(1)

    external_network = conn.network.find_network("external",
        project_id=service_project.id)
    if external_network is None:
        logging.critical('Could not find network "external" in project "service"')
        sys.exit(1)

    group = ensure_group(keystone, email, name)

    # Create project
    try:
        project = keystone.projects.find(name=name)
        logging.info('Found project "%s" [%s]', project.name, project.id)
    except keystoneauth1.exceptions.NotFound:
        project = keystone.projects.create(name=name, domain=DOMAIN)
        logging.info('Created project "%s" [%s]', project.name, project.id)

    # Assign group to project with role
    if check_role_assignment(keystone, ROLE.id, group=group, project=project):
        logging.info('Found assignment to role "%s" [%s]', ROLE.name, ROLE.id)
    else:
        keystone.roles.grant(ROLE.id, group=group, project=project)
        logging.info('Granted access to role "%s" [%s]', ROLE.name, ROLE.id)

    # Create default network
    networks = conn.network.networks(project_id=project.id, name=NETWORK_NAME)
    for network in networks:
        logging.info('Found network "%s" [%s]', network.name, network.id)
        break
    else:
        network = conn.network.create_network(
            project_id=project.id, name=NETWORK_NAME,
            description="Default network")
        logging.info('Created network "%s" [%s]', network.name, network.id)

    # Create default subnet
    subnets = conn.network.subnets(
        project_id=project.id, network_id=network.id, name=SUBNET_NAME)
    for subnet in subnets:
        logging.info('Found subnet "%s" [%s]: %s', subnet.name, subnet.id, subnet.cidr)
        break
    else:
        subnet = conn.network.create_subnet(
            project_id=project.id, network_id=network.id, name=SUBNET_NAME,
            ip_version=4, cidr=SUBNET_CIDR, description="Default subnet")
        logging.info('Created subnet "%s" [%s]: %s', subnet.name, subnet.id, subnet.cidr)

    # Create default router to connect default subnet to external network
    routers = conn.network.routers(project_id=project.id, name=ROUTER_NAME)
    for router in routers:
        logging.info('Found router "%s" [%s]', router.name, router.id)
        ### FIXME should this add the router to the external network? what if
        ### it's already connected to a network? should this check all routers?
        ### if router.external_gateway_info or router.external_gateway_info["network_id"]
        break
    else:
        router = conn.network.create_router(
            project_id=project.id, name=ROUTER_NAME,
            description="Default router",
            external_gateway_info={"network_id": external_network.id})
        logging.info('Created router "%s" [%s]', router.name, router.id)

        port = conn.network.create_port(
            project_id=project.id,
            network_id=network.id,
            fixed_ips=[
                {"subnet_id": subnet.id, "ip_address": subnet.gateway_ip}
            ])
        logging.info("Created port [%s] on tenant subnet", port.id)

        conn.network.add_interface_to_router(
            router, subnet_id=subnet.id, port_id=port.id)
        logging.info("Added port to router")

    # Update default security group to allow external access
    security_groups = conn.network.security_groups(
        project_id=project.id, name=SECURITY_GROUP_NAME)
    for security_group in security_groups:
        logging.info('Found security group "%s" [%s]',
            security_group.name, security_group.id)
        break
    else:
        security_group = conn.network.create_security_group(
            name=SECURITY_GROUP_NAME, project_id=project.id,
            description="Default security group")
        logging.info('Created security group "%s" [%s]',
            security_group.name, security_group.id)

    ### FIXME it seems to create the default security group automatically.
    ### Should we just always correct the rules?
    sg_rules = conn.network.security_group_rules(
        security_group_id=security_group.id,
        direction="ingress",
        ethertype="IPv4")
    for sg_rule in sg_rules:
        if sg_rule.remote_ip_prefix == "0.0.0.0/0":
            logging.info('Found security group rule for "%s" [%s]',
                sg_rule.remote_ip_prefix, sg_rule.id)
            break
    else:
        sg_rule = conn.network.create_security_group_rule(
            security_group_id=security_group.id,
            direction="ingress",
            ethertype="IPv4",
            remote_ip_prefix="0.0.0.0/0")
        logging.info('Created security group rule for "%s" [%s]',
                sg_rule.remote_ip_prefix, sg_rule.id)

def ensure_group(keystone, email, name):
    group_name = "User: {}".format(email)
    try:
        group = keystone.groups.find(name=group_name)
        logging.info('Found group "%s" [%s]', group.name, group.id)
    except keystoneauth1.exceptions.NotFound:
        group = keystone.groups.create(name=group_name, description=name)
        logging.info('Created group "%s" [%s]', group.name, group.id)

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

    return group

def check_role_assignment(keystone, role, group, project):
    try:
        if keystone.roles.check(role, group=group, project=project):
            return True
    except keystoneauth1.exceptions.http.NotFound:
        pass
    return False

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
