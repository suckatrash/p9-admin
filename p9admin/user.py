import logging
import p9admin
import sys

class User(object):
    def __init__(self, name, email, group=None, number=None):
        self.name = name
        self.email = email
        self.group = group
        # Keystone user object
        self.user = None

    def __str__(self):
        return "{name} <{email}>".format(**self.__dict__)

    def __repr__(self):
        if self.group:
            group_id = self.group.id
        else:
            group_id = "None"

        return '{}("{}", {})'.format(
            self.__class__.__name__,
            str(self),
            group_id)

def load_users(p9Users, client):
    """Convert Users into user objects returned by keystone"""
    users = []
    bad_emails = []

    for p9User in p9Users:
        p9User.user = client.find_user(p9User)
        if p9User.user is None:
            bad_emails.append(p9User.email)
        else:
            users.append(p9User.user)

    if bad_emails:
        sys.exit("Found users that do not exist in Platform9: {}".format(
            ", ".join(bad_emails)))

    return users

def get_ldap_group_users(name, uid, password):
    filters = [
        'objectClass=puppetPerson',
        '!(objectClass=exPuppetPerson)',
        'memberOf=cn={},ou=groups,dc=puppetlabs,dc=com'.format(name),
    ]

    filters = "".join(["({})".format(filter) for filter in filters])
    filter = '(&{})'.format(filters)

    return get_ldap_users(filter, uid, password)

def get_ldap_users(filter, uid, password):
    USERS_DN = "ou=users,dc=puppetlabs,dc=com"
    LDAP_URL = "ldap://ldap.puppetlabs.com"

    logger = logging.getLogger(__name__)

    # LDAP is a pain to build. Don't fail unless we're actually using it.
    import ldap

    bind_dn = "uid={},{}".format(uid, USERS_DN)
    client = ldap.initialize(LDAP_URL)
    client.start_tls_s()
    count = 1

    try:
        try:
            client.simple_bind_s(bind_dn, password)
        except ldap.LDAPError as e:
            logger.critical("Could not bind to LDAP server '{}' as '{}': {}"
                .format(LDAP_URL, bind_dn, e))
            sys.exit(1)

        users = client.search_st(USERS_DN, ldap.SCOPE_SUBTREE, filter,
            attrlist=["cn", "mail"], timeout=60)
        if len(users) == 0:
            logger.warn('Found 0 users in LDAP for filter "%s"', filter)
            return []

        logger.info('Found %d users in LDAP for filter "%s"',
            len(users), filter)

        user_objects = []
        for dn, attrs in users:
            cns = attrs.get("cn", list())
            mails = attrs.get("mail", list())

            if not cns:
                logger.error("Skipping %s: no cn attribute", dn)
                continue
            if not mails:
                logger.error("Skipping %s: no mail attribute", dn)
                continue

            if len(cns) > 1:
                logger.warn("%s has %d cn values", dn, len(mails))
            if len(mails) > 1:
                logger.warn("%s has %d mail values", dn, len(mails))

            # Values are returned as bytes.
            cn = cns[0].decode("utf-8")
            mail = mails[0].decode("utf-8")

            user_objects.append(p9admin.User(cn, mail, number=count))
            count += 1

        return user_objects
    finally:
        client.unbind()
