#!/usr/bin/env bash

# Select a random start time within the next ~7 days
INITIAL_SLEEP = $(( RANDOM * 2.63 * 7 ))
sleep $INITIAL_SLEEP

while true;
do
    # TODO: stop synapse containers
    # SYNAPSE_CONTAINERS=$(docker ps|grep synapse|cut -d' ' -f1)
    # docker stop -t 600 $SYNAPSE_CONTAINERS

    FN=/data/sgs_$(date -Iseconds).csv

    rust-synapse-find-unreferenced-state-groups -p postgres://postgres@db/synapse -o $FN 

    touch /data/sgs.csv
    rm /data/sgs.csv 
    cp $FN /data/sgs.csv

    # now remotely run psql to delete and vacuum
    psql -u postgres -h db -w -d synapse -f clean_and_vacuum.sql

    # TODO: restart synapse containers
    # docker start $SYNAPSE_CONTAINERS

    # Now sleep for another week
    sleep $((3600 * 24 * 7))
done
