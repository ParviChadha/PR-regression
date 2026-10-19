#!/usr/bin/env bash
# Check that clang-tidy/clangd can parse a header and a test source using the exported compile_commands.json.
# Usage: scripts/clangd_check.sh <target> <header-rel-to-repo> <test-source-rel-to-repo>
. "$(dirname "$0")/lib/common.sh"; use_target "${1:-}"
HDR="${2:?header}"; SRC="${3:?test source}"
run_in_container -- bash -c "
  ls -l /build/default/compile_commands.json
  echo '--- clang-tidy: test source'; clang-tidy -p /build/default --checks='-*,misc-definitions-in-headers' --header-filter='.*/include/nlohmann/.*' /build/src/$SRC 2>&1 | grep -v 'tweak: ExpandDeducedType\|Found definition heuristically' | tail -12
  echo '--- clang-tidy: header';      clang-tidy -p /build/default --checks='-*,misc-definitions-in-headers' --header-filter='.*/include/nlohmann/.*' /build/src/$HDR 2>&1 | grep -v 'tweak: ExpandDeducedType\|Found definition heuristically' | tail -12
  echo '--- clangd --check: test source'; clangd --compile-commands-dir=/build/default --check=/build/src/$SRC 2>&1 | grep -v 'tweak: ExpandDeducedType\|Found definition heuristically' | tail -12
  echo '--- clangd --check: header';      clangd --compile-commands-dir=/build/default --check=/build/src/$HDR 2>&1 | grep -v 'tweak: ExpandDeducedType\|Found definition heuristically' | tail -12"
