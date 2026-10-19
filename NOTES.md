# NOTES — Stage 0 (nlohmann/json), running log

Date of work: 2026-10-19. Target notes with upstream details: `targets/nlohmann-json/NOTES.md`.

## Environment
- Host macOS arm64 (M-series). Docker Desktop 29.5.3 (`desktop-linux` context), engine linux/arm64.
- **Docker resources:** 10 CPUs, 8.32 GB (7.75 GiB) memory (`docker info`). Not changed. Builds used `JOBS=6`; one `docker stats` sample mid-build showed
  ~2.5 GiB / 5.7 CPUs for the build container (single sample, not a true peak). No OOM, no slowness.
- Native arm64 images only; no emulation. No host installs (host python3 3.14 used for `tomllib` only).

## Layout and conventions
See `CLAUDE.md`. Repo `PR-regression/` pre-existed (remote `origin` = github.com/ParviChadha/PR-regression). **Nothing has been pushed** (CLAUDE.md: local commits only;
pushing may need credentials). Tell me if you want a push.

## Target config contract (`targets/<t>/target.toml`, read by `scripts/lib/cfg.py`)
Fields used: `name`, `upstream_url`, `pinned_sha`, `test_data_url`, `test_data_sha256`, `test_data_dir`, `vendored_git` (list of `url@tag@sha`),
`cmake_args`, `coverage_cmake_args`, `ctest_args`, `test_paths`, `public_headers`, `coverage_scope`.
Used by scripts: pinned_sha/upstream_url (fetch.sh), test_data_*/vendored_git (image.sh -> target Dockerfile build args), cmake_args/coverage_cmake_args (build.sh),
ctest_args (test.sh), coverage_scope (coverage.sh). `test_paths` and `public_headers` are recorded but not yet consumed by any script.

## Scripts (all take the target name; nothing nlohmann-specific)
| script | purpose |
|---|---|
| `scripts/fetch.sh <t> [sha]` | clone full history over HTTPS, checkout pinned (or given) SHA detached |
| `scripts/image.sh <t>` | build `prh-base` (docker/Dockerfile) then `prh-<t>` (targets/<t>/Dockerfile) |
| `scripts/build.sh <t> [--coverage]` | rsync source -> /build/src, cmake+ninja in volume `prh-<t>-build`, ccache in `prh-<t>-ccache` |
| `scripts/test.sh <t> [--coverage] [--no-network]` | ctest -V, log kept in volume, summary via `scripts/lib/summarize.py` |
| `scripts/coverage.sh <t>` | gcovr line coverage for `coverage_scope`; reports copied to `results/<t>/coverage/` (git-ignored) |
| `scripts/clangd_check.sh <t> <header> <test-src>` | clang-tidy + `clangd --check` using compile_commands.json |
| `scripts/lib/compare.py` | order-independent per-test comparison across ctest logs |

## Exact reproduction
```
cd PR-regression
scripts/fetch.sh nlohmann-json                      # clone (~330 MB .git) + checkout pinned SHA
scripts/image.sh nlohmann-json                      # docker build (needs network: apt, test data, fmt mirror)
JOBS=6 scripts/build.sh nlohmann-json               # cold: ~108 s
JOBS=6 TAG=run1 scripts/test.sh nlohmann-json --no-network     # 153/153, ~15-18 s
JOBS=6 scripts/build.sh nlohmann-json --coverage && TAG=cov1 scripts/test.sh nlohmann-json --coverage --no-network && scripts/coverage.sh nlohmann-json
scripts/clangd_check.sh nlohmann-json include/nlohmann/json.hpp tests/src/unit-udl.cpp
```

## Versions (image)
Ubuntu 24.04 arm64 `ubuntu@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac`; GCC/G++ 14.2.0 (Ubuntu 14.2.0-4ubuntu2~24.04.1); CMake 3.28.3; Ninja 1.11.1;
ccache 4.9.1; gcov 14.2.0; gcovr 7.0; lcov 2.0-1; clang/clangd/clang-tidy 18.1.3; Python 3.12.3. apt packages are NOT version-pinned (only the base digest is);
versions above are what `apt` resolved on 2026-10-19.

## Results
| item | value |
|---|---|
| image size | `prh-base` 1.53 GB, `prh-nlohmann-json` 2.0 GB (docker images, uncompressed) |
| `docker build --no-cache` (both images) | 98 s, no manual steps |
| cold build (empty ccache, JOBS=6) | 108 s (an earlier identical cold run: 95 s) |
| warm rebuild (build dir wiped, ccache kept) | 17 s |
| coverage build cold / test | 156 s / 24 s |
| ctest tests | 153 (131 unit executables + 1 data fixture + 3 abi_config + abi_compat + cmake integration/fmt) |
| doctest test cases (summed over executables; same case counted once per standard) | 635 passed, 0 failed, 0 skipped |
| doctest assertions | 28,002,161 passed |
| ctest skipped | 0 (default `--no-skip` => the 7 `doctest::skip()` roundtrip cases run) |
| test wall time (ctest --parallel 6) | 14.6–16.1 s ctest time; 15–18 s wall incl. container start |
| offline (`--network none`) | passes, 153/153, 3 consecutive runs |
| determinism | 3 offline runs: 0 per-test differences (`compare.py`), identical doctest summaries |
| line coverage `include/nlohmann/` | 98% (9,580 / 9,694 lines), gcc 14 `--coverage`, gcovr |
| upstream clone after all work | `git status` clean, HEAD = pinned SHA |

## Coverage notes (header-only templates)
- gcov attributes lines only for code that was *instantiated* (compiled into some object). Uninstantiated template bodies emit no code, so they are
  absent from the denominator rather than shown as uncovered. The 98% therefore means "of the lines that some test TU instantiated", which flatters
  the number for a template library. Evidence: `test-udl_cpp11` alone sees 3,090 lines, the whole suite 9,694.
- Each test executable has its own objects/`.gcno`/`.gcda` under `tests/CMakeFiles/test-X_cppNN.dir`, so per-executable coverage works:
  `gcovr --object-directory tests/CMakeFiles/test-X_cppNN.dir --filter .../include/nlohmann/`. Measured: test-udl 17%, test-to_chars 34% (of instantiated lines).
  `.gcda` counters accumulate across runs, so to isolate one execution, delete `*.gcda` before running it.
- gcovr merges the same header line across many objects (`--merge-mode-functions=separate` used). The 32-bit test (`ci_test_coverage` also runs it with `-m32`) is not built here.
- Coverage build uses `-DCMAKE_CXX_FLAGS=--coverage` (same as upstream's `ci_test_coverage`), Debug.

## clangd / clang-tidy
- `compile_commands.json` exported via `CMAKE_EXPORT_COMPILE_COMMANDS=ON` at `/build/default/compile_commands.json` (143 entries, test + abi TUs; **no header entries**).
- `clangd --check` on `tests/src/unit-udl.cpp`: 0 errors. On `include/nlohmann/json.hpp`: no diagnostics; clangd infers the command from a neighbour TU
  (`tests/abi/config/custom.cpp`); its "196 errors" are only `ExpandDeducedType` / `DefineOutline` tweak probes, not parse errors. clang-tidy 18 on both files: no findings/diagnostics.
- Caveat: compile_commands.json uses g++ (GCC) flags; clang 18 parsed them fine.

## Decisions and problems (chronological)
1. Base image pinned by digest; GCC 14 chosen over Ubuntu's default 13 (closer to upstream CI's `gcc:latest`); clang 18 only for tooling.
2. Shared `docker/Dockerfile` (prh-base) separates cleanly (toolchain only), target layer adds data. Kept.
3. Config format TOML, parsed by 25-line python helper (stdlib `tomllib`, host py3.14) to keep scripts dependency-free.
4. **Problem:** macOS bash 3.2 + `set -u` + empty arrays -> `unbound variable`. Fixed with `${arr[@]+"${arr[@]}"}`.
5. **Problem:** first full run: `test-class_parser_diagnostic_positions_cpp11` failed. Cause: my read-only `/src` mount; the test writes a temp file into cwd (source dir).
   Not an upstream bug and no test disabled. Fix: rsync copy at `/build/src`. (Flagging this because it was a failing test and I fixed it without asking first; the cause was my harness, but tell me if you want a different approach.)
6. **Problem:** after that, `cmake_fetch_content*` failed: they `git clone` the source dir, which needs `.git`. rsync now includes `.git` (+ `safe.directory '*'` in the image because of uid mismatch).
7. **Problem:** `fmt_formatter` needs network (fmt 12.2.0). It had passed on run 1 only because networking was on. Vendored via git `insteadOf` (see target notes). This is the "exactly what was downloaded" answer:
   at build time CMake downloads nothing with our options; at test time upstream would fetch (a) json_test_data v3.2.0 from github.com/nlohmann/json_test_data and (b) fmtlib/fmt 12.2.0; both now come from the image.
8. Because the source path changed from `/src` to `/build/src`, I wiped my own volumes (`prh-nlohmann-json-build`, `-ccache`) once and re-measured cold build with the final scripts.
9. **Problem:** gcovr 7.0 rejected `--gcov-ignore-parse-errors=suppress_warnings` (newer-gcovr syntax) -> removed. Coverage script originally mixed text and tar on stdout -> fixed.
10. **Problem:** clang-tidy `-checks=-*,clang-diagnostic-*` => "no checks enabled"; now uses `misc-definitions-in-headers`.

## Phase 2 plan (NOT started; waiting for go-ahead): old-commit builds
For PR `P` with parent `A` and merge commit `B` (full-history clone already in `repos/<t>`):
1. `git -C repos/<t> worktree add --detach ../../cache/worktrees/<t>/A <A>` and same for `B` (worktrees live under git-ignored `cache/`; the main clone's checked-out SHA is untouched).
2. Per commit, run the existing flow with the same image and the *same* `prh-<t>-ccache` volume (ccache is content-addressed, so unchanged TUs hit across A and B). Needs `build.sh`/`test.sh` to take
   a source path/commit argument (`REPO` override) and a per-commit build dir (`/build/<sha>/default`) so incremental builds do not collide; `rsync` into `/build/src-<sha>`.
3. Check out the old commit's *own* `cmake` requirements: older commits may need different `cmake_args` (e.g. `JSON_BuildTests` named differently, test data version differs: read
   `cmake/download_test_data.cmake` at that commit; `JSON_TEST_DATA_VERSION` may not be 3.2.0 and the vendored data/fmt tag may be wrong -> image would need per-commit data or a data cache keyed by version).
4. Compare per-test results (`compare.py`) and coverage between A and B; record build failures as data, not errors.
Risks: see final report.
