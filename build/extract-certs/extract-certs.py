import json
import sys
from base64 import b64decode
from datetime import datetime
from pathlib import Path
from time import sleep

import click


def extract(acme_json_path: Path, output_path: Path):
    with acme_json_path.open() as acme_json:
        data = json.load(acme_json)
    certs = data['Certificates']

    for cert_json in certs:
        # Decode private key, certificate and chain
        privatekey = b64decode(cert_json['Key']).decode('utf-8')
        fullchain = b64decode(cert_json['Certificate']).decode('utf-8')
        start = fullchain.find('-----BEGIN CERTIFICATE-----', 1)
        cert = fullchain[0:start]
        chain = fullchain[start:]

        domain = cert_json['Domain']['Main']
        output_path.mkdir(parents=True, exist_ok=True)
        output_path.joinpath(f'{domain}.key').write_text(privatekey)
        output_path.joinpath(f'{domain}.full.crt').write_text(fullchain)
        output_path.joinpath(f'{domain}.crt').write_text(cert)
        output_path.joinpath(f'{domain}.chain.pem').write_text(chain)

        print(f"Extracted certificate for: {domain}")


@click.command()
@click.option('--status-file', type=click.File('w', lazy=False))
@click.argument(
    'acme-json-path',
    type=click.Path(file_okay=True, dir_okay=False, resolve_path=True)
)
@click.argument('output-path', type=click.Path(file_okay=False))
def main(status_file, acme_json_path, output_path):
    acme_json_path = Path(acme_json_path)
    output_path = Path(output_path)

    print('Starting...')

    stat = None
    while True:
        new_stat = None
        try:
            new_stat = acme_json_path.stat()
        except FileNotFoundError:
            print('Waiting for acme json file to appear')
            pass
        if new_stat != stat:
            print("Change detected")
            extract(acme_json_path, output_path)
            stat = new_stat
            status_file.write(datetime.now().isoformat())
            status_file.seek(0)
        sys.stdout.flush()
        sleep(10)


if __name__ == "__main__":
    main()
