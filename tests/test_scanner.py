#!/usr/bin/env python3
"""Regression test: the fixture repo must yield exactly the expected patterns.

This is the release gate. Because the rules YAML ships to every adopter's CI
on their next run, no rules change may merge unless this passes.
Run: python tests/test_scanner.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = {"structured_workflow", "react_loop", "checkpointing", "protocol_integration"}

def main():
    out = Path(tempfile.mkdtemp()) / "scan.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scanner.py"), str(ROOT / "tests" / "fixture"),
         str(ROOT / "agentic-pattern-rules.yaml"), str(out)],
        check=True,
    )
    result = json.loads(out.read_text())
    got = {p["id"] for p in result["patterns"]}
    assert got == EXPECTED, f"pattern mismatch:\n  expected {sorted(EXPECTED)}\n  got      {sorted(got)}"
    for p in result["patterns"]:
        assert p["evidence"], f"{p['id']} has no evidence"
        assert all("file" in e for e in p["evidence"]), f"{p['id']} evidence missing file"
    try:
        import jsonschema
        jsonschema.validate(result, json.loads((ROOT / "scan-result.schema.json").read_text()))
        print("schema validation OK")
    except ImportError:
        print("jsonschema not installed; skipping schema validation")
    print(f"OK: {sorted(got)}")

if __name__ == "__main__":
    main()
