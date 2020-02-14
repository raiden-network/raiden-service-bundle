import json
import string
import time
from random import randint

import pytest

from build.purger.purger import purge_inactive_users
from raiden.constants import Networks
from tests.mocked_files import USER_PRESENCE_TEMPLATE
from tests.utils import TestGMatrixHttpApi, create_user_activity_dict

WEEK_IN_SECONDS = 60 * 60 * 24 * 7


@pytest.fixture
def due_users(last_update_in_days, due_users_count):
    return create_user_activity_dict(
        due_users_count, WEEK_IN_SECONDS + 1, WEEK_IN_SECONDS + last_update_in_days * 24 * 60 * 60
    )


@pytest.fixture
def active_users(active_users_count):
    return create_user_activity_dict(active_users_count, 0, WEEK_IN_SECONDS + 1)


@pytest.fixture
def user_presence(last_update_in_days, due_users, active_users, networks):

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
def activity_change(user_presence, due_users, activity_changed_count):

    users = dict()
    user_ids = list(due_users.keys())
    current_time = time.time()
    activity_changed = min(len(due_users), activity_changed_count)
    for _ in range(activity_changed):
        user_id = user_ids.pop()
        last_active_ago = randint(0, WEEK_IN_SECONDS + 1)
        last_active_seen = current_time - last_active_ago
        users[user_id] = last_active_seen

    return users


@pytest.fixture
def mocked_matrix_api(user_presence, activity_change):

    return TestGMatrixHttpApi(
        "https://ownserver.com",
        user_presence["network_to_users"][str(Networks.GOERLI.value)],
        activity_change,
    )


@pytest.mark.parametrize("last_update_in_days", [3])
@pytest.mark.parametrize("due_users_count, active_users_count", [(5, 10)])
@pytest.mark.parametrize("activity_changed_count", [2])
@pytest.mark.parametrize("networks", [[Networks.GOERLI]])
def test_first(
    mocked_matrix_api, user_presence, active_users_count, activity_changed_count, networks
):

    user_presence = purge_inactive_users(mocked_matrix_api, user_presence)

    assert (
        len(user_presence["network_to_users"][str(networks[0].value)])
        == active_users_count + activity_changed_count
    )
