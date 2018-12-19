#!/usr/bin/env bash

set -e

echo "======================="
echo -n "Started at: " ; date

if [[ ! -d ./venv ]]; then
    python3 -m venv venv
fi
. ./venv/bin/activate
pip3 install -r requirements.txt

# if PURGE_SLEEP_UNTIL env is defined and is a time in the format "%H:%m[:%s]",
# sleep until then before continuing
if [[ -n $PURGE_SLEEP_UNTIL ]]; then
    SLEEP_FOR=$(( ( ( $(date -d "$PURGE_SLEEP_UNTIL" '+%s') - $(date '+%s') ) + 86400 ) % 86400 ))
    echo -n "Sleeping until: " ; date -d "+$SLEEP_FOR seconds"
    sleep $SLEEP_FOR
fi

exec python3 purge.py "$@"
