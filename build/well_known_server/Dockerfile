# configure this in ./BUILD_VERSIONS
ARG NGINX_VERSION
FROM nginx:${NGINX_VERSION}

LABEL maintainer="Raiden Network Team <contact@raiden.network>"

RUN apt update && \
    apt install -y curl && \
    rm -rf /var/lib/apt/lists/*

COPY well-known.conf /etc/nginx/conf.d/
RUN rm /etc/nginx/conf.d/default.conf

HEALTHCHECK \
    --timeout=5s \
    --start-period=10s \
    CMD curl -s --fail -o /dev/null http://localhost/.well-known/matrix/server || exit 1
