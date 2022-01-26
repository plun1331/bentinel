class ModAction(object):
    def __init__(self, row):
        self.user = row[0]
        self.mod = row[1]
        self.reason = row[2]
        self.id = row[3]
        self.time = row[4]
        self.expires = row[5]
        self.action_type = row[6]
        self.expired = bool(row[7])

class Suggestion(object):
    def __init__(self, row):
        self.id = row[3]
        self.user = row[0]
        self.message = row[1]
        self.suggestion = row[2]

class AtlasException(Exception):
    pass

class LevelUser(object):
    def __init__(self, row):
        self.user = row[0]
        self.messages = row[1]
        self.xp = row[2]

class BirthdayUser(object):
    def __init__(self, row):
        self.user = row[0]
        self.month = row[1]
        self.day = row[2]

class Ticket(object):
    def __init__(self, row):
        self.id = row[0]
        self.user = row[1]
        self.channel = row[2]
        self.state = row[3]
        self.created_at = row[4]