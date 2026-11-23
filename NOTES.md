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
Added 2026-11-17 for `pipeline/env.py`: `build_mode` (only `header-only` implemented), `include_dirs`, `smoke_header`.

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

## pipeline/env.py (2026-11-17) — old/new environments, header-only targets
- `python3 pipeline/env.py <t> --pr N | --merge SHA [--parent SHA] [--check] [--docker] [--std c++17]` prints JSON (parent, merge, old_dir, new_dir, include_dirs);
  Python API `prepare()` / `compile_check()` for `run.py`. Needs `tomllib` (py>=3.11) or `tomli`.
- Decision: exports via `git archive` of `include_dirs` into `cache/worktrees/<t>/<sha>/` (about 1 MB each) instead of `git worktree add`, so the upstream clone is only read
  (`git worktree add` writes `repos/<t>/.git/worktrees`, which CLAUDE.md treats as editing upstream). Header-only means no build, no ccache; tests compile against `-I<export>/include`.
  Exports are atomic (temp dir then rename, `.prh-ok` marker) and reused. Library targets will need a second build mode (and `.git` if their build reads it); not written.
- Merge commit lookup for `--pr N`: `data/<t>/prs.jsonl` record as written by `pipeline/collect.py` (`pr`, `sha_new` = merge commit, `sha_old` = its parent), else a squash-merge subject ending `(#N)`.
  (2026-11-17: env.py first looked for `number`/`merge_sha`/`parent_sha`, a guess that never matched collect.py, so it silently used the fallback; fixed. Checked all records that exist in the local clone: sha_old/sha_new agree with git.)
  Records newer than the clone's HEAD (82 of 122 on 2026-11-17: collect used `abbc299`, the clone is at `0e95fe8`) need `git -C repos/nlohmann-json fetch origin develop` before env.py can export them.
  nlohmann/json squash-merges, so parent = the single parent; multi-parent merges need `--parent`.
- Verified with the VM's g++ 11.4 (NOT the pinned GCC 14): json #4958 and #5459 both resolve and smoke-compile at old and new; rerun is 0.07 s; upstream clone untouched (HEAD = pinned SHA, clean).
  On #4958: a type convertible to `std::string_view` used as `j[key]` compiles only on new (the PR's feature); `j.contains(key)` fails on both old and new (this is the regression #5689 later fixed).
  Still to do: run `--check --docker` on the Mac in `prh-nlohmann-json` (docker path untested).

## pipeline/run.py (2026-11-17) — compile, run, compare
- `python3 pipeline/run.py <t> --pr N | --merge SHA [--parent SHA] [--docker] [--std c++17] [--runs 3] [--timeout 10] [--compile-timeout 180] [--jobs 4] [--tests-dir DIR]`.
  Reads `data/<t>/tests/<key>/*.cpp` (key = PR number, or merge SHA[:12]), writes `results.json` beside them. Uses `env.prepare()` for the old/new exports.
- One batch per version (old and new in parallel). `--docker`: one `docker run` per version (`prh-<t>-run-<old|new>-<pid>`, `--network none`, `--memory 3g`, `--pids-limit 1024`, exports,
  tests and `pipeline/` mounted read-only); otherwise on the host. The same file is the worker in both modes (`--worker`, internal). Compile `g++ -std=<std> -O0 -I<export>/include`;
  run each binary N times in a temp cwd with a file-size ulimit and a process-group kill on timeout.
- Statuses: `same`, `output_diff`, `compile_diff` (compiles on one side only; `compile_failed_on` says which; fix.py must not repair it), `flaky` (reruns on the same version
  disagree; dropped), `invalid` (compile fails on both, or times out on both; dropped, fix.py may repair compile errors). Compared: (timeout, exit code, sha256 of full stdout); stderr kept
  for the first run only, not compared. Kept per test: first-run stdout up to 20 KB, compile stderr tail (4 KB) on failure.
- Decision: compile failures are data, not errors (your call on 2026-11-17): a test that breaks on only one side is a candidate API change.
- Verified on the host VM (g++ 11.4, not GCC 14) with hand-written probes in `data/nlohmann-json/tests/{4958,5459}/`: all five statuses occur as expected.
  #4958: `j[Key{}]` -> compile_diff (fails on old); `j.contains(Key{})` -> invalid (fails on both); #5459: `int 2^53+1 == double 2^53` prints `1 0 0` old vs `0 0 1` new -> output_diff.
  6.5 s for 5 tests, 0.7 s for 2. Docker path not yet run.

## pipeline/coverage_loop.py (2026-11-17) — changed-line coverage + refine loop
- `python3 pipeline/coverage_loop.py <t> --pr N | --merge SHA [--parent SHA] [--docker] [--std c++17] [--timeout 10] [--jobs 4] [--tests-dir DIR] [--context]`; reads the same
  `data/<t>/tests/<key>/*.cpp` as run.py, writes `coverage.json` beside them. `--docker` uses the same `launch_worker` as run.py (factored out of `run_batch`; behavior unchanged).
- Changed lines = lines added/modified in the NEW version under `include_dirs` (`git diff -U0 -w --ignore-blank-lines parent merge`). Only the new version is measured, so a deletion-only PR
  has no changed lines (n/a). Tests compile with `-O0 --coverage` against the new export, run once, `gcov --json-format --stdout` on the .gcda, keep changed lines only.
  Killed (timeout) or aborted runs write no .gcda, so they contribute no coverage.
- Union over tests; each changed line ends up in exactly one bucket: `covered`, `uncovered` (executable, never ran), `macro` (body of a #define: gcov credits the expansion site, so not
  measurable), `no_code` (code-like, no gcov data: uninstantiated template/declaration), `trivial` (blank, comment, brace, `template<...>`, preprocessor). Headline number
  `exec_coverage = covered / (covered + uncovered)`; n/a when there are no executable changed lines. Counts for all buckets are in `summary`.
- `loop(env, tests_dir, args, refine=fn, rounds=1)`: measure everything, then up to `rounds` rounds of `fn(context, remaining, tests_dir) -> [new test file names]`, re-measure only the new
  tests, stop when the union covered count does not grow. No LLM calls in this file; generate.py supplies `fn`. `uncovered_context()` builds the prompt text (`>>` marks target lines,
  with 3 lines of context). Refine triggers when any of uncovered/macro/no_code remains.
- Verified (host VM, g++/gcov 11.4 not GCC 14): #5459 probes cover 15 of 20 executable changed lines (exec_coverage 0.75; 4 macro lines, 45 trivial); union checked line-by-line against
  plain-text gcov (identical). Loop test with a stand-in refine: round 1 grew 15 -> 19 covered, round 2 did not grow and the loop stopped. NOT RUN lines matched what the probes actually pass in.
- Finding: #4958 changes only a type-trait alias, which has no executable lines (4 no_code, 2 trivial), so changed-line coverage is n/a for it. The report should count only PRs with executable
  changed lines when it quotes the coverage-loop numbers.
- Limits: the changed-lines list goes to the worker as one argv string (fine for these PRs; very large diffs may need a file). Not yet run with `--docker`.

## duckdb target + env.py "cmake" build mode (2026-11-17)
- `targets/duckdb/{target.toml,Dockerfile}`; pinned upstream main HEAD `4c0adf6440aa4aa6cac81bfedae264cfe5324863` (#28938). Dockerfile is just `FROM prh-base` (nothing extra needed, no test data).
  **repos/duckdb is NOT cloned yet**: the sandbox's network was too slow and its shell kills background jobs mid-clone. Run `scripts/fetch.sh duckdb` on the Mac. A partial clone I left is parked in
  `repos/_to_delete/duckdb-partial-clone` (git-ignored; delete it, I cannot).
- New target.toml fields (used by env.py): `build_mode = "cmake"`, `build_target`, `library`, `export_paths`, `smoke_source`; `cmake_args` and `include_dirs` as before.
- Library build (read from the pinned CMakeLists, configure verified with GCC 13/CMake 3.28 in a throwaway tree): `-DCMAKE_BUILD_TYPE=Release -DBUILD_UNITTESTS=OFF -DBUILD_SHELL=OFF
  -DENABLE_SANITIZER=OFF -DENABLE_UBSAN=OFF -DFORCE_ASSERT=ON -DSKIP_EXTENSIONS=icu;json;parquet -DSTATICALLY_LINK_EXTENSIONS=core_functions -DDUCKDB_CAPABILITIES=none`, target `duckdb`
  -> `src/libduckdb.so` (SONAME plain `libduckdb.so`, so copying that one file is enough). Configure shows 353 build steps (unity build). Why: defaults link icu/json/parquet (long compiles) and ASan/UBSan
  apply to Debug; FORCE_ASSERT keeps `D_ASSERT` live in Release so internal assertion failures show up as crashes. Consequence: tests needing icu (time zones), json or parquet cannot run;
  PRs touching only those extensions should be filtered out. Version/commit hash is the constant `0123456789` for every build (no .git in the export), so `pragma_version()` is not a false difference.
- Generated tests compile with `-I<export>/src/include` (duckdb.hpp compiles with only that; checked with GCC 13) and link `-L<export>/lib -lduckdb -Wl,-rpath,<export>/lib` AFTER the source.
- Mechanics (env.py `build_libraries`): `git archive` of `export_paths` per commit (~103 MB each instead of ~440 MB) -> in ONE `docker run` on `prh-duckdb`, under `flock` on the build volume, for parent then merge:
  `rsync -rlpgoD --checksum --delete` the export into `/build/src` (no `-t`: archive mtimes are commit dates, older than our objects, and ninja would think everything is up to date), re-run cmake configure
  (picks up added/removed files), `cmake --build /build/obj --target duckdb --parallel ${JOBS:-4}`, copy the .so to `<export>/lib/`, touch `.prh-built`. ccache volume `prh-duckdb-ccache`.
  JOBS defaults to 4 (unity TUs are memory-hungry; Docker has 8 GB). Disk: roughly one .so per commit under cache/ (git-ignored); delete old ones if space gets tight.
- Verified (cloud sandbox, GCC 13, NOT the Mac container): the generated script run against a two-commit stand-in repo and the small target `duckdb_re2`: commit 1 built 24/24 steps; commit 2 (one file changed)
  rebuilt 2/2 steps (that file + link) -> incremental logic works; markers and lib copy work. NOT yet run: the real duckdb build, `docker run` itself, `--check` linking/running the smoke program.
- Other changes: `Env` gained `old_lib/new_lib/lib_name` + `link_flags()`; `prepare(..., docker=)`; `compile_check(..., run=True)` links and runs; run.py passes `--link-flag` and puts it after the source;
  coverage_loop.py refuses cmake targets (needs a `--coverage` library build and per-test gcda handling: not written). `scripts/lib/cfg.py --optional` / `cfg_opt` and `scripts/image.sh` make the json-only
  build args optional; `scripts/build.sh` now shell-quotes cmake args so `;` survives (checked offline: json args unchanged). json flow re-run after these edits: env --check, run.py (4958, 5459), coverage_loop (5459) all give the same results as before.
- To do on the Mac, in order: `scripts/fetch.sh duckdb`; `scripts/image.sh duckdb`;
  `JOBS=4 python3 pipeline/env.py duckdb --merge 4c0adf6440aa4aa6cac81bfedae264cfe5324863 --docker --check` (cold build of the parent, then incremental merge build; record both times here).

---

# Stage 1a — PR collection (`pipeline/collect.py`, `pipeline/github.py`)

Date: 2026-11-17. Runs on the host (plain Python 3.11+, stdlib only); no container needed.

## Commands
```
scripts/fetch.sh nlohmann-json                             # full-history clone in repos/ (once)
git -C repos/nlohmann-json fetch origin develop            # if collect_head is newer than the clone
python3 -m pipeline.collect nlohmann-json                  # git-only: filters + data/nlohmann-json/prs*.jsonl (~3 s)
python3 -m pipeline.collect nlohmann-json --github         # + PR title/body/comments/linked issues
python3 -m unittest pipeline.test_collect pipeline.test_github
```

## How a PR is found
Every first-parent commit on `collect_head`'s history whose subject ends in `(#N)` (squash merge) or starts with
`Merge pull request #N` is PR N; old = first parent, new = that commit. nlohmann/json squash-merges everything
(288/288 in the sample). `--github` checks GitHub's `merge_commit_sha` against `new` and lists mismatches in
`collect_summary.json`.

## Filters (first failing one is the verdict)
bot (dependabot, pre-commit, `chore(deps` ...) -> DOC title (Testora; also catches `docs:`) -> no main source ->
more than 3 main source files (Testora) -> comment/blank-only change. Main source = C++ file under `main_source`,
not under `generated_paths`, no path part containing "test" (Testora's rule). `single_include/` is generated by
every PR, so it never counts.

## Result (collect_head abbc299, 2026-11-15)
Walked the newest 288 PRs (#4555-#6128, 2026-10-07 to 2026-11-15) until 120 passed:
bot 32, doc_title 29, no_main_source 69, too_many_main_files 35, comment_only 3, **checked 120**.
Seeds #4958 and #5459 are older than the window; both pass the filters and are added (122 rows in prs.jsonl).
Spot checks: #6100 ("Fix develop CI") is correctly comment_only (only NOLINT/comment lines in include/).

## Decisions
- `collect_head` pins the sampled history, so the sample does not drift when the clone is fetched.
- Hunk contexts use git's built-in `diff=cpp` rules via a git-ignored attributes file (cache/gitattributes-cpp);
  upstream is untouched. Improved the context of 33/122 PRs (e.g. a goto label -> the enclosing class). These are
  hints only; Clang-based change analysis (`changes.py`) replaces them.
- GitHub transport: `gh api` if gh is logged in (gh owns the credential, the code never sees a token), else
  unauthenticated HTTPS at 60 requests/hour. ~3 requests per PR + 1 per linked issue, so 122 PRs need roughly
  370-400 requests: about 6-7 hours unauthenticated, a few minutes with gh. Output is cached per PR in
  `data/<target>/github/<pr>.json`; a rate limit stops the run cleanly and a rerun continues.
- Linked issues = GitHub closing keywords in the PR body (fixes/closes/resolves #N, same-repo qualified refs and
  issue URLs). GitHub's own linked-issue sidebar needs the GraphQL API with auth; not used.

## Open
- `--github` not yet run: this cloud workspace cannot reach api.github.com. Run it on a Mac (with `gh auth login`
  for speed) and commit `data/nlohmann-json/github/`.
- QuantLib and duckdb need their own target.toml collection fields (`main_source` = `ql` / `src`+`extension`?).

## pipeline/llm.py + generate.py (LLM test generation)
- Model decision: Gemini free tier. Default `gemini-3.5-flash-lite` (reported 15 RPM / 500 RPD) for the scale run;
  `gemini-3.8-flash` (reported 5 RPM / 20 RPD) only for seed PRs #4958 and #5459 to compare quality. Model is one
  value: `--model` or env `PRH_LLM_MODEL`. The limits are third-party-reported, **verify at
  https://aistudio.google.com/rate-limit** and override with `PRH_LLM_RPM` / `PRH_LLM_RPD` if different. Paid 3.8 Flash
  would be roughly $40 for ~1,000 calls over 240 PRs (est.).
- Key: `GEMINI_API_KEY` from the environment, else from the git-ignored `.env` at the repo root (`GEMINI_API_KEY=...`;
  only that name is read, nothing else is loaded). Sent in header `x-goog-api-key`; never logged or cached (tested).
- `llm.call` caches by request hash in `cache/llm/responses/` (git-ignored), so reruns cost nothing and work without a
  key. Daily use is counted per Pacific day in `cache/llm/usage.json`; the client stops before the daily budget
  (`QuotaExhausted`, generate.py exits 3), spaces requests for RPM, retries 429/500/503 using `retryDelay`.
- generate.py: one request returns N (default 20) standalone C++17 programs as structured JSON, written to
  `data/<t>/tests/<pr>/gen_NN.cpp` plus `generated.json` (name, intent, round) and `generate.prompt.txt` for audit.
  Programs without `main` or duplicates are dropped; stale gen files are removed on regeneration.
- Leak filter: prompt uses only merge-time information (comments with created_at <= merged_at; later discussion is
  dropped), so later regressions are not handed to the model. Checked: #4958 prompt has no mention of #5689.
- Hooks for Person A: `data/<t>/changes/<pr>.json` ({"functions":[{"name","access"}]}) replaces the interim git
  hunk-header hint; `data/<t>/context/<pr>.txt` is appended as extra context.
- `--refine` feeds uncovered changed lines from coverage_loop back to the model (`--refine-n` programs per round).
- Tests: `python3 -m unittest pipeline.test_generate` (13 tests, fake transport, no network/key/quota).
- **Untested against the live API**: request shape (camelCase generationConfig, `responseSchema` with uppercase types).
  First real call must be run on the Mac; if Gemini rejects the schema, fix in llm.py.

## pipeline/fix.py (repair pass)
- Reads `results.json` + `generated.json` of a PR and repairs two kinds of program with ONE request per round
  (default 2 rounds): `compile` (invalid because it fails to compile identically on both versions: bad header, typo)
  and `detect` (compile_diff that fails on OLD only: rewrite with the detection idiom + `if constexpr` so it compiles on
  both and the new behavior is observed). Never touches the findings: fails-on-new, both-with-different-errors,
  output_diff, flaky, runtime timeouts.
- Repairs are new files (`gen_NN.cpp`); the manifest gets `fixes`/`kind` on them and `superseded_by` on the original.
  Originals stay (evidence, coherent results.json); later stages skip superseded entries. Repairs run on both versions
  immediately and are merged into results.json. Re-running generate.py discards repairs.
- `--per-signature 4`: at most 4 detect repairs per kind of old-side error (14 programs failed the same way on #4958;
  repairing all would only add near-duplicates). `--max-per-round 15`.
- Prompt: merge-time PR section + each program with its compiler errors. Directories are stripped from errors so no host
  paths go to the API (tested).
- run.py classifier now also reports `compile_diff [both]` when both versions fail with a different first error
  (`error_signature`), which exposed the #4958 const-lookup regression that used to be filed as invalid.
- coverage_loop.py now fails loudly when programs run but gcov yields nothing (Apple clang on the Mac host): use `--docker`.
- Tests: `python3 -m unittest pipeline.test_fix pipeline.test_generate`.

## pipeline/classify.py (intended vs unintended)
- Input: live programs (generated.json entries not superseded) whose result is output_diff or compile_diff. same/invalid/flaky are only counted.
- Clusters by status + first differing output line pair (or exit-code change), or by the first compiler-error kind
  (`run.error_signature`) per failing side. #4958: 18 differing programs -> 7 clusters; #5459: 2 programs -> 2 clusters.
- ONE request per PR (temperature 0): merge-time PR section (same leak filter as generate.py) + each cluster with up to 2
  representative sources and old/new outputs or compiler errors (host paths stripped, header comments stripped).
  Model returns intended | unintended | unclear + confidence + reason per cluster; a missing/odd verdict becomes `unclear`.
- Output `classification.json` (`pr_verdict.regression_candidate` = any cluster unintended) and `classify.prompt.txt`.
- Model: `--model` (default Flash-Lite). Classification is a judgment call; 3.8 Flash's free 20/day covers the seed PRs
  but not 240 PRs, so decide after seeing Flash-Lite's verdicts on #4958/#5459.
- Tests: `python3 -m unittest pipeline.test_classify pipeline.test_fix pipeline.test_generate` (42, fake model).

## pipeline/report.py (tables for the talk and final report)
- `python3 pipeline/report.py <target> [--prs ...]` -> `results/<t>/report.md` + `report.json`. No LLM calls; reads
  generated.json, results.json, classification.json, coverage.json per PR. Definitions are in the module docstring
  (compile success as generated vs after fix.py, both "new" and "both versions"; deterministic; behavioral difference;
  LLM calls are estimated from the files; wall time is run.py's last run only).
- `data/<t>/seeded.json` lists PRs with a known answer (from the plan: #4958 unintended, later #5689; #5459 intended).
  Used only by the report, never by a prompt. Recall on that set is tiny by construction (n=1) and is labeled as such.
- Result on json so far (2 PRs): #4958 flagged as regression candidate (const lookup + ordered_json clusters), #5459
  clean; compile success as generated 95% new / 60% both, after fix.py 95% / 80%; 6 LLM calls total (3 per PR).
  Cross-checked by recounting results.json by hand.
- Not yet measured: classifier precision against hand labels and inter-labeler agreement (needs labels from both of us),
  recall beyond the seeded set, QuantLib/duckdb.
- Tests: `python3 -m unittest pipeline.test_report pipeline.test_classify pipeline.test_fix pipeline.test_generate` (48).
- Unexplained leftover: data/nlohmann-json/tests/4958/classification.prompt.txt (18:40, different prompt text, no code in
  the repo writes that name; classify.py writes classify.prompt.txt). Not committed.

## pipeline/batch.py (scale driver)
- `python3 pipeline/batch.py <target> (--all | --prs N ...) [--limit K] [--docker] [--dry-run] [--model M] [--classify-model M]
  [--redo generate,run,fix,classify] [--max-failures 5]`: generate -> run -> fix -> classify per PR, then report.
- Resumable: a stage is skipped when its output is current (generate: generated.json; run: results.json covers every
  .cpp; fix: manifest "fix" marker, repairs present, or nothing repairable; classify: classification.json carries the
  sha256 of the results.json it judged). Any stage that runs makes the later ones run. `--redo generate` cascades.
- Each stage is its own process (isolation); output in cache/logs/<target>/<pr>.log. Stage exit 3 = daily LLM quota spent
  -> stop (resets midnight Pacific), still write the report. Other failures: recorded, PR skipped, retried next run;
  `--max-failures` halts a systematically failing run before it burns the day's requests.
- Order: seeded PRs first, then prs.jsonl order. Worst case 4 requests per PR (1 generate + 2 fix + 1 classify); the
  header line prints the worst case and what is left of today's quota for the model.
- json: 120 PRs need work (the 2 seeds are done): at most 480 requests vs ~488 left on a fresh day for Flash-Lite.
- fix.py now writes `manifest["fix"]`; classify.py writes `results_sha256` (older classification files fall back to mtime).
- Tests: `python3 -m unittest pipeline.test_batch pipeline.test_report pipeline.test_classify pipeline.test_fix pipeline.test_generate` (62).

## Double-check of the first batch (#6076, #6078, #6121) and the refine stage
- Verified: report numbers recounted from results.json (95/81% as generated, 97/91% after fix.py, 91 of 91 deterministic);
  logs clean (one retried 503, request counts consistent); #6076 verdicts correct (its PR text includes the #6105
  overlapping-keys fix, which is exactly what the 5 clusters show); #6121 plausible (token truncation is the PR title).
- PROBLEM FOUND: #6078 (UBJSON valueless-array limit) had 20 programs and zero differences, which is a false negative.
  11 of 20 were rejected identically by both versions at byte 1 (the model's UBJSON bytes lacked the opening '['), most
  others failed a few bytes later, and `to_ubjson(j)` was called without the optimized flags. Coverage of the changed lines
  on 10 of the programs: 54.5%; the core new check ("excessive number of elements without payload") and the writer's
  valueless-array accounting were never executed. Identical errors on both sides hide this, so "same" does not mean
  "tested". The batch had no coverage step, so nothing flagged it.
- Fix: batch.py has a `refine` stage after generate (default on, `--no-refine` to skip): `generate.py --refine-only`
  runs coverage_loop and ONE refine request aimed at the uncovered lines; the refine prompt now warns about malformed
  inputs. Demonstrated on a scratch copy: one well-formed program (two valueless arrays of 600000 elements) moves
  coverage 54.5% -> 93.3%, reaches the new check, and differs old/new (parsed vs out_of_range.408).
- report.py: a clean result is now labeled INCONCLUSIVE when coverage is missing or below 80% (it said "no regression
  flagged" before). Summary shows how many PRs had coverage measured.
- Known limits, not fixed: (1) clustering splits one behavior into several clusters when the output text differs (#6076:
  5 clusters, one behavior); (2) output comparison cannot see performance fixes (#6076's main change is linear-time
  unflatten); (3) data/nlohmann-json/tests/4958/coverage.json predates the batch (hand-written probes, trait-only change,
  so n/a) and counts as "measured"; (4) refine uses 1 round; a PR whose coverage stays low stays INCONCLUSIVE.
- Worst case is now 5 requests per PR (generate, refine, up to 2 fix, classify): 120 json PRs = up to 600 requests, so
  expect two days on Flash-Lite's 500/day.
- Tests: 68 (`python3 -m unittest pipeline.test_batch pipeline.test_report pipeline.test_classify pipeline.test_fix pipeline.test_generate`).

## Hand labels (pipeline/labels.py)
Purpose: measure classifier precision/recall and inter-labeler agreement (Testora-style metrics).
- Unit = cluster (what classify.py judges). Items keyed `<pr>-<cluster id>` with a fingerprint of the cluster's programs; eval skips labels whose fingerprint no longer matches (pipeline reruns change clusters), and reports how many it skipped.
- Sampling: every cluster the classifier called unintended/unclear, plus a seeded random sample of intended (`--intended-sample`, default 20). eval reports raw and weighted precision/recall (weight = available/exported per classifier verdict) because the intended stratum is subsampled.
- Blind: items.md shows PR link, changed files, old/new behavior and one representative program, in shuffled order, with no classifier verdict or reason. Labelers use merge-time information only.
- Commands: `labels.py export|check|reconcile|eval <target>`. Outputs in data/<t>/labels/ (items.json, items.md, labels_<name>.csv, reconciled.csv, eval.json).
- Decision: export only after the full batch (with refine) has finished, since reruns change clusters.
- Problem: first version had a nested-quote f-string (invalid before Python 3.12); fixed by precomputing the string.

## duckdb Stage 0 check on the Mac (2026-11-23)
- Pinned SHA 4c0adf644 is a true merge commit (DuckDB does not squash), so env.py needs `--parent`; used the first parent cb8605254dc64f158eb1d9816be1ebbfba5212d9 (`git -C repos/duckdb rev-parse <sha>^1`).
- Command (zsh: `time` must come first): `time JOBS=4 python3 pipeline/env.py duckdb --merge 4c0adf6440aa4aa6cac81bfedae264cfe5324863 --parent $P --docker --check`
- Result: parent built from 353 steps, then incremental merge build of 5 steps; `check old: ok`, `check new: ok`, exit 0. Wall time 4:56 total (ccache state unknown, so not a guaranteed cold figure). Docker CPUs/memory: TODO record from Docker Desktop.
- Expected noise, not errors: "fatal: not a git repository" and the CMake warning about `git log` (the build tree is a git-archive export without .git); the build then uses placeholder hash 0123456789 for both old and new, so it cannot cause differences between versions.
- Decision: do not pass DUCKDB_COMMIT; the identical placeholder is harmless and generated tests must not print the version/commit (prompt_notes says so).
- Still to do for duckdb: collection fields in target.toml (`main_source`), first-parent handling for merge-commit PRs in collection, then generate/run on a PR.
