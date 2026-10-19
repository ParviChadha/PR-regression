# Sourced by scripts/*.sh. Provides: ROOT, T (target), names, cfg(), run_in_container().
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

use_target() {
  T="${1:?usage: $0 <target> ...}"
  [ -d "$ROOT/targets/$T" ] || { echo "unknown target: $T" >&2; exit 2; }
  IMAGE="prh-$T"
  CCACHE_VOL="prh-$T-ccache"
  BUILD_VOL="prh-$T-build"
  REPO="$ROOT/repos/$T"
}

cfg() { python3 -I "$ROOT/scripts/lib/cfg.py" "$T" "$1"; }          # one value / newline-separated list

# run_in_container [--no-network] -- cmd...   (source is mounted read-only; build + ccache in named volumes)
run_in_container() {
  local net=()
  if [ "${1:-}" = "--no-network" ]; then net=(--network none); shift; fi
  [ "${1:-}" = "--" ] && shift
  docker run --rm "${net[@]}" \
    -v "$REPO":/src:ro \
    -v "$BUILD_VOL":/build \
    -v "$CCACHE_VOL":/ccache \
    -v "$ROOT/scripts/lib":/scripts:ro \
    -e CCACHE_DIR=/ccache -e CCACHE_MAXSIZE=5G \
    -w /build "$IMAGE" "$@"
}
