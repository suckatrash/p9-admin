p9-admin
========

Tool for administering our Platform9 environment.

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

    ❯ source /tmp/creds-platform9-service.sh
    Email: daniel.parks@puppet.com
    daniel.parks@puppet.com password:
    ❯ openstack project show service
    . . .
    ❯ p9-admin project show service
    Project "service" [face4110e4bb88c13fedca4e878454ba]
      . . .

LDAP
~~~~

If you wish to use LDAP search, you must install ``python-ldap``. Unfortunately,
it requires an extra step on macOS:

.. code:: sh

    pip install python-ldap \
      --global-option=build_ext \
      --global-option="-I$(xcrun --show-sdk-path)/usr/include/sasl"
