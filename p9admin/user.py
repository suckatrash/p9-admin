class User(object):
    def __init__(self, name, email, group=None, number=None):
        self.name = name
        self.email = email
        self.group = group

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