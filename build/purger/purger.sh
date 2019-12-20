#!/usr/bin/env bash

set -e

echo "======================="
echo -n "Started at: " ; date

# if PURGE_SLEEP_UNTIL env is defined and is a time in the format "%H:%m[:%s]",
# sleep until then before continuing
if [[ -n $PURGE_SLEEP_UNTIL ]]; then
    SLEEP_FOR=$(( ( ( $(date -d "$PURGE_SLEEP_UNTIL" '+%s') - $(date '+%s') ) + 86400 ) % 86400 ))
    echo -n "Sleeping until: " ; date -d "+$SLEEP_FOR seconds"
    sleep $SLEEP_FOR
fi

exec /opt/venv/bin/python3 /purger.py "$@"
