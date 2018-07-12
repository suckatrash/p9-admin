from __future__ import print_function
import click
import p9admin

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

@project.command()
@click.argument("name")
def delete(name):
    """Delete a project and the objects within"""
    p9admin.project.delete_project(p9admin.OpenStackClient(), name)
