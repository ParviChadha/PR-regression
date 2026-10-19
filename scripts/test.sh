#!/usr/bin/env bash
# Run ctest for a built target; full log kept in the build volume and summarized.
# Usage: scripts/test.sh <target> [--coverage] [--no-network]     (env: JOBS, default 6; TAG names the log)
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"; shift || true
MODE=default; NET=(); TAG="${TAG:-run}"
for a in "$@"; do case "$a" in --coverage) MODE=coverage;; --no-network) NET=(--no-network);; esac; done
JOBS="${JOBS:-6}"
START=$(date +%s)
set +e
run_in_container "${NET[@]}" -- bash -c "
  cd /build/$MODE && ctest -V --parallel $JOBS $(cfg ctest_args | tr '\n' ' ') > /build/$MODE/ctest-$TAG.log 2>&1
  rc=\$?; python3 /scripts/summarize.py /build/$MODE/ctest-$TAG.log; exit \$rc"
RC=$?
echo "test[$MODE/$TAG] exit=$RC wall time: $(( $(date +%s) - START ))s (jobs=$JOBS)"
exit $RC
