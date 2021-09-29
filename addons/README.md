# Addons

This directory contains optional addons.

## Jaeger tracing

Currently only the `PFS` supports jaeger tracing.
To enable:
- Symlink the `docker-compose.override.tracing.yaml` file to the base directory as 
`docker-compose.override.yaml`
- Add `JAEGER_COLLECTOR` pointing to the Jeagertracing collector `host:port` to `.env`
- Run `docker-compose up -d pfs jaeger_agent`
