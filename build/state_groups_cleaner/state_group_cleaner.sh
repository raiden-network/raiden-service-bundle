#!/usr/bin/env bash

## Global parameters
WAIT_TO_KILL_SYNAPSE=300
REGULAR_SLEEP=$((3600 * 7 * 24))

# Select a random start time within the next ~7 days
INITIAL_SLEEP=$(echo "$(( RANDOM )) * 2.63 * 7" | bc)
sleep "$INITIAL_SLEEP"

while true;
do
    # Find all running containers with an image name containing "synapse"
    SYNAPSE_CONTAINERS=$(curl -Ssg --unix-socket /var/run/docker.sock \
        -XGET 'http://docker/containers/json?filters={"status":["running"]}' |\
        jq -r '.[] | select(.Image | contains("synapse"))|.Id')

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
            -XGET 'http://docker/containers/json?filters={"status":["running"]}' |\
            jq -r '.[] | select(.Image | contains("synapse"))|.Id')
    done
    echo "All synapses down"

    # Construct a filename
    FN=/data/sgs_$(date -Iseconds).csv

    rust-synapse-find-unreferenced-state-groups -p postgres://postgres@db/synapse -o "$FN"

    touch /data/sgs.csv
    rm /data/sgs.csv
    cp "$FN" /data/sgs.csv

    date

    # now remotely run psql to delete and vacuum
    psql -u postgres -h db -w -d synapse -f clean_and_vacuum.sql

    date

    # restart synapse containers
    for container_id in $SYNAPSE_CONTAINERS;
    do
        curl -Ssg --unix-socket /var/run/docker.sock -XPOST \
        "http://docker/containers/$container_id/start"

    done

    # Now sleep until next execution
    sleep $REGULAR_SLEEP
done
