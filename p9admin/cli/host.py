from __future__ import print_function
import click
import operator
import p9admin

@click.group()
def host():
    """Tools for hypervisors"""
    pass

@host.command()
def list():
    """List hosts"""
    hosts = p9admin.OpenStackClient().openstack().list_hypervisors()
    hosts = sorted(hosts, key=operator.itemgetter("hypervisor_hostname"))

    for host in hosts:
        print("{host_id}  {hypervisor_hostname:<55} {state:10} {status:10}" \
            .format(
                host_id=host['OS-EXT-PF9-HYP-ATTR:host_id'],
                **host.toDict()))
