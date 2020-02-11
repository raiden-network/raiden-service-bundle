#!/usr/bin/env bash

if [[ ! -z ${CIRCLE_PR_NUMBER} ]]; then
  echo "Forked PR, skipping build since we can't upload to docker hub"
  circleci step halt
elif [[ ! -z ${CIRCLE_TAG} ]]; then
  export VERSION_TAG="${CIRCLE_TAG}"
elif [[ ! -z ${CIRCLE_PULL_REQUEST} ]]; then
  # Non-forked PR
  export VERSION_TAG="PR-${CIRCLE_PULL_REQUEST##*/}.${CIRCLE_WORKFLOW_ID:0:4}"
else
  export VERSION_TAG="nightly"
fi
echo "Version tag: ${VERSION_TAG}"
