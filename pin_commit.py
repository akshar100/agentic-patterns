#!/usr/bin/env python3
"""Pin the scan result to the CI commit and emit the Action output.

Evidence line numbers are only verifiable against an exact commit, so the
Action stamps GITHUB_SHA/GITHUB_REPOSITORY into the scan JSON after scanning.
Prints `pattern-count=N` for $GITHUB_OUTPUT.
"""
import json
import os
import sys

path = sys.argv[1]
r = json.load(open(path))
sha = os.environ.get("GITHUB_SHA")
repo = os.environ.get("GITHUB_REPOSITORY")
if sha:
    r["repo"]["commit"] = sha
if repo:
    r["repo"]["url"] = f"https://github.com/{repo}"
json.dump(r, open(path, "w"), indent=2)
print(f"pattern-count={r['summary']['pattern_count']}")
