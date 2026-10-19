#!/usr/bin/env bash
# Build the shared base image (prh-base) and the target image (prh-<target>).
# Usage: scripts/image.sh <target>
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"
docker build --platform linux/arm64 -t prh-base -f "$ROOT/docker/Dockerfile" "$ROOT/docker"
docker build --platform linux/arm64 -t "$IMAGE" -f "$ROOT/targets/$T/Dockerfile" \
  --build-arg TEST_DATA_URL="$(cfg test_data_url)" \
  --build-arg TEST_DATA_SHA256="$(cfg test_data_sha256)" \
  --build-arg TEST_DATA_DIR="$(cfg test_data_dir)" \
  "$ROOT/targets/$T"
