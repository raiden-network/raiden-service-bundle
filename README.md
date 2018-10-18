# Raiden Transport

## What is this repository

This repository contains the documentation and configuration necessary to run a 
Raiden Transport Matrix server.

**Current release:** [2018.8.1](https://github.com/raiden-network/raiden-transport/tree/2018.8.1) 

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

The Raiden Network uses a federation of [Matrix](https://matrix.org) servers as it's transport 
layer. To ensure reliability, availability and neutrality it is desirable that those servers are 
being operated by multiple independent entities.

Therefore we provide this repository which allows easy setup of such a transport server. 
It uses docker and docker-compose for easy installation and upgrades. 

Currently only this single-server configuration is supported, in the future we may also 
provide configurations with services split among multiple servers. 

### Used software

- docker
- docker-compose
- Synapse
- Postgres
- Traefik

### Structure


```
+-------------------+
|                   |
|   Raiden clients  |
|                   |
+---------+---------+
          |
==========|==========
          |
+---------v---------+
|                   |
|      Traefik      |  
|                   |
+---------+---------+
          |
+---------v---------+
|                   |
|      Synapse      <-----> Federation to other
|                   |       Raiden Matrix servers
+---------+---------+
          |
+---------v---------+
|                   |
|     Postgres      |
|                   |
+-------------------+
```


We use Traefik as a reverse proxy and also utilize it's capability of automatically provisiong 
Let's Encrypt TLS certificates.

The Synapse server is being run in the so-called split worker configuration which increases throughput.

The database stores the message data. Since the transport layer is considered ephemeral in Raiden it 
is not necessary to arrange for backups of the database data. 

### Network

After a successful deployment the following ports will be in use:

- 80 - HTTP
  - Redirects to HTTPS 
  - Let's Encrypt HTTP challenge for certificate provisioning
- 443 - HTTPS 
  - Synapse web and API client access
  - Metrics export (IP restricted, see below) 
- 8448 - HTTPS
  - Synapse Server-to-Server federation

## Requirements

### Hardware

Minumum recommended for a production setup:

- 16 GiB Ram
- 8 Cores
- 50 GiB SSD

### Software

- Docker >= 17.06
- docker-compose >= 1.16.0

### Other

- A domain (or subdomain) for exclusive use by this server   

## Installation

### Preparation

1. Provision a server that meets the [hardware](#hardware) and [software](#software) requirements listed above.
1. Ensure a domain (or subdomain) is available 
  
   Examples:
   - raidentransport.somecompany.tld
   - raidentransport-somecompany.tld
   - somecompany-raidentransport.tld

1. Configure `A` (and optionally `AAAA`) DNS records for the domain pointing to the servers IP address(es)
1. Configure a `CNAME` DNS record for `*.<domain>` pointing back to `<domain>`

### Installing

1. Clone the [current release version of this repository](https://github.com/raiden-network/raiden-transport/tree/2018.8.1) 
   to a suitable location on the server:
   
   ```shell
   git clone -b 2018.8.1 https://github.com/raiden-network/raiden-transport.git
   ```
1. Copy `.env.template` to `.env` and modify the values to fit your setup (see inline comments for details)
   - We would appreciate it if you allow us access to the monitoring interfaces 
     (to do that uncomment the default values of the `CIDR_ALLOW_METRICS` and `CIDR_ALLOW_PROXY` settings).
   - We also recommend that you provide your own monitoring. The setup of which is currently out of scope of this document. 
1. Run `docker-compose build` to build the containers
1. Run `docker-compose up -d` to start all services
   - The services are configured to automatically restart in case of a crash or reboot
1. A 'purge' script/service will run once a day, prunning old state from rooms to save disk space,
   and restarting the ``synapse`` service to fetch an up-to-date whitelist of servers.
1. Verify the service is up by opening the domain in a browser. You should see the synapse login screen.

### Submit

1. [Create an issue](https://github.com/raiden-network/raiden-transport/issues/new) and submit the 
   domain / URL of the newly deployed server for inclusion in the list of known servers.    

## Upgrades

To upgrade to a new release please check the [changelog](#changelog) for any necessary 
configuration changes and then run the following commands:

```shell
git fetch origin --tags
git reset --hard <new-release-tag>
docker-compose build
docker-compose up -d
```

## Known issues

### Protection against Spam / (D)DoS attacks

There is currently only some protection against Spam and / or DDoS attacks. 
This will be addressed in future updates. 

### Known servers

The known servers the Raiden clients try to connect to are currently tracked in a file in this 
repository and also shipped as a hard-coded list with the Raiden client. 
These lists are used by Raiden clients when the ``--matrix-server=auto`` (default) option is used,
for automatically selecting a transport server, based on response times.


## Contact / Troubleshooting

To report issues or request help with the setup please [open an issue](https://github.com/raiden-network/raiden-transport/issues/new)
or contact us via email at contact@raiden.nework.

## Changelog

- 2018-10-18 - `2018.8.2` - Purge historic state and restart service, no need for a cron service anymore
- 2018-08-09 - `2018.8.1` - **Initial public release**
- 2018-08-02 - `2018.8.0` - **Initial version**
