# -*- coding: utf-8 -*-
import os
import codecs
import random
import string
import urllib2


PATH_CONFIG = '/config/synapse.yaml'
PATH_CONFIG_TEMPLATE = '/config/synapse.template.yaml'
PATH_MACAROON_KEY = '/data/keys/macaroon.key'
PATH_KNOWN_FEDERATION_SERVERS = '/data/known_federation_servers.yaml'

URL_KNOWN_FEDERATION_SERVERS_DEFAULT = (
    'https://raw.githubusercontent.com/raiden-network/raiden-transport/master/known_servers.yaml'
)


def get_macaroon_key():
    if not os.path.isfile(PATH_MACAROON_KEY):
        alphabet = string.digits + string.ascii_letters + '!@#$%^&*()_-=+{}[]'
        macaroon = ''.join(random.choice(alphabet) for _ in range(30))
        with codecs.open(PATH_MACAROON_KEY, 'w', encoding='utf-8') as fo:
            fo.write(macaroon)
    else:
        with codecs.open(PATH_MACAROON_KEY, 'r', encoding='utf-8') as fi:
            macaroon = fi.read()
    return macaroon


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
        resp = urllib2.urlopen(url_known_federation_servers)
        if 200 <= resp.code < 300:
            with codecs.open(PATH_KNOWN_FEDERATION_SERVERS, 'w', encoding='utf-8') as fo:
                fo.write(resp.read().decode())
        else:
            print('Error fetching known servers list:', resp.code, resp.read().decode())
    except urllib2.URLError as ex:
        print('Error fetching known servers list', ex)
    if os.path.isfile(PATH_KNOWN_FEDERATION_SERVERS):
        with codecs.open(PATH_KNOWN_FEDERATION_SERVERS, 'r', encoding='utf-8') as fi:
            return fi.read()
    return ''


def main():
    template_vars = {
        'MACAROON_KEY': get_macaroon_key(),
        'SERVER_NAME': os.environ['SERVER_NAME'],
        'KNOWN_SERVERS': get_known_federation_servers(),
    }
    with codecs.open(PATH_CONFIG_TEMPLATE, 'r', encoding='utf-8') as fi:
        template_content = fi.read()
    with codecs.open(PATH_CONFIG, 'w', encoding='utf-8') as fo:
        fo.write(
            string.Template(template_content).substitute(**template_vars),
        )


if __name__ == "__main__":
    main()

