ARG KNOWN_SERVERS_FILE_URL="https://github.com/raiden-network/raiden-service-bundle/blob/master/known_servers/known_servers-production-v3.0.0.json"

FROM python:3.9
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

RUN python -m venv /synapse-venv && /synapse-venv/bin/pip install -U wheel pip

ARG SYNAPSE_VERSION
ARG RAIDEN_SYNAPSE_MODULES

RUN /synapse-venv/bin/pip install \
  "matrix-synapse[postgres,redis]==${SYNAPSE_VERSION}" \
  "jinja2<3.1.0" \
  psycopg2 \
  coincurve \
  pycryptodome \
  "twisted>=20.3.0" \
  click==7.1.2 \
  docker-py \
  raiden-synapse-modules==${RAIDEN_SYNAPSE_MODULES}

ARG KNOWN_SERVERS_FILE_URL
RUN curl --output /known_servers.default.txt --location "${KNOWN_SERVERS_FILE_URL}"

COPY synapse-entrypoint.sh /bin/
COPY render_config_template.py /bin/

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
