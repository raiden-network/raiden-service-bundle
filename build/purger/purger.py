import datetime
import json
import sys
import time
from json import JSONDecodeError
from operator import itemgetter
from typing import Any, Dict, TextIO
from urllib.parse import quote, urljoin

import click
import requests
import yaml
from matrix_client.errors import MatrixError

import docker
import psycopg2
from raiden.network.transport.matrix.client import GMatrixHttpApi

URL_KNOWN_FEDERATION_SERVERS_DEFAULT = (
    "https://raw.githubusercontent.com/raiden-network/raiden-transport/master/known_servers.yaml"
)
SYNAPSE_CONFIG_PATH = "/config/synapse.yaml"


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

    finally:
        if docker_restart_label:
            client = docker.from_env()
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


if __name__ == "__main__":
    purge(  # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
        auto_envvar_prefix="MATRIX"
    )
