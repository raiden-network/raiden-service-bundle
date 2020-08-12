"""
Utility that initializes public rooms and ensures correct federation

In Raiden we use a public discovery room that all nodes join which provides the following features:
- Nodes are findable in the server-side user search
- All nodes receive presence updates about existing and newly joined nodes

The global room is initially created on one server, after that it is federated to all other servers
and a server-local alias is added to it so it's discoverable on every server.

This utility uses for following algorithm to ensure there are no races in room creation:
- Sort list of known servers lexicographically
- Connect to all known servers
- If not all servers are reachable, sleep and retry later
- Try to join room `#<public_room_alias>:<connected_server>`
- Compare room_id of all found rooms
- If either the room_ids differ or no room is found on a specific server:
  - If `own_server` is the first server in the list:
    - Create a room if it doesn't exist and assign the server-local alias
  - Else:
    - If a room with alias `#<public_room_alias>:<own_server>` exists, remove that alias
    - Wait for the room with `#<public_room_alias>:<first_server>` to appear
    - Add server-local alias to the first_server-room
"""
from gevent.monkey import patch_all  # isort:skip

patch_all()  # isort:skip

import json
import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from itertools import chain
from json import JSONDecodeError
from typing import Any, Dict, Optional, Set, TextIO, Tuple, Union
from urllib.parse import urlparse

import click
import gevent
from eth_utils import encode_hex, to_normalized_address
from matrix_client.errors import MatrixError, MatrixHttpLibError, MatrixRequestError
from structlog import get_logger

from raiden.constants import (
    DISCOVERY_DEFAULT_ROOM,
    MONITORING_BROADCASTING_ROOM,
    PATH_FINDING_BROADCASTING_ROOM,
    Environment,
    Networks,
    ServerListType,
)
from raiden.log_config import configure_logging
from raiden.network.transport.matrix import make_room_alias
from raiden.network.transport.matrix.client import GMatrixHttpApi
from raiden.settings import DEFAULT_MATRIX_KNOWN_SERVERS
from raiden.tests.utils.factories import make_signer
from raiden.utils.cli import get_matrix_servers
from raiden.utils.datastructures import merge_dict
from raiden_contracts.utils.type_aliases import ChainID

ENV_KEY_KNOWN_SERVERS = "URL_KNOWN_FEDERATION_SERVERS"


class MatrixPowerLevels(IntEnum):
    USER = 0
    MODERATOR = 50
    ADMINISTRATOR = 100


log = get_logger(__name__)


class EnsurerError(Exception):
    pass


class MultipleErrors(EnsurerError):
    pass


@dataclass(frozen=True)
class RoomInfo:
    room_id: str
    aliases: Set[str]
    server_name: str


class RoomEnsurer:
    def __init__(
        self,
        username: str,
        password: str,
        own_server_name: str,
        known_servers_url: Optional[str] = None,
    ):
        self._username = username
        self._password = password
        self._own_server_name = own_server_name

        if known_servers_url is None:
            known_servers_url = DEFAULT_MATRIX_KNOWN_SERVERS[Environment.PRODUCTION]

        self._known_servers: Dict[str, str] = {
            urlparse(server_url).netloc: server_url
            for server_url in get_matrix_servers(
                known_servers_url, server_list_type=ServerListType.ALL_SERVERS
            )
        }
        if not self._known_servers:
            raise RuntimeError(f"No known servers found from list at {known_servers_url}.")
        self._first_server_name = list(self._known_servers.keys())[0]
        self._is_first_server = own_server_name == self._first_server_name
        self._apis: Dict[str, GMatrixHttpApi] = self._connect_all()
        self._own_api = self._apis[own_server_name]

        log.debug(
            "Room ensurer initialized",
            own_server_name=own_server_name,
            known_servers=self._known_servers.keys(),
            first_server_name=self._first_server_name,
            is_first_server=self._is_first_server,
        )

    def ensure_rooms(self) -> None:
        exceptions = {}
        for network in Networks:
            for alias_fragment in [
                DISCOVERY_DEFAULT_ROOM,
                MONITORING_BROADCASTING_ROOM,
                PATH_FINDING_BROADCASTING_ROOM,
            ]:
                try:
                    room_alias_prefix = make_room_alias(ChainID(network.value), alias_fragment)
                    self._first_server_actions(room_alias_prefix)
                    log.info(f"Ensuring {alias_fragment} room for {network.name}")
                    self._ensure_room_for_network(room_alias_prefix)
                except (MatrixError, EnsurerError) as ex:
                    log.exception(f"Error while ensuring room for {network.name}.")
                    exceptions[network] = ex
        if exceptions:
            log.error("Exceptions happened", exceptions=exceptions)
            raise MultipleErrors(exceptions)

    def _first_server_actions(self, room_alias_prefix: str) -> None:
        room_info = self._get_room(self._first_server_name, room_alias_prefix)

        # if it is the first server in the list and no room is found, create room
        if self._is_first_server and room_info is None:
            log.info("Creating room", server_name=self._own_server_name)
            first_server_room_info = self._create_room(room_alias_prefix)
            log.info(
                "Room created. Waiting for other servers to join.",
                room_aliases=first_server_room_info.aliases,
                room_id=first_server_room_info.room_id,
            )

    def _ensure_room_for_network(self, room_alias_prefix: str) -> None:

        room_infos: Dict[str, Optional[RoomInfo]] = {
            server_name: self._get_room(server_name, room_alias_prefix)
            for server_name in self._known_servers.keys()
        }

        ensure_room_info = None

        # find first available room info sorted by known_servers list
        # if first server is not available then try to ensure with second, and so on
        for server_name, room_info in room_infos.items():
            log.info(f"trying to ensure with: {server_name}")
            ensure_room_info = room_info
            if ensure_room_info:
                break

        # This means own server has not joined yet and no other servers available
        if ensure_room_info is None:
            log.warning("No other servers available. Cannot join the rooms. Doing nothing.")
            return

        has_unavailable_rooms = all(room_infos.values())

        are_all_available_rooms_the_same = all(
            room_info.room_id == ensure_room_info.room_id
            for room_info in room_infos.values()
            if room_info is not None and ensure_room_info is not None
        )

        if has_unavailable_rooms:
            log.warning(
                "Could not connect to all servers or room could not be found. Those cannot be ensured.",
                offline_servers=[
                    server_name
                    for server_name, room_info in room_infos.items()
                    if room_info is None
                ],
            )

        if not are_all_available_rooms_the_same:
            log.warning(
                "Room id mismatch",
                alias_prefix=room_alias_prefix,
                expected=ensure_room_info.room_id,
                found={
                    server_name: room_info.room_id
                    for server_name, room_info in room_infos.items()
                    if room_info is not None
                },
            )

        if not has_unavailable_rooms and are_all_available_rooms_the_same:
            log.info(
                "Room state ok.",
                server_rooms={
                    server_name: room_info.room_id if room_info else None
                    for server_name, room_info in room_infos.items()
                },
            )
            return

        # There are either mis
        own_server_room_info = room_infos.get(self._own_server_name)
        own_server_room_alias = f"#{room_alias_prefix}:{self._own_server_name}"
        first_server_room_alias = f"#{room_alias_prefix}:{self._first_server_name}"

        if not own_server_room_info:
            log.warning(
                "Room missing on own server, adding alias",
                server_name=self._own_server_name,
                room_id=ensure_room_info.room_id,
                new_room_alias=own_server_room_alias,
            )
            self._join_and_alias_room(first_server_room_alias, own_server_room_alias)
            log.info("Room alias set", alias=own_server_room_alias)

        elif own_server_room_info.room_id != ensure_room_info.room_id:
            log.warning(
                "Conflicting local room, reassigning alias",
                server_name=self._own_server_name,
                expected_room_id=ensure_room_info.room_id,
                current_room_id=own_server_room_info.room_id,
            )
            self._own_api.remove_room_alias(own_server_room_alias)
            self._join_and_alias_room(first_server_room_alias, own_server_room_alias)
            log.info(
                "Room alias updated",
                alias=own_server_room_alias,
                room_id=ensure_room_info.room_id,
            )
        else:
            log.warning("Mismatching rooms on other servers. Doing nothing.")

        # Ensure that all admins have admin power levels
        self._ensure_admin_power_levels(own_server_room_info)

    def _join_and_alias_room(
        self, first_server_room_alias: str, own_server_room_alias: str
    ) -> None:
        response = self._own_api.join_room(first_server_room_alias)
        own_room_id = response.get("room_id")
        if not own_room_id:
            raise EnsurerError("Couldn't join first server room via federation.")
        log.debug("Joined room on first server", own_room_id=own_room_id)
        self._own_api.set_room_alias(own_room_id, own_server_room_alias)

    def _get_room(self, server_name: str, room_alias_prefix: str) -> Optional[RoomInfo]:
        api = self._apis[server_name]
        if api is None:
            return None

        room_alias_local = f"#{room_alias_prefix}:{server_name}"
        try:
            response = api.join_room(room_alias_local)
            room_id = response.get("room_id")
            if not room_id:
                log.debug("Couldn't find room", room_alias=room_alias_local)
                return None
            room_state = api.get_room_state(response["room_id"])
        except MatrixError:
            log.debug("Room doesn't exist", room_alias=room_alias_local)
            return None
        existing_room_aliases = set(
            chain.from_iterable(
                event["content"]["aliases"]
                for event in room_state
                if event["type"] == "m.room.aliases"
            )
        )

        log.debug(
            "Room aliases", server_name=server_name, room_id=room_id, aliases=existing_room_aliases
        )
        return RoomInfo(room_id=room_id, aliases=existing_room_aliases, server_name=server_name)

    def _create_server_user_power_levels(self) -> Dict[str, Any]:

        server_admin_power_levels: Dict[str, Union[int, Dict[str, int]]] = {
            "users": {},
            "users_default": MatrixPowerLevels.USER,
            "events": {
                "m.room.power_levels": MatrixPowerLevels.ADMINISTRATOR,
                "m.room.history_visibility": MatrixPowerLevels.ADMINISTRATOR,
            },
            "events_default": MatrixPowerLevels.USER,
            "state_default": MatrixPowerLevels.MODERATOR,
            "ban": MatrixPowerLevels.MODERATOR,
            "kick": MatrixPowerLevels.MODERATOR,
            "redact": MatrixPowerLevels.MODERATOR,
            "invite": MatrixPowerLevels.MODERATOR,
        }

        for server_name in self._known_servers:
            username = f"admin-{server_name}".replace(":", "-")
            user_id = f"@{username}:{server_name}"
            server_admin_power_levels["users"][user_id] = MatrixPowerLevels.ADMINISTRATOR

        own_user_id = f"@{self._username}:{self._own_server_name}"
        server_admin_power_levels["users"][own_user_id] = MatrixPowerLevels.ADMINISTRATOR

        return server_admin_power_levels

    def _ensure_admin_power_levels(self, room_info: Optional[RoomInfo]) -> None:
        if not room_info:
            return

        log.info(f"Ensuring power levels for {room_info.aliases}")
        api = self._apis[self._own_server_name]
        own_user = f"@{self._username}:{self._own_server_name}"
        supposed_power_levels = self._create_server_user_power_levels()

        try:
            current_power_levels = api.get_room_state_type(
                room_info.room_id, "m.room.power_levels", ""
            )
        except MatrixError:
            log.debug("Could not fetch power levels", room_aliases=room_info.aliases)
            return

        if own_user not in current_power_levels["users"]:
            log.warning(
                f"{own_user} has not been granted administrative power levels yet. Doing nothing."
            )
            return

        # the supposed power level dict could be just a subset of the current
        # because providers who left cannot be removed from other admins
        if set(supposed_power_levels["users"].keys()).issubset(
            set(current_power_levels["users"].keys())
        ):
            log.debug(f"Power levels are up to date. Doing nothing.")
            return

        merge_dict(current_power_levels, supposed_power_levels)
        try:
            api.set_power_levels(room_info.room_id, supposed_power_levels)
        except MatrixError:
            log.debug("Could not set power levels", room_aliases=room_info.aliases)

    def _create_room(self, room_alias_prefix: str) -> RoomInfo:
        api = self._apis[self._own_server_name]
        server_admin_power_levels = self._create_server_user_power_levels()
        response = api.create_room(
            room_alias_prefix,
            is_public=True,
            power_level_content_override=server_admin_power_levels,
        )

        room_alias = f"#{room_alias_prefix}:{self._own_server_name}"
        return RoomInfo(response["room_id"], {room_alias}, self._own_server_name)

    def _connect_all(self) -> Dict[str, GMatrixHttpApi]:
        jobs = {
            gevent.spawn(self._connect, server_name, server_url)
            for server_name, server_url in self._known_servers.items()
        }
        gevent.joinall(jobs)

        return {
            server_name: matrix_api
            for server_name, matrix_api in (job.get() for job in jobs if job.get())
        }

    def _connect(self, server_name: str, server_url: str) -> Optional[Tuple[str, GMatrixHttpApi]]:
        log.debug("Connecting", server=server_name)
        api = GMatrixHttpApi(server_url)
        username = self._username
        password = self._password

        if server_name != self._own_server_name:
            signer = make_signer()
            username = str(to_normalized_address(signer.address))
            password = encode_hex(signer.sign(server_name.encode()))

        try:
            response = api.login(
                "m.login.password", user=username, password=password, device_id="room_ensurer"
            )
            api.token = response["access_token"]
        except MatrixHttpLibError:
            log.warning("Could not connect to server", server_url=server_url)
            return None
        except MatrixRequestError:
            log.warning("Failed to login to server", server_url=server_url)
            return None

        log.debug("Connected", server=server_name)
        return server_name, api


@click.command()
@click.option("--own-server", required=True)
@click.option(
    "-i",
    "--interval",
    default=3600,
    help="How often to perform the room check. Set to 0 to disable.",
)
@click.option("-l", "--log-level", default="INFO")
@click.option("-c", "--credentials-file", required=True, type=click.File("rt"))
def main(own_server: str, interval: int, credentials_file: TextIO, log_level: str) -> None:
    configure_logging(
        {"": log_level, "raiden": log_level, "__main__": log_level}, disable_debug_logfile=True
    )
    known_servers_url = os.environ.get(ENV_KEY_KNOWN_SERVERS)

    try:
        credentials = json.loads(credentials_file.read())
        username = credentials["username"]
        password = credentials["password"]

    except (JSONDecodeError, UnicodeDecodeError, OSError, KeyError):
        log.exception("Invalid credentials file")
        sys.exit(1)

    while True:
        try:
            room_ensurer = RoomEnsurer(username, password, own_server, known_servers_url)
        except MatrixError:
            log.exception("Failure while communicating with matrix servers. Retrying in 60s")
            gevent.sleep(60)
            continue

        try:
            room_ensurer.ensure_rooms()
        except EnsurerError:
            log.error("Retrying in 60s.")
            gevent.sleep(60)
            continue

        if interval == 0:
            break

        log.info("Run finished, sleeping.", duration=interval)
        gevent.sleep(interval)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
