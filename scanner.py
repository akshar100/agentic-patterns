#!/usr/bin/env python3
"""Tier-1 agentic pattern scanner.

Consumes agentic-pattern-rules.yaml, walks a repo, emits scan-result JSON
(conformant to scan-result.schema.json) that badge.py can render.

Pipeline stages:
  1. Dependency fingerprinting: match rules' `package` lists against
     requirements.txt / pyproject.toml / package.json.
  2. AST pass (Python only in v0): collect imports, call symbols, decorator
     names, and call keywords with file:line locations.
  3. Rule matching: for each framework whose package OR imports matched,
     fire rules on symbol/kwarg hits and record evidence.
  4. Config signals: file-existence checks (mcp.json etc.).
  5. Emit JSON: patterns, evidence, summary dimensions, badge endpoint.

Usage:  python scanner.py <repo_dir> <rules.yaml> <out.json>
Limitations (v0, by design): Python sources only; matches attribute leaf
names (Runner.run matches `.run(` on anything named Runner-ish is NOT
verified — we match the full dotted tail when given); no Tier-2 dataflow.
"""

import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Taxonomy dimension map (paper Section III) — drives the badge glyph.
DIMENSIONS = {
    "control_flow": {"react_loop", "plan_then_execute", "search_over_actions",
                     "reflection", "code_as_action", "structured_workflow"},
    "agent_multiplicity": {"orchestrator_worker", "peer_debate_ensemble",
                           "role_based_team", "conversational_multi_agent", "handoff"},
    "memory_scope": {"context_management", "episodic_memory", "procedural_memory",
                     "shared_memory_blackboard", "checkpointing"},
    "human_involvement": {"human_in_the_loop"},
}

NAMES = {
    "react_loop": ("Reason and Act Loop", "ReAct", "IV-A"),
    "plan_then_execute": ("Plan-Then-Execute", "Plan-Exec", "IV-B"),
    "search_over_actions": ("Search over Actions", "Search", "IV-C"),
    "reflection": ("Reflection and Self-Correction", "Reflect", "IV-D"),
    "code_as_action": ("Code-as-Action", "CodeAct", "IV-E"),
    "structured_workflow": ("Structured Workflow with Agentic Islands", "Workflow", "IV-F"),
    "orchestrator_worker": ("Orchestrator-Worker", "Orch-Worker", "V-A"),
    "peer_debate_ensemble": ("Peer Debate and Ensembling", "Debate", "V-B"),
    "role_based_team": ("Role-Based Teams", "Roles", "V-C"),
    "conversational_multi_agent": ("Conversational Multi-Agent", "GroupChat", "V-D"),
    "handoff": ("Handoff", "Handoff", "V-E"),
    "context_management": ("Context Window Management", "Context", "VI-A"),
    "episodic_memory": ("Episodic External Memory", "Memory", "VI-B"),
    "procedural_memory": ("Structured and Procedural Memory", "Skills", "VI-C"),
    "shared_memory_blackboard": ("Shared Memory and Blackboards", "Blackboard", "VI-D"),
    "checkpointing": ("Checkpointing and Resumability", "Checkpoint", "VI-E"),
    "human_in_the_loop": ("Human-in-the-Loop", "HITL", "VII-A"),
    "protocol_integration": ("Protocol-Level Integration", "MCP", "VII-B"),
    "sandboxing": ("Sandboxing and Permissioning", "Sandbox", "VII-C"),
}

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
             "dist", "build", ".tox", "site-packages"}


# ---------------------------------------------------------------- stage 1
def read_dependencies(repo: Path) -> dict[str, str]:
    """Map of lowercase package name -> relative dep-file path where first seen."""
    deps: dict[str, str] = {}

    def add(name: str, src: Path):
        deps.setdefault(name.lower(), str(src.relative_to(repo)))

    for req in repo.rglob("requirements*.txt"):
        if any(p in SKIP_DIRS for p in req.parts):
            continue
        for line in req.read_text(errors="ignore").splitlines():
            line = line.split("#")[0].strip()
            if line:
                add(re.split(r"[<>=\[~!; ]", line)[0], req)
    for pp in repo.rglob("pyproject.toml"):
        if any(p in SKIP_DIRS for p in pp.parts):
            continue
        for m in re.finditer(r'"([A-Za-z0-9_.@/\-]+?)(?:[<>=\[~!].*?)?"', pp.read_text(errors="ignore")):
            add(m.group(1), pp)
    for pj in repo.rglob("package.json"):
        if any(p in SKIP_DIRS for p in pj.parts):
            continue
        try:
            data = json.loads(pj.read_text(errors="ignore"))
            for key in ("dependencies", "devDependencies"):
                for k in data.get(key, {}):
                    add(k, pj)
        except json.JSONDecodeError:
            pass
    return deps


# ---------------------------------------------------------------- stage 2
class SymbolCollector(ast.NodeVisitor):
    """Collects imports, used symbols, and call keywords with locations."""

    def __init__(self, relpath: str, source_lines: list[str]):
        self.relpath = relpath
        self.lines = source_lines
        self.imports: list[tuple[str, int]] = []           # module path, line
        self.symbols: list[tuple[str, int, str]] = []      # name, line, excerpt
        self.kwargs: list[tuple[str, int, str]] = []       # kwarg name, line, excerpt

    def _excerpt(self, lineno: int) -> str:
        try:
            return self.lines[lineno - 1].strip()[:200]
        except IndexError:
            return ""

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        mod = node.module or ""
        self.imports.append((mod, node.lineno))
        for alias in node.names:
            # `from agents import Runner` makes Runner a usable symbol
            self.symbols.append((alias.name, node.lineno, self._excerpt(node.lineno)))
        self.generic_visit(node)

    @staticmethod
    def _dotted(node) -> str | None:
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        return None

    def visit_Call(self, node):
        name = self._dotted(node.func)
        if name:
            self.symbols.append((name, node.lineno, self._excerpt(node.lineno)))
        for kw in node.keywords:
            if kw.arg:
                self.kwargs.append((kw.arg, node.lineno, self._excerpt(node.lineno)))
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        for dec in node.decorator_list:
            name = self._dotted(dec.func if isinstance(dec, ast.Call) else dec)
            if name:
                self.symbols.append(("@" + name, node.lineno, self._excerpt(node.lineno)))
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def collect_repo_symbols(repo: Path):
    collectors = []
    for py in repo.rglob("*.py"):
        if any(p in SKIP_DIRS for p in py.parts):
            continue
        try:
            src = py.read_text(errors="ignore")
            tree = ast.parse(src)
        except SyntaxError:
            continue
        c = SymbolCollector(str(py.relative_to(repo)), src.splitlines())
        c.visit(tree)
        collectors.append(c)
    return collectors


# ---------------------------------------------------------------- stage 3
def _symbol_hits(rule_symbols, collectors):
    """A rule symbol matches a used symbol if it equals the full dotted name
    or its trailing segment(s). '@x' matches decorators exactly."""
    hits = []
    for want in rule_symbols or []:
        for c in collectors:
            for name, line, excerpt in c.symbols:
                if name == want or name.endswith("." + want.lstrip("@")) \
                        or (want.startswith("@") and name == want):
                    hits.append((want, c.relpath, line, excerpt))
    return hits


def _kwarg_hits(rule_kwargs, collectors):
    hits = []
    for want in rule_kwargs or []:
        for c in collectors:
            for kwarg, line, excerpt in c.kwargs:
                if kwarg == want:
                    hits.append((want, c.relpath, line, excerpt))
    return hits


def match_rules(rules: dict, deps: set, collectors) -> tuple[list, list]:
    frameworks_found, pattern_map = [], {}

    for fw_id, fw in rules.get("frameworks", {}).items():
        pkg_hit = any(p.lower() in deps for p in fw.get("package", []))
        import_hit = any(
            imp == mod or imp.startswith(mod + ".")
            for c in collectors for imp, _ in c.imports
            for mod in [p.replace("-", "_") for p in fw.get("package", [])]
        )
        if not (pkg_hit or import_hit):
            continue
        frameworks_found.append({
            "id": fw_id,
            "source": "both" if (pkg_hit and import_hit) else ("dependency" if pkg_hit else "import"),
        })
        for rule in fw.get("rules", []):
            evid = []
            for sym, f, line, ex in _symbol_hits(rule.get("symbols"), collectors):
                evid.append({"type": "symbol", "file": f, "line": line, "symbol": sym,
                             "rule_id": f"{fw_id}/{rule['pattern']}", "excerpt": ex})
            for kw, f, line, ex in _kwarg_hits(
                    (rule.get("also_match_kwargs") or []) + (rule.get("require_kwargs") or []),
                    collectors):
                evid.append({"type": "kwarg", "file": f, "line": line, "symbol": kw,
                             "rule_id": f"{fw_id}/{rule['pattern']}", "excerpt": ex})
            # require_kwargs means: symbol hit only counts if the kwarg co-occurs
            if rule.get("require_kwargs") and not any(e["type"] == "kwarg" for e in evid):
                continue
            if not evid:
                continue
            pid = rule["pattern"]
            entry = pattern_map.setdefault(pid, {"confidence": rule.get("confidence", "medium"),
                                                 "evidence": []})
            entry["evidence"].extend(evid[:5])   # cap evidence per pattern
    return frameworks_found, pattern_map


def match_config_signals(rules, repo: Path, pattern_map, frameworks_found, dep_files=None):
    for sig in rules.get("config_signals", []):
        if sig.get("require_cooccurrence") and not frameworks_found:
            continue
        for fname in sig.get("files", []):
            for hit in repo.rglob(fname):
                if any(p in SKIP_DIRS for p in hit.parts):
                    continue
                entry = pattern_map.setdefault(
                    sig["pattern"], {"confidence": sig.get("confidence", "medium"), "evidence": []})
                entry["evidence"].append({
                    "type": "config", "file": str(hit.relative_to(repo)),
                    "rule_id": f"config/{sig['pattern']}"})
        # package_any: dependency alone signals the pattern (e.g. `mcp` SDK)
        for pkg in sig.get("package_any", []):
            src = (dep_files or {}).get(pkg.lower())
            if src:
                entry = pattern_map.setdefault(
                    sig["pattern"], {"confidence": sig.get("confidence", "medium"), "evidence": []})
                entry["evidence"].append({
                    "type": "config", "file": src, "symbol": pkg,
                    "rule_id": f"config/{sig['pattern']}"})


# ---------------------------------------------------------------- stage 5
def build_result(repo: Path, rules_version, frameworks_found, pattern_map):
    patterns = []
    for pid, entry in pattern_map.items():
        name, abbrev, section = NAMES[pid]
        patterns.append({
            "id": pid, "name": name, "abbrev": abbrev, "section": section,
            "tier": 1, "status": "detected", "confidence": entry["confidence"],
            "evidence": entry["evidence"],
        })
    patterns.sort(key=lambda p: {"high": 0, "medium": 1, "low": 2}[p["confidence"]])
    dims = {d: any(p["id"] in ids for p in patterns) for d, ids in DIMENSIONS.items()}
    return {
        "schema_version": "0.1",
        "tool": {"name": "agentic-pattern-linter", "version": "0.1.0",
                 "rules_version": str(rules_version)},
        "repo": {"url": f"file://{repo.resolve()}", "commit": "0000000",
                 "scanned_at": datetime.now(timezone.utc).isoformat(),
                 "languages": ["python"]},
        "frameworks": frameworks_found,
        "patterns": patterns,
        "summary": {"pattern_count": len(patterns),
                    "detected_count": len(patterns), "inferred_count": 0,
                    "dimensions": dims},
    }


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    repo, rules_path, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    rules = yaml.safe_load(open(rules_path))
    deps = read_dependencies(repo)
    collectors = collect_repo_symbols(repo)
    frameworks_found, pattern_map = match_rules(rules, deps, collectors)
    match_config_signals(rules, repo, pattern_map, frameworks_found, dep_files=deps)
    result = build_result(repo, rules.get("meta", {}).get("schema_version", "?"),
                          frameworks_found, pattern_map)
    json.dump(result, open(out, "w"), indent=2)
    print(f"{len(frameworks_found)} framework(s), {len(result['patterns'])} pattern(s) -> {out}")


if __name__ == "__main__":
    main()
