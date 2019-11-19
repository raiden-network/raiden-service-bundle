# configure this in ./BUILD_VERSIONS
ARG POSTGRES_VERSION
FROM postgres:${POSTGRES_VERSION}
LABEL maintainer="Raiden Network Team <contact@raiden.network>"

RUN mkdir -p /docker-entrypoint-initdb.d
COPY db-init.sql /docker-entrypoint-initdb.d/
