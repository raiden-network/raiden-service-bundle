# Upgrading existing installations

## From releases before `2020.04.0`

Due to significant upgrades in the components of the RSB please consider deploying a fresh 
installation instead of upgrading the existing one to avoid the migration process.

Since the message data is considered ephemeral in Raiden it is not necessary to perform backups or 
restore the previous data in a fresh installation.   

If you do want to perform the upgrade please read the following sections carefully.

### Traefik
Traefik has been upgraded to version 2 which has changed the the certificate storage format.

Due to this format change the file `${DATA_DIR}/traefik/acme.json` must be deleted. 
It will automatically be recreated in the new format once Traefik has acquired fresh certificates.      

### Synapse Postgres database

With the upgrade to Synapse `v1.10.1` the recommended database collation setting has changed.
The recommended settings are:
- `LC_COLLATE='C'`
- `LC_CTYPE='C'`

Please refer to the [Synapse database documentation for details](https://github.com/matrix-org/synapse/blob/develop/docs/postgres.md#fixing-incorrect-collate-or-ctype).  
