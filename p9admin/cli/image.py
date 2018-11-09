from __future__ import print_function
import click
import logging
import p9admin
from pprint import pprint
import sys

@click.group()
def image():
    """Manage images."""
    pass


def _fix_provider_location(logger, glance, image):
    if len(image.locations) != 1:
        logger.error("Expected single location, got %s", image.locations)
        return False

    location = image.locations[0]["url"]
    logger.debug('Image "%s" [%s] location: "%s"',
        image.name, image.id, location)

    try:
        logger.debug('Image "%s" [%s] provider_location: "%s"',
            image.name, image.id, image.provider_location)
    except AttributeError:
        logger.debug('Image "%s" [%s] provider_location: None',
            image.name, image.id)

    expected_prefix = "file:///var/opt/pf9/imagelibrary/data/"
    tintri_prefix = "nfs://tintri-data-opdx-1-1.ops.puppetlabs.net:/tintri/p9openstack-prod/images/"

    if not location.startswith(expected_prefix):
        logger.error(
            'Image "%s" [%s]: expected location URL to start with "%s", got "%s"',
            image.name, image.id, expected_prefix, location)
        return False

    relative_path = location[len(expected_prefix):]
    provider_location = tintri_prefix + relative_path

    image = glance.images.update(image.id, provider_location=provider_location)
    logger.debug('Image "%s" [%s] provider_location saved as: "%s"',
        image.name, image.id, image.provider_location)

    if image.provider_location == provider_location:
        logger.info('Fixed image "%s" [%s] provider_location',
            image.name, image.id)
        return True
    else:
        logger.error('Image "%s" [%s] provider_location could not be saved',
            image.name, image.id)
        return False


@image.command("fix-provider-location")
@click.argument("id", required=False)
@click.option("--all/--one", default=False,
    help="Fix all images (don't specify an ID) or just one.")
def fix_provider_location(id=None, all=False):
    """
    Fix the provider_location property of an image.

    Setting the provider_location property correctly allows the Tintri to do the
    clone of the image instead of having OpenStack download the image and then
    re-upload it via Cinder.
    """
    logger = logging.getLogger(__name__)
    glance = p9admin.OpenStackClient().glance()

    if all and id is not None:
        sys.exit("ID and --all cannot both be specified.")
    if not all and id is None:
        sys.exit("Either ID or --all must be specified.")

    if all:
        for image in glance.images.list():
            _fix_provider_location(logger, glance, image)
    else:
        image = glance.images.get(id)
        _fix_provider_location(logger, glance, image)
