FROM python:3.6

MAINTAINER Ulrich Petri <ulrich@brianbot.com>

RUN pip install click

ADD extract-certs.py /

ENTRYPOINT ["python3", "/extract-certs.py", "--status-file", "/status"]

HEALTHCHECK \
    --timeout=1s \
    --interval=30s \
    --start-period=120s \
    CMD bash -c '[[ -s /status ]] && cat /status || exit 1'
