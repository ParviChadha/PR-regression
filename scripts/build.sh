#!/usr/bin/env bash
# Configure + build a target inside its container. Build dir lives in the named volume prh-<target>-build.
# Usage: scripts/build.sh <target> [--coverage]     (env: JOBS, default 6)
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"; shift || true
MODE=default; EXTRA=""
if [ "${1:-}" = "--coverage" ]; then MODE=coverage; EXTRA="$(cfg coverage_cmake_args)"; fi
JOBS="${JOBS:-6}"
START=$(date +%s)
run_in_container -- bash -ec "
  rsync -a --delete /src/ /build/src/   # writable copy: some tests write into their cwd; others git-clone the source dir (so .git is copied)
  cmake -S /build/src -B /build/$MODE -DCMAKE_EXPORT_COMPILE_COMMANDS=ON $(cfg cmake_args | tr '\n' ' ') $(echo $EXTRA | tr '\n' ' ')
  cmake --build /build/$MODE --parallel $JOBS
  ccache -s | head -12
"
echo "build[$MODE] wall time: $(( $(date +%s) - START ))s (jobs=$JOBS)"
