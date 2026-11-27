"""Shared helpers for pipeline/*: target config, paths, git."""
import json
import pathlib
import subprocess
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Target:
    """A target's config (targets/<name>/target.toml) plus the paths the pipeline uses for it."""

    def __init__(self, name):
        path = ROOT / "targets" / name / "target.toml"
        if not path.is_file():
            raise SystemExit(f"unknown target '{name}': {path} not found")
        self.name = name
        self.cfg = tomllib.loads(path.read_text(encoding="utf-8"))
        self.dir = path.parent
        self.repo = ROOT / "repos" / name                 # full-history upstream clone (git-ignored)
        self.data = ROOT / "data" / name                  # committed outputs
        self.cache = ROOT / "cache"                       # git-ignored caches and worktrees

    def __getitem__(self, key):
        if key not in self.cfg:
            raise SystemExit(f"targets/{self.name}/target.toml: missing key '{key}'")
        return self.cfg[key]

    def get(self, key, default=None):
        return self.cfg.get(key, default)


# Pipeline variants, each with its own folder under data/<t>/ (the proposal's comparison of a basic pipeline with the
# improved one, section D.c):
#   main      the full pipeline: prompts name the changed functions (changes.py) and show upstream tests that use
#             them (context.py), and the coverage loop adds programs aimed at changed lines nobody reached.
#   baseline  the basic pipeline: the same prompts without those two sections and without the refine round (coverage
#             is still measured, so both variants report it). Fixing and classification are the same in both.
VARIANTS = {"main": "tests", "baseline": "baseline"}


def tests_dir(t, pr, variant="main"):
    """data/<t>/tests/<pr> (main) or data/<t>/baseline/<pr>."""
    return t.data / VARIANTS[variant] / str(pr)


def pr_std(t, pr):
    """The C++ standard to compile PR `pr`'s generated programs with (e.g. "c++17", "c++20").

    changes.py marks changed entities that exist only under an `analysis_variants` flag set containing -std=...
    ("requires_flags", e.g. code inside `#if JSON_HAS_CPP_20`). When EVERY changed entity needs the same standard, the
    programs are compiled with it; otherwise (no changes file, no entities, a mix, or nothing marked) the target's
    `default_std` (default c++17). Without this a C++20-only change compiled as C++17 is never reached, and the PR
    looks like "no difference" when it was never tested (#6075 in nlohmann/json)."""
    default = t.get("default_std", "c++17")
    if pr is None:
        return default
    try:
        funcs = json.loads((t.data / "changes" / f"{pr}.json").read_text(encoding="utf-8")).get("functions", [])
    except (OSError, ValueError):
        return default
    stds = set()
    for f in funcs:
        flagged = [x[len("-std="):] for x in f.get("requires_flags", []) if x.startswith("-std=")]
        stds.add(flagged[0] if flagged else default)
    return stds.pop() if len(stds) == 1 else default


def git(repo, *args, check=True):
    """Run git in repo and return stdout as text."""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")   # UTF-8 on Windows too
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def write_text(path, text):
    """UTF-8 text with LF line endings on every OS, so files from Windows and macOS diff cleanly."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:   # LF on every OS
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    tmp.replace(path)
