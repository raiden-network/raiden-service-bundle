# Upgrading existing installations
## From `2020.11.1` or earlier

The previous release mistakenly did not upgrade Synapse, so please make sure to reset the database with this upgrade:

This can be done by stopping the entire RSB:

    docker-compose stop

And then removing the postgres data directory (`<DATA_DIR>/db`).

## From `2020.10.3` or earlier

Due to the jump in Synapse version we recommend to wipe the Synapse
database when upgrading.

This can be done by stopping the entire RSB:

    docker-compose stop

And then removing the postgres data directory (`<DATA_DIR>/db`).


## From `2020.06.0`

Due to the significant jump in Synapse version we recommend to wipe the Synapse 
database when upgrading.

This can be done by stopping the entire RSB:

    docker-compose stop

And then removing the postgres data directory (`<DATA_DIR>/db`).


## From releases before `2020.06.0`

We updated our monitoring infrastructure for the Matrix servers. You can opt-in
to share performance metrics which are helpful for further development.

If you would like to do that then set or update the following variables in your
`.env` file (an example is in the `.env.template` file):
- `CIDR_ALLOW_METRICS=64.225.82.119/32`
- `CIDR_ALLOW_PROXY=64.225.82.119/32`


## From releases before `2020.04.0`

Due to significant upgrades in the components of the RSB please consider
deploying a fresh installation instead of upgrading the existing one to avoid
the migration process.

Since the message data is considered ephemeral in Raiden it is not necessary to
perform backups or restore the previous data in a fresh installation.

If you do want to perform the upgrade please read the following sections
carefully.

### Traefik
Traefik has been upgraded to version 2 which has changed the the certificate
storage format.

Due to this format change the file `${DATA_DIR}/traefik/acme.json` must be
deleted. It will automatically be recreated in the new format once Traefik has
acquired fresh certificates.

### Synapse Postgres database

With the upgrade to Synapse `v1.10.1` the recommended database collation setting
has changed. The recommended settings are:
- `LC_COLLATE='C'`
- `LC_CTYPE='C'`

Please refer to the [Synapse database documentation for details](https://github.com/matrix-org/synapse/blob/develop/docs/postgres.md#fixing-incorrect-collate-or-ctype).
