#!/usr/bin/env bash
. .env

IMAGE=$(grep "raidennetwork/raiden-services:" docker-compose.yml|cut -d ':' -f2-|xargs)

CMD="python3 -m raiden_libs.service_registry register"

docker run --rm -it \
  -v ${DATA_DIR:-./data}/state:/state \
  -v ${DATA_DIR:-./data}/keystore:/keystore \
  -e SR_REGISTER_LOG_LEVEL=${LOG_LEVEL} \
  -e SR_REGISTER_KEYSTORE_FILE=/keystore/${KEYSTORE_FILE} \
  -e SR_REGISTER_PASSWORD=${PASSWORD} \
  -e SR_REGISTER_SERVICE_URL=pfs.${SERVER_NAME} \
  -e SR_REGISTER_ETH_RPC=${ETH_RPC} \
  --env-file .env \
  ${IMAGE} \
  ${CMD}
