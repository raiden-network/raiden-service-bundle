FROM postgres:10
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

RUN mkdir -p /docker-entrypoint-initdb.d
COPY db-init.sql /docker-entrypoint-initdb.d/
