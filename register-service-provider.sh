#!/usr/bin/env bash
. .env

IMAGE=$(grep "raidennetwork/raiden-services:" docker-compose.yml|cut -d ':' -f2-|xargs)

CMD="python3 -m raiden_libs.register_service"

docker run --rm -it \
  -v ${DATA_DIR:-./data}/state:/state \
  -v ${DATA_DIR:-./data}/keystore:/keystore \
  -e RDN_REGISTRY_LOG_LEVEL=${LOG_LEVEL} \
  -e RDN_REGISTRY_KEYSTORE_FILE=/keystore/${KEYSTORE_FILE} \
  -e RDN_REGISTRY_PASSWORD=${PASSWORD} \
  -e RDN_REGISTRY_SERVICE_URL=${SERVER_NAME} \
  -e RDN_REGISTRY_ETH_RPC=${ETH_RPC} \
  --env-file .env \
  ${IMAGE} \
  ${CMD}
