from __future__ import print_function
import functools
import keystoneclient.v3
import keystoneauth1
import logging
import openstack
import operator
import os
import p9admin
import sys

# Platform9 constants
ROLE_NAME = "_member_"
DOMAIN = "default"

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
        if os.environ.get("OS_PROTOCOL", "password") == "SAML":
            logging.info('Authenticating as "%s" on project "%s" with SAML',
                os.environ["OS_USERNAME"], os.environ["OS_PROJECT_NAME"])
            auth = self.saml().auth()
        else:
            logging.info('Authenticating as "%s" on project "%s" with password',
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
            logging.info('Found "%s" project [%s]', project.name, project.id)
        except keystoneauth1.exceptions.NotFound:
            logging.critical('Could not find project "service"')
            sys.exit(1)

        return project

    @memoize
    def external_network(self):
        name = "external"
        network = self.openstack().network.find_network(
            name, project_id=self.service_project().id)
        if network is None:
            logging.critical('Could not find network "%s" in project "%s"',
                name, self.service_project().name)
            sys.exit(1)

        return network

    @memoize
    def groups(self):
        groups = self.keystone().groups.list()
        logging.info('Retrieved %d groups', len(groups))
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
        logging.info('Deleted group "%s", [%s]', group.name, group.id)

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
            group = self.keystone().groups.create(name=group_name, description=user.name)
            user.logger.info('Created group "%s" [%s]', group.name, group.id)
            ### FIXME abstract memoization modification
            self.groups.cache[(self,)].append(group)

        user.group = group
        return group

    def ensure_project(self, user):
        # Default set up for projects
        NETWORK_NAME = "network1"
        SUBNET_NAME = "subnet0"
        SUBNET_CIDR="192.168.0.0/24"
        ROUTER_NAME = "router0"
        SECURITY_GROUP_NAME = "default"

        # Create project
        try:
            project = self.keystone().projects.find(name=user.name)
            user.logger.info('Found project "%s" [%s]', project.name, project.id)
            new_project = False
        except keystoneauth1.exceptions.NotFound:
            project = self.keystone().projects.create(name=user.name, domain=DOMAIN)
            user.logger.info('Created project "%s" [%s]', project.name, project.id)
            new_project = True

        # Assign group to project with role
        if not new_project and self.check_role_assignment(
                self.member_role().id, group=user.group, project=project):
            user.logger.info('Found assignment to role "%s" [%s]',
                self.member_role().name, self.member_role().id)
        else:
            self.keystone().roles.grant(
                self.member_role().id, group=user.group, project=project)
            user.logger.info('Granted access to role "%s" [%s]',
                self.member_role().name, self.member_role().id)

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
        security_groups = self.openstack().network.security_groups(
            project_id=project.id, name=SECURITY_GROUP_NAME)
        for security_group in security_groups:
            user.logger.info('Found security group "%s" [%s]',
                security_group.name, security_group.id)
            break
        else:
            security_group = self.openstack().network.create_security_group(
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
        networks = self.openstack().network.networks(project_id=project.id, name=name)
        for network in networks:
            user.logger.info('Found network "%s" [%s]', network.name, network.id)
            return network
        return None

    def create_network(self, user, project, name):
        network = self.openstack().network.create_network(
            project_id=project.id, name=name,
            description="Default network")
        user.logger.info('Created network "%s" [%s]',
            network.name, network.id)
        return network

    def find_subnet(self, user, project, network, name):
        subnets = self.openstack().network.subnets(
            project_id=project.id, network_id=network.id, name=name)
        for subnet in subnets:
            user.logger.info('Found subnet "%s" [%s]: %s',
                subnet.name, subnet.id, subnet.cidr)
            return subnet
        return None

    def create_subnet(self, user, project, network, name, cidr):
        subnet = self.openstack().network.create_subnet(
            project_id=project.id, network_id=network.id, name=name,
            ip_version=4, cidr=cidr, description="Default subnet")
        user.logger.info('Created subnet "%s" [%s]: %s',
            subnet.name, subnet.id, subnet.cidr)
        return subnet

    def find_router(self, user, project, name):
        routers = self.openstack().network.routers(project_id=project.id, name=name)
        for router in routers:
            user.logger.info('Found router "%s" [%s]', router.name, router.id)
            return router
        return None

    def create_router(self, user, project, network, subnet, name):
        router = self.openstack().network.create_router(
            project_id=project.id, name=name,
            description="Default router",
            external_gateway_info={"network_id": self.external_network().id})
        user.logger.info('Created router "%s" [%s]', router.name, router.id)

        port = self.openstack().network.create_port(
            project_id=project.id,
            network_id=network.id,
            fixed_ips=[
                {"subnet_id": subnet.id, "ip_address": subnet.gateway_ip}
            ])
        user.logger.info("Created port [%s] on tenant subnet", port.id)

        self.openstack().network.add_interface_to_router(
            router, subnet_id=subnet.id, port_id=port.id)
        user.logger.info("Added port to router")

        return router

    def find_security_group_rule(self, user, security_group):
        sg_rules = self.openstack().network.security_group_rules(
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
        sg_rule = self.openstack().network.create_security_group_rule(
            security_group_id=security_group.id,
            direction="ingress",
            ethertype="IPv4",
            remote_ip_prefix="0.0.0.0/0")
        user.logger.info('Created security group rule for "%s" [%s]',
            sg_rule.remote_ip_prefix, sg_rule.id)
        return sg_rule

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

    def show_project(self, name):
        ### FIXME: images?
        project = self.find_project(name)
        print('Project "{}" [{}]'.format(project.name, project.id))

        network_client = self.openstack().network
        networks = network_client.networks(project_id=project.id)
        for network in networks:
            print('  Network "{}" [{}]'.format(network.name, network.id))
            subnets = self.subnets(project_id=project.id, network_id=network.id)
            for subnet in subnets:
                print('    Subnet "{}" [{}] {}'.format(subnet.name, subnet.id, subnet.cidr))

        routers = network_client.routers(project_id=project.id)
        for router in routers:
            print('  Router "{}" [{}]'.format(router.name, router.id))
            for port in network_client.ports(device_id=router.id):
                print("    Port {} [{}]".format(port.device_owner, port.id))
                self.print_fixed_ips(port.fixed_ips)

        for sg in self.security_groups(project_id=project.id):
            print('  Security group "{}" [{}]'.format(sg.name, sg.id))

            sort_key_func = operator.attrgetter(
                "direction", "ether_type", "protocol", "remote_group_id",
                "remote_ip_prefix", "port_range_min", "port_range_max")

            sg_rules = network_client.security_group_rules(security_group_id=sg.id)
            for sg_rule in sorted(sg_rules, key=sort_key_func):
                self.print_security_group_rule(sg_rule)

        for volume in self.volumes(project_id=project.id):
            print('  Volume "{}" [{}] {} GB, {}'.format(
                volume.name, volume.id, volume.size, volume.status))

        for server in self.servers(project_id=project.id):
            print('  Server "{}" [{}] {}'.format(
                server.name, server.id, server.status))

    def print_fixed_ips(self, fixed_ips):
        for ip in fixed_ips:
            subnet = self.subnet(ip["subnet_id"])
            print("      {} ({})".format(ip["ip_address"], subnet.name))

    def print_security_group_rule(self, rule):
        if rule.direction == "egress":
            direction = "to"
        elif rule.direction == "ingress":
            direction = "from"
        else:
            direction = rule.direction

        if rule.remote_group_id:
            remote = "<{}>".format(self.security_group(rule.remote_group_id).name)
        elif rule.remote_ip_prefix:
            remote = rule.remote_ip_prefix
        else:
            remote = "everywhere"

        if rule.protocol == None:
            protocol = "all"
        else:
            protocol = rule.protocol

        if rule.port_range_min == None:
            port_range = "all ports"
        elif rule.port_range_min == rule.port_range_max:
            port_range = "port {}".format(rule.port_range_min)
        else:
            port_range = "ports {}-{}".format(rule.port_range_min, rule.port_range_max)

        print("    {} {} {} {} on {}".format(
            rule.ether_type, protocol, direction, remote,
            port_range))

    def delete_project(self, name):
        ### FIXME: images?
        project = self.find_project(name)
        logging.info('Started deleting project "%s" [%s]', project.name, project.id)

        for server in self.servers(project_id=project.id):
            self.openstack().compute.delete_server(server, force=True, ignore_missing=True)
            logging.info('  Deleted server "%s" [%s]', server.name, server.id)

        for volume in self.volumes(project_id=project.id):
            self.openstack().block_storage.delete_volume(volume, ignore_missing=True)
            logging.info('  Deleted volume "%s" [%s]', volume.name, volume.id)

        network_client = self.openstack().network
        routers = network_client.routers(project_id=project.id)
        for router in routers:
            logging.info('  Started deleting router "%s" [%s]', router.name, router.id)
            for port in network_client.ports(device_id=router.id):
                network_client.remove_interface_from_router(router, port_id=port.id)
                logging.info("    Removed port %s [%s]", port.device_owner, port.id)
            network_client.delete_router(router, ignore_missing=True)
            logging.info('    Finished deleting router')

        networks = network_client.networks(project_id=project.id)
        for network in networks:
            logging.info('  Started deleting network "%s" [%s]', network.name, network.id)
            subnets = self.subnets(project_id=project.id, network_id=network.id)
            for subnet in subnets:
                network_client.delete_subnet(subnet, ignore_missing=True)
                logging.info('    Deleted subnet "%s" [%s]', subnet.name, subnet.id)
            network_client.delete_network(network, ignore_missing=True)
            logging.info('    Finished deleting network')

        # The default security group is recreating when it's deleted, so we have
        # to delete the project first.
        security_groups = list(self.security_groups(project_id=project.id))

        self.keystone().projects.delete(project)
        logging.info('  Deleted project itself')

        for sg in security_groups:
            network_client.delete_security_group(sg, ignore_missing=True)
            logging.info('  Deleted security group "%s" [%s]', sg.name, sg.id)

        logging.info('  Finished deleting project')
