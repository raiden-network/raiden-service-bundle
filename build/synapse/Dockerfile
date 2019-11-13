FROM python:3.7
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

ARG SYNAPSE_VERSION

RUN \
    python -m venv /synapse-venv && \
    /synapse-venv/bin/pip install "matrix-synapse[postgres]==${SYNAPSE_VERSION}"

RUN /synapse-venv/bin/pip install psycopg2 coincurve pycryptodome

# Temporary patch until raiden-network/raiden#4634 is resolved
RUN sed -i -E 's/^MAX_DISPLAYNAME_LEN = 100$/MAX_DISPLAYNAME_LEN = 200/' /synapse-venv/lib/python3.7/site-packages/synapse/handlers/profile.py

COPY eth_auth_provider.py /synapse-venv/lib/python3.7/site-packages/
COPY synapse-entrypoint.sh /bin/
COPY render_config_template.py /bin/

ENTRYPOINT ["/bin/synapse-entrypoint.sh"]

# HTTP
EXPOSE 8008
# HTTP metrics
EXPOSE 9101
# TCP replication
EXPOSE 9092
# HTTP replication
EXPOSE 9093

HEALTHCHECK \
    --timeout=5s \
    --start-period=60s \
    CMD curl -s --fail -o /dev/null http://localhost:8008/_matrix/client/versions || exit 1
