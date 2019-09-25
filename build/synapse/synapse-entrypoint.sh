#!/bin/bash

# Ensure data dirs exist
mkdir -p /data/log
mkdir -p /data/keys

/synapse-venv/bin/python /bin/render_config_template.py
/synapse-venv/bin/python -m synapse.app.homeserver --config-path /config/synapse.yaml --generate-keys
exec /synapse-venv/bin/python -m synapse.app.homeserver --config-path /config/synapse.yaml --config-path /config/workers/homeserver.yaml
