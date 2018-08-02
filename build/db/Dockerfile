FROM postgres:10
MAINTAINER Ulrich Petri <ulrich@brainbot.com>

RUN mkdir -p /docker-entrypoint-initdb.d
ADD db-init.sql /docker-entrypoint-initdb.d/
