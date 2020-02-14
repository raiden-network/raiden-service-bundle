import time
from random import randint

from matrix_client.errors import MatrixRequestError

from raiden.network.transport.matrix.client import GMatrixHttpApi
from raiden.tests.mocked.test_matrix_transport import \
    create_new_users_for_address


class TestGMatrixHttpApi(GMatrixHttpApi):
    def __init__(self, server_name, user_presence=dict(), activity_change=dict()):
        self.server_name = server_name
        self.user_presence = user_presence
        self.activity_change = activity_change

    def get_room_id(self, room_alias):
        return f"!{room_alias}:{self.server_name}"

    def get_presence(self, user_id):
        if user_id in self.activity_change:
            return {"presence": "online", "last_active_ago": self.activity_change[user_id] * 1000}
        if user_id in self.user_presence:
            return {"presence": "offline", "last_active_ago": self.user_presence[user_id] * 1000}

        raise MatrixRequestError()

    def kick_user(self, room_id, user_id):
        return None

    def get_joined_members(self, room_id):
        return self.user_presence


def create_user_activity_dict(size, lower_bound, upper_bound):
    users = {}
    current_time = int(time.time())
    for _ in range(size):
        user_id = create_new_users_for_address()[0].user_id
        last_active_ago = randint(lower_bound, upper_bound)
        last_active_seen = current_time - last_active_ago
        users[user_id] = last_active_seen

    return users
