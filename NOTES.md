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
