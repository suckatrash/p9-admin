from datetime import datetime
import json
import keystoneclient.v3
import keystoneauth1
import logging
import openstack
import os
import pf9_saml_auth
import sys

# Platform9 constants
ROLE_NAME = "_member_"
MAPPING_NAME = "idp1_mapping"
DOMAIN = "default"

class OpenStackClient(object):
    def __init__(self):
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
        self.keystone = keystoneclient.v3.client.Client(session=session)
        self.openstack = openstack.connect(session=session)

        try:
            self.service_project = self.keystone.projects.find(name="service")
        except keystoneauth1.exceptions.NotFound:
            logging.critical('Could not find project "service"')
            sys.exit(1)

        self.external_network = self.openstack.network.find_network("external",
            project_id=self.service_project.id)
        if self.external_network is None:
            logging.critical('Could not find network "external" in project "service"')
            sys.exit(1)

        self.ROLE = self.keystone.roles.find(name=ROLE_NAME)
        self._groups = None

    def groups(self):
        if self._groups == None:
            self._groups = self.keystone.groups.list()
            logging.info('Retrieved %d groups', len(self._groups))

        return self._groups

    def ensure_group(self, user):
        # Ensure that a group exists for a user
        if user.group:
            return group

        ### This optimizes for bulk add. Should we have a separate path when the number of users is <N?
        group_name = "User: {}".format(user.email)
        for group in self.groups():
            if group.name == group_name:
                user.logger.info('Found group "%s" [%s]', group.name, group.id)
                break
        else:
            group = self.keystone.groups.create(name=group_name, description=user.name)
            user.logger.info('Created group "%s" [%s]', group.name, group.id)
            self._groups.append(group)

        user.group = group
        return group

    def ensure_okta_mappings(self, users):
        # Map SAML email attribute to groups
        old_rules = self.keystone.federation.mappings.get(MAPPING_NAME).rules
        new_rules = []

        for user in users:
            for rule in old_rules:
                if check_rule(rule, user.email, user.group.id):
                    logging.info('Found mapping of "%s" to group [%s]',
                        user.email, user.group.id)
                    break
            else:
                new_rules.append(create_rule(user.email, user.group.id))
                logging.info('Adding mapping of "%s" to group [%s]',
                    user.email, user.group.id)

        if new_rules:
            backup = datetime.now().strftime("/tmp/rules_%Y-%m-%d_%H:%M:%S.json")
            with open(backup, "w") as file:
                file.write(json.dumps(old_rules, indent=2))
            logging.info("Old mappings backed up to %s", backup)

            self.keystone.federation.mappings.update(MAPPING_NAME,
                rules = old_rules + new_rules)
            logging.info("New mappings saved")
        else:
            logging.info("Mappings are already up to date")

    def ensure_project(self, user):
        # Default set up for projects
        NETWORK_NAME = "network1"
        SUBNET_NAME = "subnet0"
        SUBNET_CIDR="192.168.0.0/24"
        ROUTER_NAME = "router0"
        SECURITY_GROUP_NAME = "default"

        # Create project
        try:
            project = self.keystone.projects.find(name=user.name)
            user.logger.info('Found project "%s" [%s]', project.name, project.id)
            new_project = False
        except keystoneauth1.exceptions.NotFound:
            project = self.keystone.projects.create(name=user.name, domain=DOMAIN)
            user.logger.info('Created project "%s" [%s]', project.name, project.id)
            new_project = True

        # Assign group to project with role
        if not new_project and self.check_role_assignment(self.ROLE.id, group=user.group, project=project):
            user.logger.info('Found assignment to role "%s" [%s]',
                self.ROLE.name, self.ROLE.id)
        else:
            self.keystone.roles.grant(self.ROLE.id, group=user.group, project=project)
            user.logger.info('Granted access to role "%s" [%s]',
                self.ROLE.name, self.ROLE.id)

        # Create default network
        network = None
        if not new_project:
            network = self.find_network(user, project, NETWORK_NAME)
            new_network = False
        if not network:
            network = self.create_network(user, project, NETWORK_NAME)
            new_network = True

        # Create default subnet
        subnet = None
        if not new_network:
            subnet = self.find_subnet(user, project, network, SUBNET_NAME)
            new_subnet = False
        if not subnet:
            subnet = self.create_subnet(user, project, network, SUBNET_NAME, SUBNET_CIDR)
            new_subnet = True

        # Create default router to connect default subnet to external network
        ### FIXME should this add the router to the external network? what if
        ### it's already connected to a network? should this check all routers?
        ### if router.external_gateway_info or router.external_gateway_info["network_id"]
        router = None
        if not new_project:
            router = self.find_router(user, project, ROUTER_NAME)
        if not router:
            router = self.create_router(user, project, network, subnet, ROUTER_NAME)
            new_router = True

        ### FIXME it seems to create the default security group automatically.
        security_groups = self.openstack.network.security_groups(
            project_id=project.id, name=SECURITY_GROUP_NAME)
        for security_group in security_groups:
            user.logger.info('Found security group "%s" [%s]',
                security_group.name, security_group.id)
            break
        else:
            security_group = self.openstack.network.create_security_group(
                name=SECURITY_GROUP_NAME, project_id=project.id,
                description="Default security group")
            user.logger.info('Created security group "%s" [%s]',
                security_group.name, security_group.id)

        # Update default security group to allow external access
        ### Should we always correct the rules?
        sg_rule = None
        if not new_project:
            sg_rule = self.find_security_group_rule(user, security_group)
        if not sg_rule:
            sg_rule = self.create_security_group_rule(user, security_group)

    def find_network(self, user, project, name):
        networks = self.openstack.network.networks(project_id=project.id, name=name)
        for network in networks:
            user.logger.info('Found network "%s" [%s]', network.name, network.id)
            return network
        return None

    def create_network(self, user, project, name):
        network = self.openstack.network.create_network(
            project_id=project.id, name=name,
            description="Default network")
        user.logger.info('Created network "%s" [%s]',
            network.name, network.id)
        return network

    def find_subnet(self, user, project, network, name):
        subnets = self.openstack.network.subnets(
            project_id=project.id, network_id=network.id, name=name)
        for subnet in subnets:
            user.logger.info('Found subnet "%s" [%s]: %s',
                subnet.name, subnet.id, subnet.cidr)
            return subnet
        return None

    def create_subnet(self, user, project, network, name, cidr):
        subnet = self.openstack.network.create_subnet(
            project_id=project.id, network_id=network.id, name=name,
            ip_version=4, cidr=cidr, description="Default subnet")
        user.logger.info('Created subnet "%s" [%s]: %s',
            subnet.name, subnet.id, subnet.cidr)
        return subnet

    def find_router(self, user, project, name):
        routers = self.openstack.network.routers(project_id=project.id, name=name)
        for router in routers:
            user.logger.info('Found router "%s" [%s]', router.name, router.id)
            return router
        return None

    def create_router(self, user, project, network, subnet, name):
        router = self.openstack.network.create_router(
            project_id=project.id, name=name,
            description="Default router",
            external_gateway_info={"network_id": self.external_network.id})
        user.logger.info('Created router "%s" [%s]', router.name, router.id)

        port = self.openstack.network.create_port(
            project_id=project.id,
            network_id=network.id,
            fixed_ips=[
                {"subnet_id": subnet.id, "ip_address": subnet.gateway_ip}
            ])
        user.logger.info("Created port [%s] on tenant subnet", port.id)

        self.openstack.network.add_interface_to_router(
            router, subnet_id=subnet.id, port_id=port.id)
        user.logger.info("Added port to router")

        return router

    def find_security_group_rule(self, user, security_group):
        sg_rules = self.openstack.network.security_group_rules(
            security_group_id=security_group.id,
            direction="ingress",
            ethertype="IPv4")
        for sg_rule in sg_rules:
            if sg_rule.remote_ip_prefix == "0.0.0.0/0":
                user.logger.info('Found security group rule for "%s" [%s]',
                    sg_rule.remote_ip_prefix, sg_rule.id)
                return sg_rule
        return None

    def create_security_group_rule(self, user, security_group):
        sg_rule = self.openstack.network.create_security_group_rule(
            security_group_id=security_group.id,
            direction="ingress",
            ethertype="IPv4",
            remote_ip_prefix="0.0.0.0/0")
        user.logger.info('Created security group rule for "%s" [%s]',
            sg_rule.remote_ip_prefix, sg_rule.id)
        return sg_rule

    def check_role_assignment(self, role, group, project):
        try:
            if self.keystone.roles.check(role, group=group, project=project):
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
