#!/usr/bin/env bash

set -eo pipefail

## Global parameters
REGULAR_SLEEP=$((3600 * 24 * 7))

# Check for last run (if any)
LAST_FN="$(find /data -iname 'sgs_*.csv'|cut -d'_' -f2|cut -d'.' -f1|head -1)"

if [[ $LAST_FN ]];
then
    LAST_RUN_UTC=$(date --date="$LAST_FN" "+%s")
    TIME_SINCE_LAST_RUN=$(echo "$(date '+%s') - $LAST_RUN_UTC" | bc)
    EARLY_RESTART=$(echo "$TIME_SINCE_LAST_RUN < $REGULAR_SLEEP" | bc)
fi

if [[ $EARLY_RESTART -gt 0 ]];
then
    # Sleep for the remainder of one week
    INITIAL_SLEEP=$(echo "$REGULAR_SLEEP - $TIME_SINCE_LAST_RUN" | bc)
else
    # Select a random start time within the next ~7 days
    INITIAL_SLEEP=$(echo "$(( RANDOM )) * 2.63 * 7" | bc)
fi

date

echo "Sleeping for $INITIAL_SLEEP seconds"
sleep "$INITIAL_SLEEP"

while true;
do
    date
    COMPRESS_ROOMS="${COMPRESS_ROOMS}"
    if [ -z "$COMPRESS_ROOMS" ];
    then
        echo "No rooms to work on, make sure you define 'COMPRESS_ROOMS' in environment"
        exit 1
    fi
    # loop through rooms
    for ROOM in $(printf "%s" "$COMPRESS_ROOMS");
    do
        # Construct a filename
        FN="/data/compress_state-${ROOM}_$(date -Iseconds).sql"

        date
        echo "Compressing state for $ROOM"

        synapse-compress-state -p "postgres://postgres@db/synapse" -r "$ROOM" -o "$FN" -t

        date
        echo "Applying changes for $ROOM"

        # now remotely run psql to apply
        psql -U postgres -h db -w -d synapse -f "$FN"

        date
        echo "Done"
    done

    # Now sleep until next execution
    echo "Sleeping for $REGULAR_SLEEP seconds"
    sleep $REGULAR_SLEEP
done
