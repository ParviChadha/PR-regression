#!/usr/bin/env python3
"""Compare per-test outcomes (order-independent) across ctest -V logs. Usage: compare.py <log> <log>..."""
import re, sys

def results(path):
    return dict(re.findall(r"Test +#\d+: (\S+) \.+\**\s*(?:\*\*\*)?(Passed|Failed|Timeout|Not Run|Skipped)", open(path, errors="replace").read()))

runs = [results(p) for p in sys.argv[1:]]
base, bad = runs[0], 0
for p, r in zip(sys.argv[2:], runs[1:]):
    for k in sorted(set(base) | set(r)):
        if base.get(k) != r.get(k):
            bad += 1; print(f"DIFF {k}: {base.get(k)} vs {r.get(k)} ({p})")
print(f"{len(base)} tests per run, {len(runs)} runs compared, {bad} differences")
