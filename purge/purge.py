import os
import click
import json
import requests
import psycopg2
import datetime
import time
import docker
from eth_keyfile import extract_key_from_keyfile, create_keyfile_json
from eth_utils import keccak, encode_hex
from eth_keys import keys
from operator import itemgetter
from urllib.parse import urlparse, urljoin, quote


def eth_sign_hash(data: bytes) -> bytes:
    """ eth_sign/recover compatible hasher

    Prefixes data with '\x19Ethereum Signed Message:\n<len(data)>' """
    prefix = b'\x19Ethereum Signed Message:\n'
    if not data.startswith(prefix):
        data = prefix + b'%d%s' % (len(data), data)
    return keccak(data)


@click.command()
@click.argument('db_uri', envvar='MATRIX_DB_URI')
@click.argument('server', envvar='MATRIX_SERVER')
@click.option(
    '--admin-access-token-file',
    default='./admin_access.json',
    show_default=True,
    type=click.Path(dir_okay=False, writable=True),
    help=(
        'JSON file to retrieve and persist "admin_user" and "admin_access_token". '
        'If present, any other --admin-* option is ignored and these credentials are used.'
    ),
)
@click.option(
    '--admin-user',
    help='Full admin user_id. e.g.: @username:server_hostname.com',
)
@click.option(
    '--admin-password',
    help='Admin user password',
)
@click.option(
    '--admin-private-key',
    type=click.Path(dir_okay=False),
    default='admin_key.json',
    help='Admin ETH JSON private key file to derive admin user and password from.',
)
@click.option(
    '--admin-private-key-password',
    help='Admin ETH JSON private key file password. Prompted if needed and not provided.',
)
@click.option(
    '--admin-private-key-generate',
    is_flag=True,
    flag_value=True,
    help=(
        'Generates a private keyfile, encrypted with password, if one does not exist. '
        'This key shouldn\'t be used for transactions, and is only meant to '
        'ease generating a valid ethereum/matrix admin user.'
    ),
)
@click.option(
    '--admin-private-key-print-only',
    is_flag=True,
    flag_value=True,
    help='Print matrix user and password derived from private key and exit',
)
@click.option(
    '--server-name',
    help=(
        'Custom Matrix server name to be used to calculate user_id from private key. '
        'Defaults to server\'s hostname'
    ),
    envvar='SERVER_NAME',
)
@click.option(
    '--admin-set/--no-admin-set',
    default=True,
    show_default=True,
    help=(
        'If true, sets the user as admin in DB. '
        'Requires --admin-user or --admin-private-key'
    ),
)
@click.option(
    '--keep-newer',
    type=int,
    help='Keep events newer than this number of days',
)
@click.option(
    '--keep-min-msgs',
    type=int,
    help='Keep at least this number of message events per room, regardless of --keep-newer',
)
@click.option(
    '--parallel-purges',
    default=10,
    show_default=True,
    type=int,
    help='Max number of purges to run in parallel.',
)
@click.option(
    '--post-sql',
    type=click.File(),
    help=(
        'Pass a SQL script file as parameter to run it on DB after purging. '
        'Useful to run cleanup scripts, like "synapse_janitor.sql".'
    ),
)
@click.option(
    '--docker-restart-label',
    help='If set, search all containers with given label and, if they\'re running, restart them',
)
def purge(
        db_uri,
        server,
        admin_access_token_file,
        admin_user,
        admin_password,
        admin_private_key,
        admin_private_key_password,
        admin_private_key_generate,
        admin_private_key_print_only,
        server_name,
        admin_set,
        keep_newer,
        keep_min_msgs,
        parallel_purges,
        post_sql,
        docker_restart_label,
):
    """ Purge historic data from rooms in a synapse server

    DB_URI: DB connection string: postgres://user:password@netloc:port/dbname
    SERVER: matrix synapse server url, e.g.: http://hostname

    All option can be passed through uppercase environment variables prefixed with 'MATRIX_'
    e.g.: export MATRIX_KEEP_MIN_MSGS=100
    """
    try:
        session = requests.Session()

        # no --server-name, defaults to server hostname
        if not server_name:
            server_name = urlparse(server).hostname

        # admin_access_token_file has priority over everything else, to avoid re-logins
        if os.path.isfile(admin_access_token_file):
            with open(admin_access_token_file, 'r') as fo:
                admin_user, admin_access_token = itemgetter(
                    'admin_user',
                    'admin_access_token',
                )(json.load(fo))
        else:
            if (
                    not admin_user and
                    not os.path.isfile(admin_private_key) and
                    admin_private_key_generate
            ):
                if admin_private_key_password is None:
                    admin_private_key_password = click.prompt(
                        'JSON keyfile password',
                        default='',
                        hide_input=True,
                    )
                with open(admin_private_key, 'w') as fo:
                    json.dump(create_keyfile_json(
                        os.urandom(32),
                        admin_private_key_password.encode(),
                    ), fo, indent=2)

            # derive admin_user and admin_password from private key
            if not admin_user and os.path.isfile(admin_private_key):
                if admin_private_key_password is None:
                    admin_private_key_password = click.prompt(
                        'JSON keyfile password',
                        default='',
                        hide_input=True,
                    )
                pk_bin = extract_key_from_keyfile(
                    admin_private_key,
                    admin_private_key_password.encode(),
                )
                pk = keys.PrivateKey(pk_bin)

                # username is 0x-prefixed lowercase eth address
                admin_user = f'@{pk.public_key.to_address()}:{server_name}'
                # password is server_name signed with key, with eth_sign prefixed hash
                admin_password_bin = pk.sign_msg_hash(
                    eth_sign_hash(server_name.encode()),
                ).to_bytes()
                admin_password = encode_hex(
                    admin_password_bin[:-1] +
                    bytes([admin_password_bin[-1] + 27])  # v += 27
                )
                if admin_private_key_print_only:
                    click.secho(f'PK to Matrix User:     {admin_user}')
                    click.secho(f'PK to Matrix Password: {admin_password}')
                    return

            if admin_user:
                if not admin_password:
                    admin_password = click.prompt(
                        'Admin user password',
                        default='',
                        hide_input=True,
                    )
                response = session.post(
                    urljoin(server, '/_matrix/client/r0/login'),
                    json={
                        'type': 'm.login.password',
                        'user': admin_user,
                        'password': admin_password,
                    },
                )
                assert response.status_code == 200, f'{response!r} => {response.text!r}'
                admin_access_token = response.json()['access_token']
                with open(admin_access_token_file, 'w') as fo:
                    json.dump({
                        'admin_user': admin_user,
                        'admin_access_token': admin_access_token,
                    }, fo, indent=2)

            else:
                raise RuntimeError('No admin_user nor previous access token found')

        if admin_private_key_print_only:
            # only hit if --admin-private-key-print-only passed, but an access token or admin user
            # was already present, or no --admin-private-key file nor --admin-private-key-generate
            return

        with psycopg2.connect(db_uri) as db, db.cursor() as cur:

            # set user as admin in database if needed
            cur.execute(
                'SELECT admin FROM users WHERE name = %s ;',
                (admin_user,),
            )
            if not cur.rowcount:
                raise RuntimeError(f'User {admin_user!r} not found')
            is_admin, = cur.fetchone()
            if admin_set and not is_admin:
                cur.execute(
                    'UPDATE users SET admin=1 WHERE name = %s ;',
                    (admin_user,),
                )
                db.commit()
            elif not is_admin:
                raise RuntimeError(f'User {admin_user!r} is not an admin. See --admin-set option')

            purges = dict()
            def wait_and_purge_room(room_id=None, event_id=None):
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
                                '/_matrix/client/r0/admin/purge_history_status/' + quote(purge_id),
                            ),
                            params={'access_token': admin_access_token},
                        )
                        assert response.status_code == 200, f'{response!r} => {response.text!r}'
                        if response.json()['status'] != 'active':
                            click.secho(f'Finished purge: room {_room_id!r}, purge {purge_id!r}')
                            purges.pop(_room_id)

                if not room_id:
                    return

                body = {'delete_local_events': True}
                if event_id:
                    body['purge_up_to_event_id'] = event_id
                else:
                    body['purge_up_to_ts'] = int(time.time() * 1000)
                response = session.post(
                    urljoin(server, '/_matrix/client/r0/admin/purge_history/' + quote(room_id)),
                    params={'access_token': admin_access_token},
                    json=body,
                )
                if response.status_code == 200:
                    purge_id = response.json()['purge_id']
                    purges[room_id] = purge_id
                    return purge_id

            if not keep_newer and not keep_min_msgs:
                click.confirm(
                    'No --keep-newer nor --keep-min-msgs option provided. Purge all history?',
                    abort=True,
                )

            ts_ms = None
            if keep_newer:
                ts = datetime.datetime.now() - datetime.timedelta(keep_newer)
                ts_ms = int(ts.timestamp() * 1000)

            cur.execute('SELECT room_id FROM rooms ;')
            all_rooms = {row for row, in cur}

            click.secho(f'Processing {len(all_rooms)} rooms')
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
                    {
                        'room_id': room_id,
                        'ts_ms': ts_ms,
                        'keep_min_msgs': keep_min_msgs,
                    },
                )
                if cur.rowcount:
                    event_id, = cur.fetchone()
                    wait_and_purge_room(room_id, event_id)
                # else: room doesn't have messages eligible for purging, skip

            wait_and_purge_room(None)

        if post_sql:
            click.secho(f'Running {post_sql.name!r}')
            with psycopg2.connect(db_uri) as db, db.cursor() as cur:
                cur.execute(post_sql.read())
                click.secho(f'Results {cur.rowcount}:')
                for i, row in enumerate(cur):
                    click.secho(f'{i}: {row}')

    finally:
        if docker_restart_label:
            client = docker.from_env()
            for container in client.containers.list():
                if container.attrs['State']['Status'] == 'running' and\
                        container.attrs['Config']['Labels'].get(docker_restart_label):
                    container.restart(timeout=30)


if __name__ == '__main__':
    purge(auto_envvar_prefix='MATRIX')
