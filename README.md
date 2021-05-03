# Raiden Service Bundle (RSB)

## What is this repository

This repository contains the documentation and configuration necessary to run a
Raiden Service Bundle.

**Current release:** [Latest](https://github.com/raiden-network/raiden-service-bundle/releases/latest)

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
  - [Hardware](#hardware)
  - [Software](#software)
- [Installation](#installation)
- [Upgrades](#upgrades)
- [Known issues](#known-issues)
- [Contact / Troubleshooting](#contact-troubleshooting)
- [Changelog](#changelog)

## Overview

The Raiden Network uses a federation of [Matrix](https://matrix.org) servers as
its transport layer and a set of services for improved usability. This set of
services is called the Raiden Service Bundle. To ensure reliability,
availability and neutrality it is desirable that those services are being
operated by multiple independent entities.

Therefore we provide this repository which allows easy setup of such a service
bundle. It uses docker and docker-compose for easy installation and upgrades.

Currently only this single-server configuration is supported; in the future we
may also provide configurations with services split among multiple servers.

### Used software

- docker
- docker-compose
- Synapse
- Postgres
- Traefik
- Raiden Services (Pathfinding, Monitoring)

### Structure


```
+-------------------+
|                   |
|   Raiden clients  |
|                   |
+---------+---------+
          |https://
==========|==========
          |
+---------v---------+                       Federation to
|                 +-+-------------------->  other Raiden
|      Traefik    | |                       Matrix servers
|                 |-+---------+----------------------+
+---------+-------+-+         |                      |
          |       |           |                      |
+---------v-------v-+   +-----v----------------+ +---v-----------------+
|                   |   |                      | |                     |
|      Synapse      |   |  Raiden Pathfinding  | |  Raiden Monitoring  |
|                   |   |                      | |                     |
+---------+---------+   +-------------------+--+ +-+-------------------+
          |                                 |      |
+---------v---------+                     +-v- - - v -+
|                   |                     |
|     Postgres      |                        ETH_RPC  |
|                   |                     |
+-------------------+                     + - - - - - +
```


We use Traefik as a reverse proxy and also utilize its capability of
automatically provisioning Let's Encrypt TLS certificates.

The Synapse server is being run in the so-called split worker configuration
which increases throughput.

The database stores the message data. Since the transport layer is considered
ephemeral in Raiden it is not necessary to arrange for backups of the database
data.

### Network

After a successful deployment the following ports will be in use:

- 80 - HTTP
  - Redirects to HTTPS
  - Let's Encrypt HTTP challenge for certificate provisioning
- 443 - HTTPS
  - Synapse (on subdomain `transport.$<SERVER_NAME>`)
    - Client API access
    - Server-to-Server federation
  - Raiden Pathfinding Server (on subdomain `pfs.$<SERVER_NAME>`)
  - Metrics export (IP restricted, see below)

## Requirements

### Hardware

Minimum recommended for a production setup:

- 16 GiB RAM
-  8 Cores
- 50 GiB SSD

Note: The default Postgres configuration assumes 16GiB of system RAM

### Software

- Docker >= 17.12
- docker-compose >= 1.21.0

### Other

- A domain (or subdomain) for exclusive use by this server
- To ensure acceptable performance the server should be reserved for exclusive use by the RSB.

## Installation

### Preparation

1. Provision a server that meets the [hardware](#hardware) and [software](#software) requirements listed above.
1. Ensure a domain (or subdomain) is available

   Examples:
   - raiden.somedomain.com
   - raiden-service-bundle-somecompany.tld

1. Configure `A` (and optionally `AAAA`) DNS records for the domain pointing to the servers IP address(es)
1. Configure a `CNAME` DNS record for `*.<domain>` pointing back to `<domain>`


**NOTE:**

If you intend to use a subdomain it is important to be aware of the security implications.
Sudomains share Cookies and Browser LocalStoarage with the apex domain.
Therefore we strongly suggest that a subdomain is only used below an apex domain that does *not*
host an application that relies on either Cookies or LocalStorage for security relevant purposes (e.g. user authentication).


### Installing the RSB

**NOTE:**
This document will sometimes display release candidate versions, also known as pre-releases in the section below. You
can identify this, if there is an `rcX` at the end of the version (E.g. `2019.03.0rc5`). When in doubt, always check against the
[latest full release](https://github.com/raiden-network/raiden-service-bundle/releases/latest). If the version is
different from what you see below, you should stick to the "full release" and replace the version accordingly.

1. Clone the [current release version of this repository](https://github.com/raiden-network/raiden-service-bundle/tree/2021.02.0rc2)
   to a suitable location on the server:

   ```shell
   git clone -b 2021.02.0rc2 https://github.com/raiden-network/raiden-service-bundle.git
   ```
1. Copy `.env.template` to `.env` and modify the values to fit your setup. Please read [Configuring the `.env` file](#configuring-the-env-file) for detailed information.
   - We would appreciate it if you allow us access to the monitoring interfaces
     (to do that uncomment the default values of the `CIDR_ALLOW_METRICS` and `CIDR_ALLOW_PROXY` settings).
   - We also recommend that you provide your own monitoring. The setup of which is currently out of scope of this document.
   - Please read the disclaimers for the path finding and monitoring services carefully and uncomment the variables `<SERVICE>_ACCEPT_DISCLAIMER` if you agree. Note, that without agreement the services won't start.
1. If you haven't done so before, run `./register-service-provider.sh register` (it uses configuration values from `.env`). Please read the information provided [Registering as a RSB Provider](#registering-as-a-rsb-provider) carefully before executing the script.
1. Run `docker-compose up -d` to start all services
   - The services are configured to automatically restart in case of a crash or reboot

**NOTE:**

After a new RSB has been registered and added to the `known_servers.main.yaml` file it can take up
to 24 hours for the information to propagate to existing RSB installations.

During this time some services will not yet be able to start successfully and log
various error messages. This is expected behaviour and will resolve itself.

After the 24h have elapsed all services should run successfully.
See [verifying that the RSB is working](#verifying-that-the-rsb-is-working) below.

### Configuring the `.env` file
After cloning the repository the `.env` file needs to be configured. A template named `.env.template` is provided. Below you find a detailed list of the parameters to be set and their explanations.

- `SERVER_NAME`: The host domain without protocol prefix `https://` respectively
- `LETSENCRYPT_EMAIL`: Email addres to use when requesting LetsEncrypt certificates
- `CIDR_ALLOW_METRICS`: Metrics whitelist. IP address/network whitelists for access to non-public parts of the service. Uses CIDR notation. Separate multiple entries with commas. Example values: 10.0.0.0/16,10.1.2.3/32 or 10.1.2.3/32.
- `CIDR_ALLOW_PROXY`: Proxy metrics / management interface whitelist
- `WORKER_COUNT`: Number of worker processes to start, setting this to the number of CPUs is a good starting point
- `DATA_DIR`: Data dir location. Optional, defaults to ./data in the checkout directory.
- `URL_KNOWN_FEDERATION_SERVERS`: URL to use to fetch federation whitelist - used only for testing
- `KEYSTORE_FILE`: The keystore file which has to be located in ${DATA_DIR}/keystore
- `PASSWORD`: Password to decrypt the keystore file
- `ETH_RPC`: Ethereum RPC URL
- `PFS_ACCEPT_DISCLAIMER`: TRUE or FALSE if you accept the Pathfinding Service disclaimer or not. Read the Disclaimer [here](https://github.com/raiden-network/raiden-services/blob/f4bcb9c289e093754204fe18684e4b57558ea29b/src/pathfinding_service/constants.py#L34)
- `MS_ACCEPT_DISCLAIMER`: TRUE or FALSE if you accept the Monitoring Service disclaimer or not. Read the Disclaimer [here](https://github.com/raiden-network/raiden-services/blob/f4bcb9c289e093754204fe18684e4b57558ea29b/src/monitoring_service/constants.py#L22)
- `CHAIN_ID`: Chain ID of the connected Ethereum node.
- `PFS_SERVICE_FEE`: The Pathfinding Service Fee to be paid for requests
- `PFS_OPERATOR`: Official Operator Name
- `PFS_INFO_MESSAGE`: Info message. Will be displayed on info endpoint.
- `LOG_LEVEL`: 'INFO' or 'DEBUG' recommended


### Registering as a RSB Provider
For your newly deployed Raiden Service Bundle to be used by Raiden nodes it must be registered.

1. **Registering in the Services Registry On-Chain**
  - In order to register as a service provider you need to run the script [`register-service-provider.sh`](https://github.com/raiden-network/raiden-service-bundle/blob/master/register-service-provider.sh)` register`.
  - Make sure that you have configured a keystore file (`$KEYSTORE_FILE` in `.env`). If not, the script will exit with an error and you cannot register as a service provider.
  - Make sure that the configured account has enough funding to register as a service provider.
    You can check the [registry contract](https://etherscan.io/address/0xa80aEc9eebD8058A1468e563C025999590F32C08#readContract) for the current price of a slot.
    You will find the price under `3. currentPrice`. To get the price in RDN divide the value by (10^18).
    The script will also inform you about price as well.


2. **Extending `known_servers/known_servers-production-v1.2.0.json`**
  - In order to be whitelisted in the Matrix Federation, the list needs to be extended with your server name.
  - [Create an issue](https://github.com/raiden-network/raiden-service-bundle/issues/new) and submit the
   domain / URL of the newly deployed server for inclusion in the list of known servers.
   Please, state your server name as you have set `$SERVER_NAME` in your `.env` file.
  - It may take up to 24 hours for the federation to accept the server as a new member. Please note, that until this moment, the pathfinding service and monitoring service cannot run properly as they need to use the broadcasting rooms. Once the new server is accepted as part of the federation, all services will restart automatically.


#### Interacting with the service registry contract
Besides the subcommand `register` which can be used to register as a RSB provider, there are several other subcommands to interact with the service registry contract.

Commands:

- *extend*    Extend the duration of a service registration
- *info*      Show information about current registration and deposits
- *register*  Registers the address of a service deployment with the...
- *withdraw*  Withdraw tokens deposited to the ServiceRegistry.

You can call [`register-service-provider.sh`](https://github.com/raiden-network/raiden-service-bundle/blob/master/register-service-provider.sh)` <command>` to use them.

### Verifying that the RSB is working

Check the status of the services by executing `docker-compose ps`.
If any services are in a state other than `Up`, `Up (healthy)` or `Exit 0` after the elapse of the 24h waiting period a configuration problem is the most likely cause.
See [troubleshooting the RSB installation](#troubleshooting-the-rsb-installation) below in that case.

- Matrix
  - Check that the following endpoints return a successful response (HTTP status 200):
    - `https://transport.<SERVER_NAME>/_matrix/client/versions`

- PFS
  - Check that the `latest_committed_block` is increasing regularly:

    `docker-compose logs --tail 100 pfs | grep latest_committed_block`
  - Check that the following endpoint returns a successful response (HTTP status 200):
    - `https://pfs.<SERVER_NAME>/api/v1/info`

- MS
  - Check that the `latest_confirmed_block` is increasing regularly:

    `docker-compose logs --tail 100 ms | grep latest_confirmed_block`


### Troubleshooting the RSB installation

If you experience any unexpected behavior while installing the RSB, please do not hesitate to contact the development team. The fastet way to reach out to us is via the plublic [Raiden Gitter channel](https://gitter.im/raiden-network/raiden).
Otherwise, you can also open an issue in this repository with the predefined template for a [bug report](https://github.com/raiden-network/raiden-service-bundle/issues/new?template=bug_report.md)


## Upgrades

To upgrade to a new release please refer to the [`upgrading document`](./UPGRADING.md) for any
necessary configuration changes.

Afterwards run the following commands:

```shell
git fetch origin --tags
git reset --hard <new-release-tag>
docker-compose pull
docker-compose up -d
```
## Notes:

 - A 'purger' service will run once a day, removing inactive users from global rooms
  to save disk space and processing performance.
 - If necessary it will restart the ``synapse`` service to fetch an up-to-date
  whitelist of servers.

## Known issues

### Protection against Spam / (D)DoS attacks

There is currently only some protection against Spam and / or DDoS attacks.
This will be addressed in future updates.

### Known servers

The known servers the Raiden clients try to connect to are currently tracked in
the *.yml files in this repository. These lists are used by Raiden clients when
the ``--matrix-server=auto`` (default) option is used, for automatically
selecting a transport server, based on response times. We intend to change this
in the future to use a decentralized scheme (for example an on-chain registry).


## Contact / Troubleshooting <a name="contact-troubleshooting" />

To report issues or request help with the setup please [open an issue](https://github.com/raiden-network/raiden-service-bundle/issues/new)
or contact us via email at contact@raiden.nework.


## Changelog
See [`CHANGELOG.md`](./CHANGELOG.md).


## Licenses

The code and documentation in this repository are released under the [MIT license](./LICENSE).

This repository contains instructions to install third party software. Those are licensed as follows:

- [Traefik](https://github.com/containous/traefik): [MIT](https://github.com/containous/traefik/blob/6a55772cda1684546a6a5456b6847e0f9b3df44d/LICENSE.md)
- [Synapse](https://github.com/matrix-org/synapse): [Apache 2.0](https://github.com/matrix-org/synapse/blob/047ac0cbba25ccffb93d92b46254a58f48ddaf9c/LICENSE)
- [PostgreSQL](https://www.postgresql.org): [PostgreSQL License](https://www.postgresql.org/about/licence/)
