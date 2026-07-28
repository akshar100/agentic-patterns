#!/usr/bin/env python3
"""Inject the badge embed line between AGENTIC_BADGES markers in a README.

Usage: python inject_readme.py README.md .github/agentic-badge.svg .github/agentic-scan.json
No-ops gracefully (exit 0) if the README or markers are absent, so the
Action never fails an adopter's build over a missing marker.
"""
import re
import sys

START, END = "<!-- AGENTIC_BADGES_START -->", "<!-- AGENTIC_BADGES_END -->"

def main():
    readme, badge, scan = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        content = open(readme, encoding="utf-8").read()
    except FileNotFoundError:
        print(f"note: {readme} not found; skipping injection")
        return
    if START not in content or END not in content:
        print("note: AGENTIC_BADGES markers not found; skipping injection. "
              f"Add these lines to {readme} to enable:\n{START}\n{END}")
        return
    embed = f"[![Agentic Patterns]({badge})]({scan})"
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.DOTALL)
    new = pattern.sub(f"{START}\n{embed}\n{END}", content)
    if new != content:
        open(readme, "w", encoding="utf-8").write(new)
        print(f"injected badge embed into {readme}")
    else:
        print("badge embed already up to date")

if __name__ == "__main__":
    main()
