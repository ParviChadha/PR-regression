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
        self.cfg = tomllib.loads(path.read_text())
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


def git(repo, *args, check=True):
    """Run git in repo and return stdout as text."""
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    tmp.replace(path)
