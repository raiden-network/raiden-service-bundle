import os
from pathlib import Path
import random
import string
import urllib.request
from urllib.error import URLError


PATH_CONFIG = Path('/config/synapse.yaml')
PATH_CONFIG_TEMPLATE = Path('/config/synapse.template.yaml')
PATH_MACAROON_KEY = Path('/data/keys/macaroon.key')
PATH_KNOWN_FEDERATION_SERVERS = Path('/data/known_federation_servers.yaml')

URL_KNOWN_FEDERATION_SERVERS_DEFAULT = (
    'https://raw.githubusercontent.com/raiden-network/raiden-transport/master/known_servers.yaml'
)


def get_macaroon_key():
    if not PATH_MACAROON_KEY.is_file():
        alphabet = string.digits + string.ascii_letters + '!@#$%^&*()_-=+{}[]'
        PATH_MACAROON_KEY.write_text(''.join(random.choice(alphabet) for _ in range(30)))
    return PATH_MACAROON_KEY.read_text()


def get_known_federation_servers():
    url_known_federation_servers = os.environ.get(
        'URL_KNOWN_FEDERATION_SERVERS',
        URL_KNOWN_FEDERATION_SERVERS_DEFAULT
    )
    if not url_known_federation_servers:
        # In case the env variable is set but empty
        url_known_federation_servers = URL_KNOWN_FEDERATION_SERVERS_DEFAULT
    print('Fetching known federation servers from:', url_known_federation_servers)
    try:
        resp = urllib.request.urlopen(url_known_federation_servers)
        if 199 < resp.status < 300:
            PATH_KNOWN_FEDERATION_SERVERS.write_text(resp.read().decode())
        else:
            print('Error fetching known servers list:', resp.status, resp.read().decode())
    except URLError as ex:
        print('Error fetching known servers list', ex)
    if PATH_KNOWN_FEDERATION_SERVERS.is_file():
        return PATH_KNOWN_FEDERATION_SERVERS.read_text()
    return ''


def main():
    template_vars = {
        'MACAROON_KEY': get_macaroon_key(),
        'SERVER_NAME': os.environ['SERVER_NAME'],
        'KNOWN_SERVERS': get_known_federation_servers(),
    }
    template_content = PATH_CONFIG_TEMPLATE.read_text()
    PATH_CONFIG.write_text(
        string.Template(template_content).substitute(**template_vars)
    )


if __name__ == "__main__":
    main()

