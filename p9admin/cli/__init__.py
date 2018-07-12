import click
import logging
import openstack
import p9admin
import sys

def add_command_group(module):
    for attr in dir(module):
        object = getattr(module, attr)
        if object.__class__ == click.core.Group:
            cli.add_command(object)

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
@click.option("--openstack-debug", default=False, is_flag=True)
@click.version_option()
def cli(verbose, debug, openstack_debug):
    if debug:
        set_up_logging(logging.INFO)
        openstack.enable_logging()
        logging.getLogger("p9admin").setLevel(logging.DEBUG)
    elif verbose:
        set_up_logging(logging.INFO)
        openstack.enable_logging()
    else:
        set_up_logging(logging.WARNING)

    if openstack_debug:
        openstack.enable_logging(debug=True, http_debug=True)

@cli.command("repl")
def repl():
    """Drop into interactive Python REPL"""
    client = p9admin.OpenStackClient()

    import code
    vars = globals().copy()
    vars.update(locals())
    code.interact(local=vars)

import p9admin.cli.project
import p9admin.cli.saml
import p9admin.cli.user

add_command_group(project)
add_command_group(saml)
add_command_group(user)

if __name__ == '__main__':
    cli()
