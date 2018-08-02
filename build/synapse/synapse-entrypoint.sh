#!/bin/bash

# Ensure data dirs exist
mkdir -p /data/log
mkdir -p /data/keys

python3 /bin/render_config_template.py
/synapse-venv/bin/python -m synapse.app.homeserver --config-path /config/synapse.yaml --generate-keys
/synapse-venv/bin/python -m synapse.app.homeserver --config-path /config/synapse.yaml
