ARG RAIDEN_VERSION
FROM raidennetwork/raiden:${RAIDEN_VERSION} AS RAIDEN

RUN /opt/venv/bin/python -c \
    'from raiden.settings import DEFAULT_MATRIX_KNOWN_SERVERS; \
    from raiden.constants import Environment; \
    print(DEFAULT_MATRIX_KNOWN_SERVERS[Environment.PRODUCTION])' > /known_servers.default.txt

FROM python:3.7
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

ARG SYNAPSE_VERSION

RUN \
    python -m venv /synapse-venv && \
    /synapse-venv/bin/pip install "matrix-synapse[postgres,redis]==${SYNAPSE_VERSION}"

RUN /synapse-venv/bin/pip install psycopg2 coincurve pycryptodome twisted>=20.3.0 click==7.1.2 docker-py

COPY eth_auth_provider.py /synapse-venv/lib/python3.7/site-packages/
COPY admin_user_auth_provider.py /synapse-venv/lib/python3.7/site-packages/
COPY synapse-entrypoint.sh /bin/
COPY render_config_template.py /bin/
COPY --from=RAIDEN /known_servers.default.txt /

ENTRYPOINT ["/bin/synapse-entrypoint.sh"]
CMD ["synapse"]

# HTTP
EXPOSE 8008
# HTTP metrics
EXPOSE 9101
# HTTP replication
EXPOSE 9093

HEALTHCHECK \
    --timeout=5s \
    --start-period=60s \
    CMD curl -s --fail -o /dev/null http://localhost:8008/health || exit 1
