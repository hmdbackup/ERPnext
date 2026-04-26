#!/bin/bash
# Build the HMD Agro production image from apps.json.
# Usage:
#   ./build-hmd.sh                       # tag=v15, uses cache
#   ./build-hmd.sh --no-cache            # tag=v15, fresh build (guaranteed clean)
#   ./build-hmd.sh v16                   # custom tag, uses cache
#   ./build-hmd.sh v16 --no-cache        # custom tag, fresh build
#
# Any docker-build flag passed (--no-cache, --pull, --progress=plain, etc.)
# is forwarded to `docker build`. Anything else is treated as the image tag.
set -e

TAG="v15"
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --*) EXTRA_ARGS+=("$arg") ;;
    *)   TAG="$arg" ;;
  esac
done

echo "Building hmd-agro-prod:${TAG}${EXTRA_ARGS:+ with ${EXTRA_ARGS[*]}}"

DOCKER_BUILDKIT=1 docker build "${EXTRA_ARGS[@]}" \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-15 \
  --secret id=apps_json,src=apps.json \
  --tag=hmd-agro-prod:${TAG} \
  --file=images/layered/Containerfile .
