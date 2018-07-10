p9-admin
========

Tool for administering our Platform9 environment.

LDAP
~~~~

If you wish to use LDAP search, you must install ``python-ldap``. Unfortunately,
it requires an extra step on macOS:

.. code:: sh

    pip install python-ldap \
      --global-option=build_ext \
      --global-option="-I$(xcrun --show-sdk-path)/usr/include/sasl"
