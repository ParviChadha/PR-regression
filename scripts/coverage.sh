#!/usr/bin/env bash
# Line coverage for coverage_scope, from the instrumented build (run build.sh/test.sh --coverage first).
# Writes reports into the build volume (/build/coverage/report) and into results/<target>/coverage/ on the host.
# Usage: scripts/coverage.sh <target>
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"
FILTERS=""; while read -r p; do FILTERS="$FILTERS --filter /build/src/$p/"; done < <(cfg coverage_scope)
OUT="$ROOT/results/$T/coverage"; mkdir -p "$OUT"
run_in_container -- bash -ec "
  mkdir -p /build/coverage/report && cd /build/coverage
  gcovr --root /build/src --object-directory /build/coverage $FILTERS --gcov-executable gcov -j 6 \
        --merge-mode-functions=separate \
        --txt /build/coverage/report/summary.txt --html-details /build/coverage/report/index.html --json-summary /build/coverage/report/summary.json \
        --txt-metric line >&2
  cat /build/coverage/report/summary.txt >&2
  tar -C /build/coverage/report -cf - ." | tar -C "$OUT" -xf -
