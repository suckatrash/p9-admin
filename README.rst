Administer Puppet's Platform9 environment
=========================================

This is used to administer Puppet's internal Platform9 environment. It requires
admin access.

For installation information, see the “Installing” section at bottom.


Common tasks
~~~~~~~~~~~~

Provisioning a team project
---------------------------

Some teams want a shared project for their team. For example, team “Vampire
Fighters” might want a project that Buffy, Blade, and their friends can all
access together.

The first step for them is to file a HELP ticket to get an LDAP group created
for them. The name of the group should be the name of the project they want to
create, like “Vampire Fighters” or “vampire-fighters”.

Once that group has been created, you can provision the team project and all of
the users in that team with:

.. code::

    p9-admin -v project ensure-ldap -u $uid -p "$password" "Vampire Fighters"

Note that the users with access to the team progress will not automatically
update to match changes in LDAP. To sync with the LDAP group, simply run the
command again.

Provisioning users
------------------

Everybody in the company should already have a user. However, when somebody
joins the company you'll need to create a new account for them:

.. code::

    p9-admin -v user ensure-ldap-users uid=happy.noob

That will load the user's information from LDAP, then create a user and project
for them in Platform9.

In order for that user to access Platform9, they'll need to go to the login
screen, switch to local credentials, click the forgotten password link, then
enter their email address. They will receive an email allowing them to set their
password (note that the link in the email will not work in Safari).

Deleting a user
---------------

This is currently not implemented, but you can do almost as well by deleting
their project:

.. code::

    p9-admin project delete "Grumpy McCatface"


OpenStack credentials
~~~~~~~~~~~~~~~~~~~~~

You'll need to set environment variables to hold the OpenStack credentials. I
recommend creating a shell script the like one below that you can source to set
the variables correctly:

.. code:: sh

    if [ -z "$p9_user" ] ; then
      echo -n "Email: "
      read p9_user
      export p9_user
    fi

    if [ -z "$p9_password" ] ; then
      echo -n "${p9_user} password: "
      read -s p9_password
      echo
      export p9_password
    fi

    export OS_AUTH_URL=https://puppet.platform9.net/keystone/v3
    export OS_NOVA_URL=https://puppet.platform9.net/nova/v2.1

    export OS_IDENTITY_API_VERSION=3
    export OS_REGION_NAME="Portland"
    export OS_USERNAME="$p9_user"
    export OS_PASSWORD="$p9_password"
    export OS_USER_DOMAIN_ID=default
    export OS_PROJECT_NAME="service"
    export OS_PROJECT_DOMAIN_ID=default
    unset OS_IDENTITY_PROVIDER
    unset OS_PROTOCOL
    unset OS_AUTH_TYPE

Example usage:

.. code::

    ❯ source creds-platform9-service.sh
    Email: daniel.parks@puppet.com
    daniel.parks@puppet.com password:
    ❯ openstack project show service
    . . .
    ❯ p9-admin project show service
    Project "service" [face4110e4bb88c13fedca4e878454ba]
      . . .


Installing
~~~~~~~~~~

The easiest way to install this is:

1. Clone this repo locally
2. Create a virtualenv for it
3. Install ``python-ldap`` (see below)
4. Run ``python setup.py develop``

You will then be able to ``p9-admin`` directly from within the virtualenv.

On macOS that looks like:

.. code::

    ~ ❯ git clone https://github.com/puppetlabs/p9-admin.git
    ~ ❯ cd p9-admin
    p9-admin ❯ virtualenv .
    p9-admin ❯ source bin/activate
    p9-admin ❯ pip install python-ldap \
      --global-option=build_ext \
      --global-option="-I$(xcrun --show-sdk-path)/usr/include/sasl"
    p9-admin ❯ python setup.py develop

LDAP
----

If you wish to use LDAP search, you must install ``python-ldap``. Unfortunately,
it requires an extra step on macOS:

.. code:: sh

    pip install python-ldap \
      --global-option=build_ext \
      --global-option="-I$(xcrun --show-sdk-path)/usr/include/sasl"
