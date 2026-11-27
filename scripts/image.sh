#!/usr/bin/env bash
# Build the shared base image (prh-base) and the target image (prh-<target>).
# Usage: scripts/image.sh <target>
# Builds for this machine's architecture (arm64 on Apple Silicon, amd64 on x86 Windows/WSL or Linux); set
# PLATFORM=linux/arm64 (or linux/amd64) to force one.
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"
docker build ${PLATFORM:+--platform "$PLATFORM"} -t prh-base -f "$ROOT/docker/Dockerfile" "$ROOT/docker"
docker build ${PLATFORM:+--platform "$PLATFORM"} -t "$IMAGE" -f "$ROOT/targets/$T/Dockerfile" \
  --build-arg TEST_DATA_URL="$(cfg_opt test_data_url)" \
  --build-arg TEST_DATA_SHA256="$(cfg_opt test_data_sha256)" \
  --build-arg TEST_DATA_DIR="$(cfg_opt test_data_dir)" \
  --build-arg VENDORED_GIT="$(cfg_opt vendored_git | tr '\n' ' ')" \
  "$ROOT/targets/$T"
