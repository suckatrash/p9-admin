from __future__ import print_function
import click
import csv
import operator
import p9admin
import sys

@click.group()
def host():
    """Tools for hypervisors."""
    pass

@host.command()
@click.option("--format", "-f", default="table")
def list(format):
    """List hosts."""
    hosts = p9admin.OpenStackClient().openstack().list_hypervisors()
    hosts = sorted(hosts, key=operator.itemgetter("hypervisor_hostname"))

    if format == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(["host_id", "hostname", "state", "status"])
        for host in hosts:
            writer.writerow([
                host['OS-EXT-PF9-HYP-ATTR:host_id'],
                host['hypervisor_hostname'],
                host['state'],
                host['status'],
            ])
    elif format == "table":
        for host in hosts:
            print("{host_id}  {hypervisor_hostname:<55} {state:10} {status:10}" \
                .format(
                    host_id=host['OS-EXT-PF9-HYP-ATTR:host_id'],
                    **host.toDict()))
    else:
        sys.exit("Format must be csv or table")
