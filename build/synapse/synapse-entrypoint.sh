#!/bin/bash

set -e

# Ensure data dirs exist
mkdir -p /data/log
mkdir -p /data/keys

TYPE="$1"
shift

if [[ $TYPE == 'worker' ]]; then
  echo "WORKERS ARE DISABLED!"
  exit 1
  WORKER="$1"
  shift
  CONFIG_PATH=$(/synapse-venv/bin/python /bin/render_config_template.py "$TYPE" --type "$WORKER")

  /synapse-venv/bin/python -m "synapse.app.${WORKER}" --config-path /config/synapse.yaml --config-path "${CONFIG_PATH}"
elif [[ $TYPE == 'synapse' ]]; then
  /synapse-venv/bin/python /bin/render_config_template.py "$TYPE"
  /synapse-venv/bin/python -m synapse.app.homeserver --config-path /config/synapse.yaml --generate-keys

  /synapse-venv/bin/python -m synapse.app.homeserver --config-path /config/synapse.yaml
else
  echo "Unknown run type: $TYPE"
  exit 1
fi
