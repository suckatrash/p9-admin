from __future__ import print_function
from datetime import datetime
import json
import logging
import p9admin.user

MAPPING_NAME = "idp1_mapping"

class SAML(object):
    # client should be p9admin.OpenStackClient
    def __init__(self, client, backup_directory="/tmp"):
        self.client = client
        self.backup_directory = backup_directory
        self.logger = logging.getLogger(__name__)
        self._mappings = None

    def auth(self):
        import pf9_saml_auth
        return pf9_saml_auth.V3Pf9SamlOkta(
            auth_url=os.environ["OS_AUTH_URL"],
            username=os.environ["OS_USERNAME"],
            password=os.environ["OS_PASSWORD"],
            project_name=os.environ["OS_PROJECT_NAME"],
            project_domain_name=os.environ["OS_PROJECT_DOMAIN_ID"],
            protocol="saml2",
            identity_provider="IDP1",
        )

    def show_group(self, email):
        group = self.client.keystone().groups.find(name="User: {}".format(email))
        print('Group "{}" [{}]: {}'.format(group.name, group.id, group.description))
        for rule in self.filter_mappings(email, group.id):
            print("  Rule")
            for match in rule["remote"]:
                m2 = match.copy()
                del(m2["type"])
                print("    {}: {}".format(match["type"], m2))

    def delete_groups(self, emails):
        groups = []
        for email in emails:
            groups.append(self.client.keystone().groups.find(name="User: {}".format(email)))
        self.delete_mappings(email, [group.id for group in groups])
        for group in groups:
            self.client.keystone().groups.delete(group)
            self.logger.info('Deleted group "%s", [%s]', group.name, group.id)

    def ensure_group(self, user):
        # Ensure that a group exists for a user
        if user.group:
            return group

        ### This optimizes for bulk add. Should we have a separate path when the number of users is <N?
        group_name = "User: {}".format(user.email)
        for group in self.client.groups():
            if group.name == group_name:
                self.logger.info('Found group "%s" [%s]', group.name, group.id)
                break
        else:
            group = self.client.keystone().groups.create(name=group_name, description=user.name)
            self.logger.info('Created group "%s" [%s]', group.name, group.id)
            ### FIXME abstract memoization modification
            self.client.groups.cache[(self,)].append(group)

        user.group = group
        return group

    def manager(self):
        return self.client.keystone().federation.mappings

    def all_mappings(self):
        return self.manager().get(MAPPING_NAME).rules

    def filter_mappings(self, email, group_id):
        for rule in self.all_mappings():
            if check_rule(rule, email, [group_id]):
                yield rule

    def delete_mappings(self, email, group_ids):
        old = self.all_mappings()
        new = [r for r in old if not check_rule(r, email, group_ids)]
        self.save_mappings(old, new)

    def save_mappings(self, old, new):
        backup_path = datetime.now().strftime(
            "{}/rules_%Y-%m-%d_%H:%M:%S.json".format(self.backup_directory))

        with open(backup_path, "w") as file:
            file.write(json.dumps(old, indent=2))
        self.logger.info("Old mappings backed up to %s", backup_path)

        self.manager().update(MAPPING_NAME, rules=new)
        self.logger.info("New mappings saved")

    def ensure_mappings(self, users):
        # Map SAML email attribute to groups
        old = self.all_mappings()
        new = []

        for user in users:
            for rule in old:
                if check_rule(rule, user.email, [user.group.id]):
                    self.logger.info('Found mapping of "%s" to group [%s]',
                        user.email, user.group.id)
                    break
            else:
                new.append(create_rule(user.email, user.group.id))
                self.logger.info('Adding mapping of "%s" to group [%s]',
                    user.email, user.group.id)

        if new:
            self.save_mappings(old, old + new)
        else:
            self.logger.info("Mappings are already up to date")

def create_rule(email, group_id):
    return {
        'remote': [
            {'type': 'FirstName'},
            {'type': 'LastName'},
            {'type': 'Email', 'regex': False, 'any_one_of': [email]}
        ],
        'local': [
            {
                'group': {'id': group_id},
                'user': {'name': '{0} {1}'}
            }
        ]
    }

def check_rule(rule, email, group_ids):
    """
    Check if a rule matches and email and group

    See create_rule() for an example of what a rule looks like.
    """

    for match in rule["remote"]:
        if match.get("type") == "Email" and email in match.get("any_one_of"):
            break
    else:
        return False

    for match in rule["local"]:
        if match.get("group", dict()).get("id") in group_ids:
            return True

    return False
