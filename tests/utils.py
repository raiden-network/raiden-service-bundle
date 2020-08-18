import string
import time
from random import choice, randint
from typing import Dict

from matrix_client.errors import MatrixRequestError

from raiden.network.transport.matrix.client import GMatrixHttpApi
from raiden.tests.mocked.test_matrix_transport import create_new_users_for_address


class GMatrixHttpApiTest(GMatrixHttpApi):
    def __init__(self, server_name, user_presence=dict(), activity_change=dict()):
        super(GMatrixHttpApiTest, self).__init__(base_url=server_name)
        self.server_name = server_name
        self.user_presence = user_presence
        self.activity_change = activity_change

    def get_room_id(self, room_alias) -> str:
        letters = string.ascii_lowercase
        random_room_id = "".join(choice(letters) for i in range(10))
        return f"!{random_room_id}:{self.server_name}"

    def get_presence(self, user_id):
        if user_id in self.activity_change:
            return {"presence": "online", "last_active_ago": self.activity_change[user_id] * 1000}
        if user_id in self.user_presence:
            return {"presence": "offline", "last_active_ago": self.user_presence[user_id] * 1000}

        raise MatrixRequestError()

    def get_joined_members(self, room_id):
        return self.user_presence

    # this is a hack because _send is only called upon fetching room members via admin api
    def _send(
        self, method, path, content=None, query_params=None, headers=None, api_path="",
    ):
        return {"members": []}


def create_user_activity_dict(size: int, lower_bound: int, upper_bound: int) -> Dict[str, int]:
    """

    :param size: number of users
    :param lower_bound: lower bound of how many seconds ago the user was seen online
    :param upper_bound: higher bound of how many seconds ago the user was seen online
    :return: dictionary of users to last seen online age in seconds
    """
    users = {}
    current_time = int(time.time())
    for _ in range(size):
        user_id = create_new_users_for_address()[0].user_id
        last_active_ago = randint(lower_bound, upper_bound)
        last_active_seen = current_time - last_active_ago
        users[user_id] = last_active_seen

    return users
