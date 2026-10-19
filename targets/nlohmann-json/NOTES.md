# nlohmann/json — target notes

Pinned upstream: `0e95fe8200adbf0e033d0c0818eea473e1d4d346` (develop, 2026-10-17, `v3.11.3-763-g0e95fe820`).

## What upstream says (README, tests/CMakeLists.txt, cmake/*.cmake, .github/workflows/ubuntu.yml)
- Supported compilers: GCC 4.8–16.2, Clang 3.4–22.1, AppleClang, MSVC, etc. CI uses `gcc:latest`, `silkeh/clang:22`, CMake via `lukka/get-cmake`.
- Recommended test build (README "Execute unit tests"): `cmake .. -DJSON_BuildTests=On && cmake --build . && ctest --output-on-failure`.
  CI uses `-DJSON_CI=On` and custom targets (`ci_test_gcc`: Debug + Ninja + `JSON_BuildTests=ON` + max warnings). We use the README flow
  (Debug, Ninja), *without* `JSON_CI` (CI targets download CMake 3.5.0, run valgrind, 32-bit etc.; not needed for Stage 0).
- Tests: doctest, `tests/src/unit-*.cpp` (102 files). Each file is built once per C++ standard it mentions via `JSON_HAS_CPP_<n>`
  (standards list 11/14/17/20/23). On this commit that gives 131 executables: 104×cpp11, 4×cpp14, 13×cpp17, 10×cpp20, 0×cpp23.
  Plus `abi_*` compat builds and CMake integration tests (`cmake_import*`, `cmake_add_subdirectory`, `cmake_fetch_content*`,
  `cmake_target_include_directories`, `fmt_formatter`) = 153 ctest tests total.
- `JSON_FastTests=OFF` (default) runs executables with `--no-skip`, so the 7 `doctest::skip()` "roundtrip" test cases DO run.
  32-bit test (`JSON_32bitTest=AUTO`) is not built on aarch64 without multilib.
- `JSON_MultipleHeaders` defaults to ON: tests compile against split `include/` (see below), not `single_include/`.

## Network dependencies at test time (all vendored in the image)
1. **Test data**: `cmake/download_test_data.cmake` downloads `https://github.com/nlohmann/json_test_data` tag `v3.2.0` (ExternalProject, zip)
   at *ctest* time (`download_test_data` fixture). Upstream's own escape hatch: `-DJSON_TestDataDirectory=<dir>`.
   We fetch the tag tarball in the image build (sha256-verified, 134 MB) into `/opt/test_data`.
2. **fmt**: `tests/fmt_formatter/project/CMakeLists.txt` FetchContent-clones `https://github.com/fmtlib/fmt.git` tag `12.2.0` at ctest configure time.
   No upstream switch reaches that nested configure, so the image holds a mirror (`/opt/vendor/...`) and a *system* git config
   `url.file:///opt/vendor/....insteadOf=https://github.com/fmtlib/fmt.git`. Commit verified: `1be298e1bd68957e4cd352e1f676f00e07dcfb57`.
3. `JSON_TestSimdutf` (off) would fetch simdutf; not used.
4. `cmake_fetch_content*` / `fmt_formatter` `git clone` the *source dir itself* (`GIT_TAG HEAD`), so the writable source copy must include `.git`.

## Environment gotchas found
- Several tests write into their working directory (= `CMAKE_SOURCE_DIR`), e.g. `unit-class_parser.cpp` writes
  `unit-class_parser_diagnostic_positions.tmp`. With a read-only source mount this made
  `test-class_parser_diagnostic_positions_cpp11` fail (empty input). Fix is harness-side: scripts mount upstream read-only at `/src`
  and `rsync` it (with `.git`) to `/build/src` in the build volume; building and testing happen there. Upstream is never written.

## Include path for generated tests
Tests compile with `-I<build>/include -I<src>/include -isystem <src>/tests/thirdparty/doctest -DJSON_TEST_USING_MULTIPLE_HEADERS=1`
(`-std=gnu++11` for the cpp11 variants). To compile a generated test against a checkout's split headers: `g++ -std=c++17 -I<checkout>/include test.cpp`
(`#include <nlohmann/json.hpp>`). `single_include/` is only used by `JSON_MultipleHeaders=OFF` (not used here).
`<build>/include/test_data.hpp` (generated) defines `TEST_DATA_DIRECTORY`; only tests that read data need it.
