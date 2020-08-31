import json
import os
import random
import string
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

import click
from docker import Client

PATH_CONFIG_SYNAPSE = Path("/config/synapse.yaml")
PATH_CONFIG_TEMPLATE_SYNAPSE = Path("/config/synapse.template.yaml")
PATH_CONFIG_WORKER_BASE = Path("/config/workers/")
PATH_CONFIG_TEMPLATE_WORKER = Path("/config/worker.template.yaml")

PATH_MACAROON_KEY = Path("/data/keys/macaroon.key")
PATH_ADMIN_USER_CREDENTIALS = Path("/config/admin_user_cred.json")
PATH_KNOWN_FEDERATION_SERVERS = Path("/data/known_federation_servers.json")
PATH_WELL_KNOWN_FILE = Path("/data_well_known/server")

# This file gets created during docker build from the given Raiden version
PATH_KNOWN_FEDERATION_SERVERS_DEFAULT_URL = Path("/known_servers.default.txt")


def get_macaroon_key() -> str:
    if not PATH_MACAROON_KEY.exists():
        alphabet = string.digits + string.ascii_letters + "!@#$%^&*()_-=+{}[]"
        macaroon = "".join(random.choice(alphabet) for _ in range(30))
        PATH_MACAROON_KEY.write_text(macaroon)
    else:
        macaroon = PATH_MACAROON_KEY.read_text()
    return macaroon


def get_known_federation_servers(url_known_federation_servers: Optional[str]) -> str:
    if not url_known_federation_servers:
        # Env variable not set or empty, use default
        url_known_federation_servers = PATH_KNOWN_FEDERATION_SERVERS_DEFAULT_URL.read_text()
    print("Fetching known federation servers from:", url_known_federation_servers)
    try:
        resp = urlopen(url_known_federation_servers)
        if 200 <= resp.code < 300:
            try:
                known_servers = json.loads(resp.read().decode())
                PATH_KNOWN_FEDERATION_SERVERS.write_text(
                    "".join(f"- {server}\n" for server in known_servers["all_servers"])
                )
            except (JSONDecodeError, KeyError):
                print("Error loading known servers list:", resp.code, resp.read().decode())
        else:
            print("Error fetching known servers list:", resp.code, resp.read().decode())
    except URLError as ex:
        print("Error fetching known servers list", ex)
    if PATH_KNOWN_FEDERATION_SERVERS.exists():
        return PATH_KNOWN_FEDERATION_SERVERS.read_text()
    return ""


def render_synapse_config(server_name: str, url_known_federation_servers: Optional[str]) -> None:
    template_content = PATH_CONFIG_TEMPLATE_SYNAPSE.read_text()
    rendered_config = string.Template(template_content).substitute(
        MACAROON_KEY=get_macaroon_key(),
        SERVER_NAME=server_name,
        KNOWN_SERVERS=get_known_federation_servers(url_known_federation_servers),
    )
    PATH_CONFIG_SYNAPSE.write_text(rendered_config)


def render_well_known_file(server_name: str) -> None:
    content = {"m.server": f"{server_name}:443"}
    PATH_WELL_KNOWN_FILE.write_text(json.dumps(content, indent=2))


def generate_admin_user_credentials() -> None:
    """
    Generate the username "admin-{server-name}" and a random password combination
    that will be used by various tools in the
    package to authenticate as an admin user via the ``AdminUserAuthProvider``.
    """
    if PATH_ADMIN_USER_CREDENTIALS.exists():
        return
    username = f"admin-{os.environ['SERVER_NAME']}"
    password = "".join(random.choice(string.digits + string.ascii_lowercase) for _ in range(30))
    PATH_ADMIN_USER_CREDENTIALS.write_text(
        json.dumps({"username": username, "password": password})
    )


def main() -> None:
    url_known_federation_servers = os.environ.get("URL_KNOWN_FEDERATION_SERVERS")
    server_name = os.environ["SERVER_NAME"]

    render_synapse_config(
        server_name=server_name, url_known_federation_servers=url_known_federation_servers
    )
    render_well_known_file(server_name=server_name)
    generate_admin_user_credentials()


if __name__ == "__main__":
    main()
