# Raiden Service Bundle (RSB)

## What is this repository

This repository contains the documentation and configuration necessary to run a
Raiden Service Bundle.

**Current release:** [2020.03.0rc1](https://github.com/raiden-network/raiden-service-bundle/tree/2020.03.0rc1)

## Table of Contents

- [Overview](#overview)
- [Requirements](#requirements)
  - [Hardware](#hardware)
  - [Software](#software)
- [Installation](#installation)
- [Upgrades](#upgrades)
- [Known issues](#known-issues)
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
+---+-----------+---+
    |matrix://  |pfs://
====|===========|====
    |           |
+---v-----------v---+                       Federation to
|                 +-+-------------------->  other Raiden
|      Traefik    | |                       Matrix servers
|                 | |
+---------+-------+-+---------+
          |       |           |
+---------v-------v-+   +-----v----------------+ +---------------------+
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
  - Synapse web and API client access
  - Synapse Server-to-Server federation
  - Raiden Pathfinding Server (on subdomain `pfs.$SERVER_NAME`)
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
- No other than this software should be used in production on this server 

## Installation

### Preparation

1. Provision a server that meets the [hardware](#hardware) and [software](#software) requirements listed above.
1. Ensure a domain (or subdomain) is available

   Examples:
   - raiden.somedomain.com

1. Configure `A` (and optionally `AAAA`) DNS records for the domain pointing to the servers IP address(es)
1. Configure a `CNAME` DNS record for `*.<domain>` pointing back to `<domain>`




### Installing the RSB

1. Clone the [current release version of this repository](https://github.com/raiden-network/raiden-service-bundle/tree/2020.03.0rc1)
   to a suitable location on the server:

   ```shell
   git clone -b 2020.03.0rc1 https://github.com/raiden-network/raiden-service-bundle.git
   ```
1. Copy `.env.template` to `.env` and modify the values to fit your setup (see inline comments for details)
   - We would appreciate it if you allow us access to the monitoring interfaces
     (to do that uncomment the default values of the `CIDR_ALLOW_METRICS` and `CIDR_ALLOW_PROXY` settings).
   - We also recommend that you provide your own monitoring. The setup of which is currently out of scope of this document.
   - Please, read carefully the disclaimers for the path finding and monitoring service and uncomment the variables `XX_ACCEPT_DISCLAIMER` if you agree. Note, that the services won't start if you do not. 
1. Make sure, that the account, configured in `KEYSTORE_FILE`, has enough funding to register as a service operator (you might want to have a look at *Registering as a RSB Provider* below first). Make sure that the account is stored in `${DATA_DIR}/KEYSTORE/`.
1. If you haven't done so before, run `./register-service-provider.sh` (it uses configuration values from `.env`).
1. Run `docker-compose up -d` to start all services
   - The services are configured to automatically restart in case of a crash or reboot

---
**NOTE**

Being accepted in the whitelist as a part of the federation currently takes up to 24 hours after your server name has been added to `known_servers.main.yaml`. After running `docker-compose up -d` you will likely encounter errors but you don't need to worry about them as they will resolve over time. The RSB is configured to restart upon failure automatically. Please verify that your RSB is connected and running successfully after a period of 24 hours.

---

### Registering as a RSB Provider
If you want to participate in the network by running a Raiden Service Bundle you need to register yourself as a provider. Currently, there are two conditions that must be fulfilled to run the RSB successfully.

1. **Registering in the Services Registry On-Chain**  
  - In order to register as a service provider you need to run the script `register-service-provider.sh` as described in step 3 and 4 in *Installing the RSB* written below. 

2. **Extending `known_servers.main.yaml`**  
  - In order to be whitelisted in the Matrix Federation, the list needs to be extended with your server name. Open an issue in this repository with the request to be added to the list. Please, state your server name as you have set `$SERVER_NAME` in your `.env` file.


### Verifying that the RSB is working

- Matrix

- PFS

- MS


### Troubleshooting
After starting, you can run `docker-compose ps` -- if any services are not in `Up`, `Up (healthy)` or `Exit 0` state, you should check the respective logs for configuration errors.
Note: some services might need a few minutes to become healthy.

### Submit a Transport Server to the federation

1. [Create an issue](https://github.com/raiden-network/raiden-service-bundle/issues/new) and submit the
   domain / URL of the newly deployed server for inclusion in the list of known servers.

## Upgrades

To upgrade to a new release please check the [changelog](#changelog) for any
necessary configuration changes and then run the following commands:

```shell
git fetch origin --tags
git reset --hard <new-release-tag>
docker-compose pull
docker-compose up -d
```
## Notes:

 - A 'purge' script/service will run once a day, pruning old state from rooms to save disk space,
   and restarting the ``synapse`` service to fetch an up-to-date whitelist of servers.

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


## Contact / Troubleshooting

To report issues or request help with the setup please [open an issue](https://github.com/raiden-network/raiden-service-bundle/issues/new)
or contact us via email at contact@raiden.nework.


## Changelog
See `CHANGELOG.md`.

## Licenses

The code and documentation in this repository are released under the [MIT license](LICENSE).

This repository contains instructions to install third party software. Those are licensed as follows:

- [Traefik](https://github.com/containous/traefik): [MIT](https://github.com/containous/traefik/blob/6a55772cda1684546a6a5456b6847e0f9b3df44d/LICENSE.md)
- [Synapse](https://github.com/matrix-org/synapse): [Apache 2.0](https://github.com/matrix-org/synapse/blob/047ac0cbba25ccffb93d92b46254a58f48ddaf9c/LICENSE)
- [PostgreSQL](https://www.postgresql.org): [PostgreSQL License](https://www.postgresql.org/about/licence/)
