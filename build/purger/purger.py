import datetime
import json
import sys
import time
from dataclasses import dataclass
from json import JSONDecodeError
from operator import itemgetter
from pathlib import Path
from typing import Any, Dict, List, TextIO
from urllib.parse import quote, urljoin, urlparse

import click
import psycopg2
import requests
import yaml
from matrix_client.errors import MatrixError
from raiden_contracts.utils.type_aliases import ChainID

import docker
from raiden.constants import (DISCOVERY_DEFAULT_ROOM,
                              MONITORING_BROADCASTING_ROOM,
                              PATH_FINDING_BROADCASTING_ROOM, Networks)
from raiden.network.transport.matrix import make_room_alias
from raiden.network.transport.matrix.client import GMatrixHttpApi

URL_KNOWN_FEDERATION_SERVERS_DEFAULT = (
    "https://raw.githubusercontent.com/raiden-network/raiden-transport/master/known_servers.yaml"
)

SYNAPSE_CONFIG_PATH = "/config/synapse.yaml"
USER_PURGING_THRESHOLD = 2 * 24 * 60 * 60  # 2 days
USER_ACTIVITY_PATH = Path("/config/user_activity.json")


@dataclass(frozen=True)
class RoomInfo:
    room_id: str
    alias: str
    server_name: str

    @property
    def local_room_alias(self):
        return f"#{self.alias}:{self.server_name}"


@click.command()
@click.argument("db_uri", envvar="MATRIX_DB_URI")
@click.argument("server", envvar="MATRIX_SERVER")
@click.option("-c", "--credentials-file", required=True, type=click.File("rt"))
@click.option("--keep-newer", type=int, help="Keep events newer than this number of days")
@click.option(
    "--keep-min-msgs",
    type=int,
    help="Keep at least this number of message events per room, regardless of --keep-newer",
)
@click.option(
    "--parallel-purges",
    default=10,
    show_default=True,
    type=int,
    help="Max number of purges to run in parallel.",
)
@click.option(
    "--post-sql",
    type=click.File("rt"),
    help=(
        "Pass a SQL script file as parameter to run it on DB after purging. "
        'Useful to run cleanup scripts, like "synapse_janitor.sql".'
    ),
)
@click.option(
    "--docker-restart-label",
    help="If set, search all containers with given label and, if they're running, restart them",
)
def purge(
    db_uri: str,
    server: str,
    credentials_file: TextIO,
    keep_newer: int,
    keep_min_msgs: int,
    parallel_purges: int,
    post_sql: TextIO,
    docker_restart_label: str,
) -> None:
    """ Purge historic data from rooms in a synapse server

    DB_URI: DB connection string: postgres://user:password@netloc:port/dbname
    SERVER: matrix synapse server url, e.g.: http://hostname

    All option can be passed through uppercase environment variables prefixed with 'MATRIX_'
    e.g.: export MATRIX_KEEP_MIN_MSGS=100
    """
    session = requests.Session()

    try:
        credentials = json.loads(credentials_file.read())
        username = credentials["username"]
        password = credentials["password"]
    except (JSONDecodeError, UnicodeDecodeError, OSError, KeyError) as ex:
        click.secho(f"Invalid credentials file: {ex}", fg="red")
        sys.exit(1)

    api = GMatrixHttpApi(server)
    try:
        response = api.login("m.login.password", user=username, password=password)
        admin_access_token = response["access_token"]
    except (MatrixError, KeyError) as ex:
        click.secho(f"Could not log in to server {server}: {ex}")
        sys.exit(1)

    try:
        with psycopg2.connect(db_uri) as db, db.cursor() as cur:
            purges: Dict[str, str] = dict()

            def wait_and_purge_room(room_id: str = None, event_id: str = None) -> None:
                """ Wait for available slots in parallel_purges and purge room

                If room_id is None, just wait for current purges to complete and return
                If event_id is None, purge all events in room
                """
                while len(purges) >= (parallel_purges if room_id else 1):
                    # wait and clear completed purges
                    time.sleep(1)
                    for _room_id, purge_id in list(purges.items()):
                        response = session.get(
                            urljoin(
                                server,
                                "/_matrix/client/r0/admin/purge_history_status/" + quote(purge_id),
                            ),
                            params={"access_token": admin_access_token},
                        )
                        assert response.status_code == 200, f"{response!r} => {response.text!r}"
                        if response.json()["status"] != "active":
                            click.secho(f"Finished purge: room {_room_id!r}, purge {purge_id!r}")
                            purges.pop(_room_id)

                if not room_id:
                    return

                body: Dict[str, Any] = {"delete_local_events": True}
                if event_id:
                    body["purge_up_to_event_id"] = event_id
                else:
                    body["purge_up_to_ts"] = int(time.time() * 1000)
                response = session.post(
                    urljoin(server, "/_matrix/client/r0/admin/purge_history/" + quote(room_id)),
                    params={"access_token": admin_access_token},
                    json=body,
                )
                if response.status_code == 200:
                    purge_id = response.json()["purge_id"]
                    purges[room_id] = purge_id
                    return

            if not keep_newer and not keep_min_msgs:
                click.confirm(
                    "No --keep-newer nor --keep-min-msgs option provided. Purge all history?",
                    abort=True,
                )

            ts_ms = None
            if keep_newer:
                ts = datetime.datetime.now() - datetime.timedelta(keep_newer)
                ts_ms = int(ts.timestamp() * 1000)

            cur.execute("SELECT room_id FROM rooms ;")
            all_rooms = {row for row, in cur}

            click.secho(f"Processing {len(all_rooms)} rooms")
            for room_id in all_rooms:
                # no --keep-min-msgs nor --keep-newer, purge everything
                if not keep_newer and not keep_min_msgs:
                    wait_and_purge_room(room_id)
                    continue
                cur.execute(
                    f"""
                    SELECT event_id FROM (
                        SELECT event_id,
                            received_ts,
                            COUNT(*) OVER (ORDER BY received_ts DESC) AS msg_count_above
                        FROM events
                        WHERE room_id=%(room_id)s AND type='m.room.message'
                        ORDER BY received_ts DESC
                    ) t WHERE true
                    {'AND received_ts < %(ts_ms)s' if keep_newer else ''}
                    {'AND msg_count_above > %(keep_min_msgs)s' if keep_min_msgs else ''}
                    LIMIT 1 ;""",
                    {"room_id": room_id, "ts_ms": ts_ms, "keep_min_msgs": keep_min_msgs},
                )
                if cur.rowcount:
                    event_id, = cur.fetchone()
                    wait_and_purge_room(room_id, event_id)
                # else: room doesn't have messages eligible for purging, skip

            wait_and_purge_room(None)

        if post_sql:
            click.secho(f"Running {post_sql.name!r}")
            with psycopg2.connect(db_uri) as db, db.cursor() as cur:
                cur.execute(post_sql.read())
                click.secho(f"Results {cur.rowcount}:")
                for i, row in enumerate(cur):
                    click.secho(f"{i}: {row}")

        global_user_activity = {
            "last_update": int(time.time()) - USER_PURGING_THRESHOLD - 1,
            "network_to_users": {},
        }

        try:
            global_user_activity = json.loads(USER_ACTIVITY_PATH.read_text())
        except JSONDecodeError:
            click.secho(f"{USER_ACTIVITY_PATH} is not a valid JSON. Starting with empty list")
        except FileNotFoundError:
            click.secho(f"{USER_ACTIVITY_PATH} not found. Starting with empty list")

        # check if there are new networks to add
        for network in Networks:
            if str(network.value) in global_user_activity["network_to_users"]:
                continue
            global_user_activity["network_to_users"][str(network.value)] = dict()

        # get broadcast room ids for all networks
        network_to_broadcast_rooms = get_network_to_broadcast_rooms(api)

        new_global_user_activity = run_user_purger(
            api, global_user_activity, network_to_broadcast_rooms
        )

        # write the updated user activity to file
        USER_ACTIVITY_PATH.write_text(json.dumps(new_global_user_activity))
    finally:
        if docker_restart_label:
            client = docker.from_env()  # type: ignore
            for container in client.containers.list():
                if container.attrs["State"]["Status"] != "running" or not container.attrs[
                    "Config"
                ]["Labels"].get(docker_restart_label):
                    continue

                try:
                    # parse container's env vars
                    env_vars: Dict[str, Any] = dict(
                        itemgetter(0, 2)(e.partition("="))
                        for e in container.attrs["Config"]["Env"]
                    )
                    remote_config_file = (
                        env_vars.get("URL_KNOWN_FEDERATION_SERVERS")
                        or URL_KNOWN_FEDERATION_SERVERS_DEFAULT
                    )

                    # fetch remote file
                    remote_whitelist = yaml.load(requests.get(remote_config_file).text)

                    # fetch local list from container's synapse config
                    local_whitelist = yaml.load(
                        container.exec_run(["cat", SYNAPSE_CONFIG_PATH]).output
                    )["federation_domain_whitelist"]

                    # if list didn't change, don't proceed to restart container
                    if local_whitelist and remote_whitelist == local_whitelist:
                        continue

                    click.secho(f"Whitelist changed. Restarting. new_list={remote_whitelist!r}")
                except (
                    KeyError,
                    IndexError,
                    requests.RequestException,
                    yaml.scanner.ScannerError,
                ) as ex:
                    click.secho(
                        f"An error ocurred while fetching whitelists: {ex!r}\n"
                        "Restarting anyway",
                        err=True,
                    )
                # restart container
                container.restart(timeout=30)


def run_user_purger(
    api: GMatrixHttpApi,
    global_user_activity: Dict[str, Any],
    network_to_broadcast_rooms: Dict[str, List[RoomInfo]],
) -> Dict[str, Any]:
    """
    The user purger mechanism finds inactive users which have been offline
    longer than the threshold time and will kick them out of the global rooms
    to clean up the server's database and reduce load.
    Each server is responsible for its own users

    :param api: Api object to own server
    :param global_user_activity: content of user activity file
    :param network_to_broadcast_rooms: RoomInfo Objects of all broadcast rooms
    :return: None
    """

    # perform update on user presence for due users
    # receive a list for due users on each network
    due_users = update_user_activity(api, global_user_activity, network_to_broadcast_rooms)
    # purge due users form rooms
    purge_inactive_users(api, global_user_activity, network_to_broadcast_rooms, due_users)

    return global_user_activity


def get_network_to_broadcast_rooms(api: GMatrixHttpApi) -> Dict[str, List[RoomInfo]]:

    room_alias_fragments = [
        DISCOVERY_DEFAULT_ROOM,
        PATH_FINDING_BROADCASTING_ROOM,
        MONITORING_BROADCASTING_ROOM,
    ]

    server = urlparse(api.base_url).netloc
    network_to_broadcast: Dict[str, List[RoomInfo]] = dict()

    for network in Networks:
        broadcast_room_infos: List[RoomInfo] = list()
        network_to_broadcast[str(network.value)] = broadcast_room_infos
        for room_alias_fragment in room_alias_fragments:
            broadcast_room_alias = make_room_alias(ChainID(network.value), room_alias_fragment)
            local_room_alias = f"#{broadcast_room_alias}:{server}"

            try:
                room_id = api.get_room_id(local_room_alias)
                broadcast_room_infos.append(RoomInfo(room_id, broadcast_room_alias, server))
            except MatrixError as ex:
                click.secho(f"Could not find room {broadcast_room_alias} with error {ex}")

    return network_to_broadcast


def update_user_activity(
    api: GMatrixHttpApi,
    global_user_activity: Dict[str, Any],
    broadcast_rooms: Dict[str, List[RoomInfo]],
) -> Dict[str, List[str]]:
    """
    runs update on users' presences which are about to be kicked.
    If they are still overdue they are going to be added to the list
    of users to be kicked. Presence updates are included in the
    global list which is going to be stored in the user_activity_file
    :param api: api to its own server
    :param global_user_activity: content of user_activity_file
    :param broadcast_rooms: room information for broadcast rooms
    :return: a list of due users to be kicked
    """
    current_time = int(time.time())
    last_user_activity_update = global_user_activity["last_update"]
    network_to_users = global_user_activity["network_to_users"]
    network_to_due_users = dict()
    fetch_new_members = False

    # check if new members have to be fetched
    # new members only have to be fetched every
    # USER_PURGING_THRESHOLD since that is the earliest time
    # new members are able to be kicked. This keeps the load on
    # the server as low as possible
    if last_user_activity_update < current_time - USER_PURGING_THRESHOLD:
        fetch_new_members = True
        global_user_activity["last_update"] = current_time

    for network_key, user_activity in network_to_users.items():
        if fetch_new_members:
            _fetch_new_members_for_network(
                api=api,
                user_activity=network_to_users[network_key],
                discovery_room=broadcast_rooms[network_key][0],
                current_time=current_time,
            )

        network_to_due_users[network_key] = _update_user_activity_for_network(
            api=api, user_activity=user_activity, current_time=current_time
        )

    return network_to_due_users


def _fetch_new_members_for_network(
    api: GMatrixHttpApi, user_activity: Dict[str, int], discovery_room: RoomInfo, current_time: int
) -> None:
    try:
        response = api.get_room_members(discovery_room.room_id)
        room_members = [
            event["state_key"]
            for event in response["chunk"]
            if event["content"]["membership"] == "join"
            and event["state_key"].split(":")[1] == urlparse(api.base_url).netloc
            and not event["state_key"].find("admin")
        ]

        # Add new members with an overdue activity time
        # to trigger presence update later
        for user_id in room_members:
            if user_id not in user_activity:
                user_activity[user_id] = current_time - USER_PURGING_THRESHOLD - 1

    except MatrixError as ex:
        click.secho(f"Could not fetch members for {discovery_room.alias} with error {ex}")


def _update_user_activity_for_network(
    api: GMatrixHttpApi, user_activity: Dict[str, Any], current_time: int
) -> List[str]:
    deadline = current_time - USER_PURGING_THRESHOLD

    possible_candidates = [
        user_id for user_id, last_seen in user_activity.items() if last_seen < deadline
    ]

    due_users = list()

    # presence updates are only run for possible due users.
    # This helps to spread the load on the server as good as possible
    # Since this script runs once a day, every day a couple of users are
    # going to be updated rather than all at once
    for user_id in possible_candidates:
        try:
            response = api.get_presence(user_id)
            # in rare cases there is no last_active_ago sent
            if "last_active_ago" in response:
                last_active_ago = response["last_active_ago"] // 1000
            else:
                last_active_ago = USER_PURGING_THRESHOLD + 1
            presence = response["presence"]
            last_seen = current_time - last_active_ago
            user_activity[user_id] = last_seen
            if user_activity[user_id] < deadline and presence == "offline":
                due_users.append(user_id)

        except MatrixError as ex:
            click.secho(f"Could not fetch user presence of {user_id}: {ex}")
        finally:
            time.sleep(0.1)
    return due_users


def purge_inactive_users(
    api: GMatrixHttpApi,
    global_user_activity: Dict[str, Any],
    network_to_broadcast_rooms: Dict[str, List[RoomInfo]],
    network_to_due_users: Dict[str, List[str]],
) -> None:
    for network_key, due_users in network_to_due_users.items():
        _purge_inactive_users_for_network(
            api=api,
            user_activity=global_user_activity["network_to_users"][network_key],
            due_users=due_users,
            broadcast_rooms=network_to_broadcast_rooms[network_key],
        )


def _purge_inactive_users_for_network(
    api: GMatrixHttpApi,
    user_activity: Dict[str, int],
    due_users: List[str],
    broadcast_rooms: List[RoomInfo],
) -> None:
    for user_id in due_users:
        for room in broadcast_rooms:
            try:
                # kick the user and remove him from the user_activity_file
                last_ago = (int(time.time()) - user_activity[user_id]) / (60 * 60 * 24)
                api.kick_user(room.room_id, user_id)
                user_activity.pop(user_id, None)
                click.secho(
                    f"{user_id} kicked from room {room.alias}. Offline for {last_ago} days."
                )
            except MatrixError as ex:
                click.secho(f"Could not kick user from room {room.alias} with error {ex}")
            finally:
                time.sleep(0.1)


if __name__ == "__main__":
    purge(  # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
        auto_envvar_prefix="MATRIX"
    )
