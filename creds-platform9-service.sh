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
