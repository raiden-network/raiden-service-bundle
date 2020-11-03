### State groups cleaner

This tool will run every 7 days and automatically purge legacy `state_groups` from the synapse db.

It uses https://github.com/erikjohnston/synapse-find-unreferenced-state-groups

The tools expect a network connection to the database at the host `db` with a passwordless connection for the user `postgres` to the database `synapse`. 

It furthermore needs privileges to stop the `synapse` containers for maintenance.
