FROM python:2.7
MAINTAINER Ulrich Petri <ulrich@brainbot.com>

ARG SYNAPSE_VERSION

RUN \
    virtualenv /synapse-venv && \
    /synapse-venv/bin/pip install https://github.com/matrix-org/synapse/tarball/${SYNAPSE_VERSION}

RUN /synapse-venv/bin/pip install --no-binary psycopg2 coincurve pycryptodome

ADD eth_auth_provider.py /synapse-venv/lib/python2.7/site-packages/eth_auth_provider.py
ADD synapse-entrypoint.sh /bin/
ADD render_config_template.py /bin/

ENTRYPOINT ["/bin/synapse-entrypoint.sh"]

EXPOSE 8008
EXPOSE 8448
EXPOSE 9101
EXPOSE 9092
EXPOSE 9093

HEALTHCHECK \
    --timeout=5s \
    --start-period=60s \
    CMD curl -s --fail -o /dev/null http://localhost:8008/_matrix/client/versions || exit 1
