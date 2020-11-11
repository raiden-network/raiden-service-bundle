#!/usr/bin/env bash

set -eo pipefail

## Global parameters
WAIT_TO_KILL_SYNAPSE=120  # most likely useless, it seems synapse doesn't stop without being forced
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
    # Find all running containers that have a stop label for state_group cleaning
    SYNAPSE_CONTAINERS=$(curl -Ssg --unix-socket /var/run/docker.sock \
        -XGET 'http://docker/containers/json?filters={"status":["running"],"label":["state_groups_cleaner_stop=true"]}' |\
        jq -r '.[].Id')

    CONTAINER_COUNT=$(echo $SYNAPSE_CONTAINERS | wc -w)
    echo "Stopping $CONTAINER_COUNT containers with label 'state_groups_cleaner_stop=true'..."
    # Stop the synapse containers (in background)
    for container_id in $SYNAPSE_CONTAINERS;
    do
        curl -Ssg --unix-socket /var/run/docker.sock -XPOST \
        "http://docker/containers/$container_id/stop?t=$WAIT_TO_KILL_SYNAPSE" &
    done

    # Stop calls were detached, we probe the API to see when we're done
    SYNAPSE_RUNNING=$SYNAPSE_CONTAINERS
    while [[ $SYNAPSE_RUNNING ]];
    do
        sleep 1
        SYNAPSE_RUNNING=$(curl -Ssg --unix-socket /var/run/docker.sock \
            -XGET 'http://docker/containers/json?filters={"status":["running"],"label":["state_groups_cleaner_stop=true"]}' |\
            jq -r '.[].Id')
    done
    echo "All synapses down."

    # Construct a filename
    FN=/data/sgs_$(date -Iseconds).csv

    rust-synapse-find-unreferenced-state-groups -p postgres://postgres@db/synapse -o "$FN"

    cp -f "$FN" /data/sgs.csv

    date

    # now remotely run psql to delete and vacuum
    psql -U postgres -h db -w -d synapse -f clean_and_vacuum.sql

    date

    # restart synapse containers
    for container_id in $SYNAPSE_CONTAINERS;
    do
        curl -Ssg --unix-socket /var/run/docker.sock -XPOST \
        "http://docker/containers/$container_id/start"

    done

    # Now sleep until next execution
    echo "Sleeping for $REGULAR_SLEEP seconds"
    sleep $REGULAR_SLEEP
done
