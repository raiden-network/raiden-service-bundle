FROM rust
LABEL maintainer="Raiden Network Team <contact@raiden.network>"
RUN apt-get update && \
    apt-get -y install postgresql-client jq bc && \
    apt-get clean

RUN cargo install --git https://github.com/matrix-org/rust-synapse-compress-state

COPY compress_state.sh /compress_state.sh
RUN chmod +x /compress_state.sh

ENTRYPOINT ["/compress_state.sh"]
