from __future__ import print_function
import functools
import keystoneclient.v3
import keystoneauth1
import logging
import openstack
import os
import p9admin
import sys

# Platform9 constants
ROLE_NAME = "_member_"

def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args):
        if args not in cache:
            cache[args] = obj(*args)
        return cache[args]
    return memoizer

def add_memo(obj, args, memo):
    obj.cache[args] = memo

class OpenStackClient(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

        if os.environ.get("OS_PROTOCOL", "password") == "SAML":
            self.logger.info('Authenticating as "%s" on project "%s" with SAML',
                os.environ["OS_USERNAME"], os.environ["OS_PROJECT_NAME"])
            auth = self.saml().auth()
        else:
            self.logger.info('Authenticating as "%s" on project "%s" with password',
                os.environ["OS_USERNAME"], os.environ["OS_PROJECT_NAME"])
            auth = keystoneauth1.identity.v3.Password(
                auth_url=os.environ["OS_AUTH_URL"],
                username=os.environ["OS_USERNAME"],
                password=os.environ["OS_PASSWORD"],
                user_domain_id=os.environ["OS_USER_DOMAIN_ID"],
                project_name=os.environ["OS_PROJECT_NAME"],
                project_domain_id=os.environ["OS_PROJECT_DOMAIN_ID"],
            )

        self.session = keystoneauth1.session.Session(auth=auth)

    @memoize
    def keystone(self):
        return keystoneclient.v3.client.Client(session=self.session)

    @memoize
    def openstack(self):
        return openstack.connect(session=self.session)

    @memoize
    def saml(self):
        return p9admin.SAML(self)

    @memoize
    def member_role(self):
        return self.keystone().roles.find(name=ROLE_NAME)

    @memoize
    def service_project(self):
        try:
            project = self.keystone().projects.find(name="service")
            self.logger.info('Found "%s" project [%s]', project.name, project.id)
        except keystoneauth1.exceptions.NotFound:
            self.logger.critical('Could not find project "service"')
            sys.exit(1)

        return project

    @memoize
    def external_network(self):
        name = "external"
        network = self.openstack().network.find_network(
            name, project_id=self.service_project().id)
        if network is None:
            self.logger.critical('Could not find network "%s" in project "%s"',
                name, self.service_project().name)
            sys.exit(1)

        return network

    @memoize
    def groups(self):
        groups = self.keystone().groups.list()
        self.logger.info('Retrieved %d groups', len(groups))
        return groups

    def subnets(self, *args, **kwargs):
        for subnet in self.openstack().network.subnets(*args, **kwargs):
            add_memo(self.subnet, (self, subnet.id), subnet)
            yield subnet

    @memoize
    def subnet(self, id):
        return self.openstack().network.get_subnet(id)

    def security_groups(self, *args, **kwargs):
        for sg in self.openstack().network.security_groups(*args, **kwargs):
            add_memo(self.security_group, (self, sg.id), sg)
            yield sg

    @memoize
    def security_group(self, id):
        return self.openstack().network.get_security_group(id)

    @memoize
    def all_volumes(self):
        return self.openstack().block_storage.volumes(details=True, all_tenants=True)

    def volumes(self, project_id):
        for volume in self.all_volumes():
            if volume.project_id == project_id:
                yield volume

    @memoize
    def all_servers(self):
        return self.openstack().compute.servers(details=True, all_tenants=True)

    def servers(self, project_id):
        for server in self.all_servers():
            if server.project_id == project_id:
                yield server

    def show_group(self, email):
        group = self.keystone().groups.find(name="User: {}".format(email))
        print('Group "{}" [{}]: {}'.format(group.name, group.id, group.description))
        for rule in self.saml().filter_mappings(email, group.id):
            print("  Rule")
            for match in rule["remote"]:
                m2 = match.copy()
                del(m2["type"])
                print("    {}: {}".format(match["type"], m2))

    def delete_group(self, email):
        group = self.keystone().groups.find(name="User: {}".format(email))
        self.saml().delete_mapping(email, group.id)
        self.keystone().groups.delete(group)
        self.logger.info('Deleted group "%s", [%s]', group.name, group.id)

    def ensure_group(self, user):
        # Ensure that a group exists for a user
        if user.group:
            return group

        ### This optimizes for bulk add. Should we have a separate path when the number of users is <N?
        group_name = "User: {}".format(user.email)
        for group in self.groups():
            if group.name == group_name:
                self.logger.info('Found group "%s" [%s]', group.name, group.id)
                break
        else:
            group = self.keystone().groups.create(name=group_name, description=user.name)
            self.logger.info('Created group "%s" [%s]', group.name, group.id)
            ### FIXME abstract memoization modification
            self.groups.cache[(self,)].append(group)

        user.group = group
        return group

    def find_network(self, project, name):
        networks = self.openstack().network.networks(project_id=project.id, name=name)
        for network in networks:
            self.logger.info('Found network "%s" [%s]', network.name, network.id)
            return network
        return None

    def create_network(self, project, name):
        network = self.openstack().network.create_network(
            project_id=project.id, name=name,
            description="Default network")
        self.logger.info('Created network "%s" [%s]', network.name, network.id)
        return network

    def find_subnet(self, project, network, name):
        subnets = self.openstack().network.subnets(
            project_id=project.id, network_id=network.id, name=name)
        for subnet in subnets:
            self.logger.info('Found subnet "%s" [%s]: %s',
                subnet.name, subnet.id, subnet.cidr)
            return subnet
        return None

    def create_subnet(self, project, network, name, cidr):
        subnet = self.openstack().network.create_subnet(
            project_id=project.id, network_id=network.id, name=name,
            ip_version=4, cidr=cidr, description="Default subnet")
        self.logger.info('Created subnet "%s" [%s]: %s',
            subnet.name, subnet.id, subnet.cidr)
        return subnet

    def find_router(self, project, name):
        routers = self.openstack().network.routers(project_id=project.id, name=name)
        for router in routers:
            self.logger.info('Found router "%s" [%s]', router.name, router.id)
            return router
        return None

    def create_router(self, project, network, subnet, name):
        router = self.openstack().network.create_router(
            project_id=project.id, name=name,
            description="Default router",
            external_gateway_info={"network_id": self.external_network().id})
        self.logger.info('Created router "%s" [%s]', router.name, router.id)

        port = self.openstack().network.create_port(
            project_id=project.id,
            network_id=network.id,
            fixed_ips=[
                {"subnet_id": subnet.id, "ip_address": subnet.gateway_ip}
            ])
        self.logger.info("Created port [%s] on tenant subnet", port.id)

        self.openstack().network.add_interface_to_router(
            router, subnet_id=subnet.id, port_id=port.id)
        self.logger.info("Added port to router")

        return router

    def find_security_group(self, project, name):
        security_groups = self.openstack().network.security_groups(
            project_id=project.id, name=name)
        for sg in security_groups:
            self.logger.info('Found security group "%s" [%s]', sg.name, sg.id)
            return sg
        return None

    def create_security_group(self, project, name):
        sg = self.openstack().network.create_security_group(
            name=name, project_id=project.id,
            description="Default security group")
        self.logger.info('Created security group "%s" [%s]', sg.name, sg.id)
        return sg

    def find_security_group_rule(self, security_group):
        sg_rules = self.openstack().network.security_group_rules(
            security_group_id=security_group.id,
            direction="ingress",
            ethertype="IPv4")
        for sg_rule in sg_rules:
            if sg_rule.remote_ip_prefix == "0.0.0.0/0":
                self.logger.info('Found security group rule for "%s" [%s]',
                    sg_rule.remote_ip_prefix, sg_rule.id)
                return sg_rule
        return None

    def create_security_group_rule(self, security_group):
        sg_rule = self.openstack().network.create_security_group_rule(
            security_group_id=security_group.id,
            direction="ingress",
            ethertype="IPv4",
            remote_ip_prefix="0.0.0.0/0")
        self.logger.info('Created security group rule for "%s" [%s]',
            sg_rule.remote_ip_prefix, sg_rule.id)
        return sg_rule

    def assign_group_to_project(self, group, project):
        # Assign group to project with role
        role = self.member_role()
        if self.check_role_assignment(role.id, group=group, project=project):
            self.logger.info('Found assignment to role "%s" [%s]', role.name, role.id)
        else:
            self.keystone().roles.grant(role.id, group=group, project=project)
            self.logger.info('Granted access to role "%s" [%s]', role.name, role.id)

    def check_role_assignment(self, role, group, project):
        try:
            if self.keystone().roles.check(role, group=group, project=project):
                return True
        except keystoneauth1.exceptions.http.NotFound:
            pass
        return False

    def find_project(self, name):
        try:
            return self.keystone().projects.find(name=name)
        except keystoneauth1.exceptions.NotFound:
            # Maybe the name is an ID?
            try:
                return self.keystone().projects.get(name)
            except keystoneauth1.exceptions.http.NotFound:
                sys.exit('Could not find project with name or ID "%s"' % name)