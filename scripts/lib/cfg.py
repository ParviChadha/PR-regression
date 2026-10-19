#!/usr/bin/env python3
"""Print one field of a target's target.toml. Usage: cfg.py <target> <key>
Strings print as-is; lists print one item per line."""
import pathlib, sys, tomllib

root = pathlib.Path(__file__).resolve().parents[2]
target, key = sys.argv[1], sys.argv[2]
path = root / "targets" / target / "target.toml"
if not path.is_file():
    sys.exit(f"unknown target '{target}': {path} not found")
cfg = tomllib.loads(path.read_text())
if key not in cfg:
    sys.exit(f"{path}: missing key '{key}'")
val = cfg[key]
print("\n".join(val) if isinstance(val, list) else val)
