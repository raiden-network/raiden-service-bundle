ARG RAIDEN_VERSION
FROM raidennetwork/raiden:${RAIDEN_VERSION}
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

COPY room_ensurer.py /room_ensurer.py

ENTRYPOINT ["/opt/venv/bin/python3", "/room_ensurer.py"]
