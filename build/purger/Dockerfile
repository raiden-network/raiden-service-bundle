ARG RAIDEN_VERSION
FROM raidennetwork/raiden:${RAIDEN_VERSION}
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

COPY requirements.txt /requirements.txt
RUN /opt/venv/bin/python3 -m pip install -r /requirements.txt

COPY purger.py /purger.py
COPY purger.sh /purger.sh

ENTRYPOINT ["/purger.sh"]
