# CLAUDE.md — conventions for PR-regression

Research harness: an LLM-based pipeline that detects behavioral regressions in
pull requests to C++ libraries. Stage 0 = prove we can build and test a target
(first: nlohmann/json) with coverage in a reproducible Linux container.
Do not start later stages (PR mining, test generation, LLM calls) without a go-ahead.

## Environment
- Host is macOS on Apple Silicon; containers are **native arm64 Linux**. No amd64 emulation.
- Use the Docker runtime already installed (Docker Desktop). Do not install runtimes or anything else on the host without asking.
- Keep ccache and build dirs in **named Docker volumes**, not bind mounts. Bind-mount only what must be shared with the host.
- Record CPUs/memory available to Docker. If a build runs out of memory or is very slow, stop and report; do not silently reconfigure Docker.

## Layout
- `CLAUDE.md` conventions; `NOTES.md` running log (commands, decisions, problems).
- `scripts/` small generic scripts taking a target name (build, test, coverage).
- `docker/` shared toolchain base image, only if it separates cleanly.
- `targets/<name>/` Dockerfile or target layer, one small config file, target notes. Committed.
- `pipeline/` generic pipeline code (empty for now). `data/`, `results/` committed, empty for now.
- `repos/` upstream clones and `cache/` API/LLM caches: **git-ignored**.

## Rules
- **Upstream is read-only.** Clone over HTTPS into `repos/<name>/` with full history (no shallow clone). Never modify upstream files; never fork or push upstream. Pass build options from outside the source tree. No git submodules.
- **Pinned commit.** Each target config records the tested upstream SHA; a script can fetch and check out exactly that SHA.
- **Target config.** One small human-readable config per target folder, read by the generic scripts. Only fields actually used; extend when a new target needs it.
- **Generic vs target-specific.** Nothing in `scripts/` or `pipeline/` hardcodes a target. Scripts take the target name as an argument. Do not over-engineer.
- **No credentials.** Never read, create, or store tokens, SSH keys, or secrets. If something seems to need one, stop and ask.
- **Docker hygiene.** Every image, container, volume is named `prh-<target>[-suffix]` (e.g. `prh-nlohmann-json-ccache`). Only delete resources with that prefix. No `docker system prune`. No `--privileged`. Never mount the host root or home directory.
- **Reproducibility.** Pin base image by digest (Ubuntu LTS arm64, e.g. 24.04). Record exact compiler/CMake/tool versions. Everything installable from the Dockerfile; nothing manual.
- **Notes.** Keep `NOTES.md` current: every command that mattered, each decision and why, each problem and its resolution.
- **Style.** A few small, clearly named scripts rather than long manual READMEs.
- **Commits.** Local commits in this repo at logical steps. Never commit `repos/`. Do not push unless asked.

## Stop and ask before
- Anything needing network at **runtime** that cannot be vendored into the image.
- Any failing test, or any workaround for one (e.g. disabling a test).
- Editing anything inside an upstream clone.
- Installing/changing anything on the host (including Docker settings/runtimes).
- Anything needing a credential, or deleting something outside this project.
- Spending more than ~20 minutes on one build step with no progress.
