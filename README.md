Administer Puppet's Platform9 environment
=========================================

This is used to administer Puppet's internal Platform9 environment. It requires
admin access.

For installation information, see the “Installing and upgrading” section at
bottom. If you want to work on this tool itself, see the “Developing” section.


## Common tasks

### Provisioning a team project

Some teams want a shared project for their team. For example, team “Vampire
Fighters” might want a project that Buffy, Blade, and their friends can all
access together.

The first step for them is to file a HELP ticket to get an LDAP group created
for them. The name of the group should be the name of the project they want to
create, like “Vampire Fighters” or “vampire-fighters”.

Once that group has been created, you can provision the team project and all of
the users in that team with:

```
p9-admin -v project ensure-ldap -u $uid -p "$password" "Vampire Fighters"
```

Note that the users with access to the team progress will not automatically
update to match changes in LDAP. To sync with the LDAP group, simply run the
command again.

### Provisioning users

Everybody in the company should already have a user. However, when somebody
joins the company you'll need to create a new account for them:

```
p9-admin -v user ensure-ldap-users uid=happy.noob
```

That will load the user's information from LDAP, then create a user and project
for them in Platform9.

In order for that user to access Platform9, they'll need to go to the login
screen, switch to local credentials, click the forgotten password link, then
enter their email address. They will receive an email allowing them to set their
password (note that the link in the email will not work in Safari).

### Deleting a user

This is currently not implemented, but you can do almost as well by deleting
their project:

```
p9-admin project delete "Grumpy McCatface"
```

## OpenStack credentials

You'll need to set environment variables to hold the OpenStack credentials. I
recommend creating a shell script the like one below that you can source to set
the variables correctly:

```
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
```

Example usage:

```
❯ source creds-platform9-service.sh
Email: daniel.parks@puppet.com
daniel.parks@puppet.com password:
❯ openstack project show service
. . .
❯ p9-admin project show service
Project "service" [face4110e4bb88c13fedca4e878454ba]
  . . .
```

## Installing and upgrading via pip

If you wish to do development on this tool, you should skip this and follow the
instructions under “Developing” below.

```
pip install \
--upgrade \
--extra-index-url https://artifactory.delivery.puppetlabs.net/artifactory/api/pypi/pypi/simple \
p9-admin
```


## Using via Docker

If you wish to use p9-admin via `docker run` you can do so by wither building
the contaner locally or by pulling it from our internal registry like so:

```
source creds-platform9-service.sh
./run.sh <options for p9-admin>
```

For example:

```
./run.sh --help
Usage: p9-admin [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --verbose
  -d, --debug
  --openstack-debug
  --version          Show the version and exit.
  --help             Show this message and exit.

Commands:
  host     Tools for hypervisors.
  image    Manage images.
  project  Manage projects.
  repl     Drop into interactive Python REPL.
  user     Manage local users.

./run.sh project show service
Project "service" [1367dca4e889454baface4110e4bb88c]
  Network "external" [c62ece49-cc9e-49a4-816a-c06b55486beb]
    Subnet "external-subnet" [01ad0a64-33d8-4108-8f51-6ee9e396ca39] 10.234.0.0/21
  Security group "default" .........
```


## Developing

To get this set up for development:

1. Clone this repo locally
2. Create a virtualenv for it
3. Run ``python setup.py develop``

You will then be able to ``p9-admin`` directly from within the virtualenv.

On macOS that looks like:

```
~ ❯ git clone https://github.com/puppetlabs/p9-admin.git
~ ❯ cd p9-admin
p9-admin ❯ virtualenv .
p9-admin ❯ source bin/activate
p9-admin ❯ python setup.py develop
```
