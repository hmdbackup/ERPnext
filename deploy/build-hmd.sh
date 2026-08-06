#!/bin/bash
# Build the HMD Agro production image from apps.json.
#
# IMPORTANT: --no-cache is the DEFAULT. The git-clone steps for erpnext and
# hmd_agro live in cached Docker layers; a cached build can silently ship
# code that is weeks/months old even after a push to main. Only skip
# --no-cache for local experiments where staleness does not matter.
#
# Usage:
#   ./build-hmd.sh                       # tag=v15, fresh build (--no-cache, default)
#   ./build-hmd.sh v16                   # custom tag, fresh build
#   NO_CACHE=0 ./build-hmd.sh            # opt OUT of --no-cache (cached, fast, may be stale)
#
# Any docker-build flag passed (--pull, --progress=plain, etc.)
# is forwarded to `docker build`. Anything else is treated as the image tag.
set -e

TAG="v15"
NO_CACHE="${NO_CACHE:-1}"
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --no-cache) NO_CACHE=1 ;;          # kept for backward compat; already the default
    --*) EXTRA_ARGS+=("$arg") ;;
    *)   TAG="$arg" ;;
  esac
done

if [ "$NO_CACHE" != "0" ]; then
  EXTRA_ARGS+=("--no-cache")
else
  echo "WARNING: NO_CACHE=0 — building WITH the Docker layer cache. The image may contain STALE app code."
fi

echo "Building hmd-agro-prod:${TAG}${EXTRA_ARGS:+ with ${EXTRA_ARGS[*]}}"

DOCKER_BUILDKIT=1 docker build "${EXTRA_ARGS[@]}" \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-15 \
  --secret id=apps_json,src=apps.json \
  --tag=hmd-agro-prod:${TAG} \
  --file=images/layered/Containerfile .
