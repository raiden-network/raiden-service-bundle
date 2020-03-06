import json
import string
import time
from random import randint
from typing import Any, Dict

import pytest

from build.purger.purger import (
    USER_PURGING_THRESHOLD,
    get_network_to_broadcast_rooms,
    run_user_purger,
)
from raiden.constants import Networks
from tests.file_templates import USER_PRESENCE_TEMPLATE
from tests.utils import GMatrixHttpApiTest, create_user_activity_dict


@pytest.fixture
def due_users(last_update_in_days: int, due_users_count: int) -> Dict[str, int]:
    return create_user_activity_dict(
        due_users_count,
        USER_PURGING_THRESHOLD + 1,
        USER_PURGING_THRESHOLD + last_update_in_days * 24 * 60 * 60,
    )


@pytest.fixture
def active_users(active_users_count: int) -> Dict[str, int]:
    return create_user_activity_dict(active_users_count, 0, USER_PURGING_THRESHOLD - 1)


@pytest.fixture
def global_user_activity(last_update_in_days, due_users, active_users, networks):

    network_to_users_activity = dict()

    for network in networks:
        users = {**due_users, **active_users}
        network_to_users_activity[network.value] = users

    return json.loads(
        string.Template(USER_PRESENCE_TEMPLATE).substitute(
            last_update=last_update_in_days * 24 * 60 * 60,
            network_to_users=json.dumps(network_to_users_activity),
        )
    )


@pytest.fixture
def activity_change(due_users: Dict[str, int], activity_changed_count: int) -> Dict[str, int]:

    users = dict()
    user_ids = list(due_users.keys())
    activity_changed = min(len(due_users), activity_changed_count)
    for _ in range(activity_changed):
        user_id = user_ids.pop()
        last_active_ago = randint(0, USER_PURGING_THRESHOLD - 1)
        users[user_id] = last_active_ago

    return users


@pytest.fixture
def mocked_matrix_api(
    global_user_activity: Dict[str, Any], activity_change: Dict[str, int]
) -> GMatrixHttpApiTest:

    return GMatrixHttpApiTest(
        "https://ownserver.com",
        global_user_activity["network_to_users"][str(Networks.GOERLI.value)],
        activity_change,
    )


@pytest.mark.parametrize("last_update_in_days", [3])
@pytest.mark.parametrize("due_users_count, active_users_count", [(5, 10)])
@pytest.mark.parametrize("activity_changed_count", [2])
@pytest.mark.parametrize("networks", [[Networks.GOERLI]])
def test_due_users_get_kicked(
    mocked_matrix_api, global_user_activity, active_users_count, activity_changed_count, networks
):
    network_to_broadcast_rooms = get_network_to_broadcast_rooms(mocked_matrix_api)

    new_global_user_activity = run_user_purger(
        mocked_matrix_api, global_user_activity, network_to_broadcast_rooms
    )
    # assert that number of user reduced as expected
    assert (
        len(new_global_user_activity["network_to_users"][str(networks[0].value)])
        == active_users_count + activity_changed_count
    )

    due_user_items = [
        (user_id, last_seen)
        for user_id, last_seen in new_global_user_activity["network_to_users"][
            str(networks[0].value)
        ].items()
        if last_seen < int(time.time()) - USER_PURGING_THRESHOLD
    ]
    # assert that there are no due users in the dictionary anymore
    assert len(due_user_items) == 0
