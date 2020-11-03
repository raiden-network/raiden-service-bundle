FROM rust
LABEL maintainer="Raiden Network Team <contact@raiden.network>"
RUN apt-get update && apt-get -y install postgresql-client && apt-get clean

RUN cargo install --git https://github.com/erikjohnston/synapse-find-unreferenced-state-groups

COPY state_group_cleaner.sh /state_group_cleaner.sh
COPY clean_and_vacuum.sql /clean_and_vacuum.sql

ENTRYPOINT ["/state_group_cleaner.sh"]
