#!/usr/bin/env python3
"""Summarize a `ctest -V` log (doctest executables). Usage: summarize.py <ctest.log>"""
import re, sys
log = open(sys.argv[1], errors="replace").read()
m = re.search(r"(\d+)% tests passed, (\d+) tests failed out of (\d+)", log)
print("ctest:", m.group(0) if m else "no ctest summary found")
tc = tp = tf = ts = ta = tap = taf = 0
for t in re.finditer(r"\[doctest\] test cases:\s*(\d+) \|\s*(\d+) passed \|\s*(\d+) failed \|\s*(\d+) skipped", log):
    a, b, c, d = map(int, t.groups()); tc += a; tp += b; tf += c; ts += d
for t in re.finditer(r"\[doctest\] assertions:\s*(\d+) \|\s*(\d+) passed \|\s*(\d+) failed", log):
    a, b, c = map(int, t.groups()); ta += a; tap += b; taf += c
print(f"doctest test cases (summed over all executables): {tc} | passed {tp} | failed {tf} | skipped {ts}")
print(f"doctest assertions (summed): {ta} | passed {tap} | failed {taf}")
fails = re.findall(r"^\s*\d+/\d+ Test\s+#\d+: (\S+) \.+\**\s*(?:\*\*\*)?(Failed|Timeout|Not Run)", log, re.M)
print("failed/not-run ctest tests:", fails or "none")
sk = re.findall(r"^\s*\d+/\d+ Test\s+#\d+: (\S+) \.+\s*(?:\*+)?Skipped", log, re.M)
print("ctest-skipped tests:", sk or "none")
