#!/usr/bin/env bash
set -eo pipefail

get_env_setting() {
    # Look for a variable named as given in `$1` and assign it to a shell variable of the same name.
    # Exit with error if the variable isn't found (unless `$2` is set in which case the target is
    # set to the empty string).
    # We do this instead of sourcing the file because docker(-compose) .env files have different
    # quoting rules than bash.
    # See: https://github.com/docker/compose/issues/3702

    local -n target="$1"  # -n makes `target` a nameref, requires bash >= 4.3
    local var=$1
    local optional=$2
    # shellcheck disable=SC2034
    target=$(grep -e "^${var}=" .env | sed -e "s/${var}=//") || {
      if [[ -z $optional ]]; then
        echo "Variable $var is missing in .env" >&2
        exit 1
      else
        target=""
      fi
    }
}

get_env_setting DATA_DIR optional
get_env_setting ETH_RPC
get_env_setting KEYSTORE_FILE
get_env_setting LOG_LEVEL
get_env_setting PASSWORD optional
get_env_setting SERVER_NAME


IMAGE=$(grep "raidennetwork/raiden-services:" docker-compose.yml|cut -d ':' -f2-|xargs)
CMD="python3 -m raiden_libs.service_registry"
SUBCMD="${@:---help}"

docker run --rm -it \
  -v "${DATA_DIR:-$(pwd)/data}"/state:/state \
  -v "${DATA_DIR:-$(pwd)/data}"/keystore:/keystore \
  -e SR_REGISTER_LOG_LEVEL="${LOG_LEVEL}" \
  -e SR_REGISTER_KEYSTORE_FILE=/keystore/"${KEYSTORE_FILE}" \
  -e SR_REGISTER_PASSWORD="${PASSWORD}" \
  -e SR_REGISTER_ETH_RPC="${ETH_RPC}" \
  -e SR_REGISTER_SERVICE_URL="https://pfs.${SERVER_NAME}" \
  -e SR_EXTEND_LOG_LEVEL="${LOG_LEVEL}" \
  -e SR_EXTEND_KEYSTORE_FILE=/keystore/"${KEYSTORE_FILE}" \
  -e SR_EXTEND_PASSWORD="${PASSWORD}" \
  -e SR_EXTEND_ETH_RPC="${ETH_RPC}" \
  -e SR_EXTEND_STATE_DB="/state/ms-state.db" \
  -e SR_INFO_LOG_LEVEL="${LOG_LEVEL}" \
  -e SR_INFO_KEYSTORE_FILE=/keystore/"${KEYSTORE_FILE}" \
  -e SR_INFO_PASSWORD="${PASSWORD}" \
  -e SR_INFO_ETH_RPC="${ETH_RPC}" \
  -e SR_INFO_STATE_DB="/state/ms-state.db" \
  -e SR_WITHDRAW_LOG_LEVEL="${LOG_LEVEL}" \
  -e SR_WITHDRAW_KEYSTORE_FILE=/keystore/"${KEYSTORE_FILE}" \
  -e SR_WITHDRAW_PASSWORD="${PASSWORD}" \
  -e SR_WITHDRAW_ETH_RPC="${ETH_RPC}" \
  -e SR_WITHDRAW_STATE_DB="/state/ms-state.db" \
  --env-file .env \
  "${IMAGE}" \
  ${CMD} ${SUBCMD}
