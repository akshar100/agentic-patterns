# Agentic Pattern Linter

A GitHub Action that statically detects **agentic AI architectural patterns** in your
codebase and generates an evidence-backed badge — with every claim traceable to a
`file:line` in your source.

<!-- AGENTIC_BADGES_START -->
<!-- AGENTIC_BADGES_END -->

Pattern names follow the peer-reviewed taxonomy in
*Architectural Patterns for Agentic AI Systems: A Survey and Taxonomy*
([agenticprotocols.dev](https://agenticprotocols.dev)), which organizes agentic
architectures along four dimensions — control flow, agent multiplicity, memory
scope, and human involvement. The badge's four-quadrant glyph lights one quadrant
per dimension detected in your repo.

## Install (2 minutes)

1. Copy [`examples/adopter-workflow.yml`](examples/adopter-workflow.yml) into your
   repo as `.github/workflows/agentic-badge.yml`.
2. Add these two lines to your `README.md` where the badge should appear:
   ```html
   <!-- AGENTIC_BADGES_START -->
   <!-- AGENTIC_BADGES_END -->
   ```
3. Push. The Action scans your code, writes `.github/agentic-badge.svg` and
   `.github/agentic-scan.json`, injects the badge between the markers, and
   commits the result. The badge links to the scan JSON so anyone can audit
   the evidence behind every pattern claim.

**Branch protection on `main`?** Have the workflow push to a `badges` branch
instead and embed via
`https://raw.githubusercontent.com/OWNER/REPO/badges/.github/agentic-badge.svg`.

## How detection works

- **Deterministic, not vibes.** Detection is AST-based (imports, call symbols,
  call keywords), driven by a versioned rules table
  ([`agentic-pattern-rules.yaml`](agentic-pattern-rules.yaml)) covering
  LangGraph/LangChain, AutoGen, CrewAI, MetaGPT, OpenAI Agents SDK,
  Claude Agent SDK, Semantic Kernel, and LlamaIndex — plus config signals
  (e.g. `mcp.json`). No regex over raw text, no LLM guessing.
- **Every claim carries evidence.** The scan output
  ([schema](scan-result.schema.json)) records the matched symbol, file, line,
  and a source excerpt, pinned to the exact commit scanned.
- **Honest uncertainty.** Patterns are marked `detected` (static analysis) and
  carry a `high`/`medium` confidence from the rule that fired. A repo using no
  known framework yields "none found" — never a guess.

Current scope: Python sources; TypeScript support is planned via tree-sitter.
Structural (Tier 2) detection of hand-rolled scaffolds — ReAct loops,
plan-then-execute, reflection — is specified in the rules file and under
development.

## Detected patterns

| ID | Pattern | Taxonomy § |
|---|---|---|
| `react_loop` | Reason and Act Loop | IV-A |
| `plan_then_execute` | Plan-Then-Execute | IV-B |
| `search_over_actions` | Search over Actions | IV-C |
| `reflection` | Reflection and Self-Correction | IV-D |
| `code_as_action` | Code-as-Action | IV-E |
| `structured_workflow` | Structured Workflow with Agentic Islands | IV-F |
| `orchestrator_worker` | Orchestrator–Worker | V-A |
| `peer_debate_ensemble` | Peer Debate and Ensembling | V-B |
| `role_based_team` | Role-Based Teams | V-C |
| `conversational_multi_agent` | Conversational Multi-Agent | V-D |
| `handoff` | Handoff | V-E |
| `context_management` | Context Window Management | VI-A |
| `episodic_memory` | Episodic External Memory | VI-B |
| `procedural_memory` | Structured and Procedural Memory | VI-C |
| `shared_memory_blackboard` | Shared Memory and Blackboards | VI-D |
| `checkpointing` | Checkpointing and Resumability | VI-E |
| `human_in_the_loop` | Human-in-the-Loop | VII-A |
| `protocol_integration` | Protocol-Level Integration (MCP/A2A) | VII-B |
| `sandboxing` | Sandboxing and Permissioning | VII-C |

## Running locally

```bash
pip install pyyaml
python scanner.py /path/to/repo agentic-pattern-rules.yaml scan.json
python badge.py scan.json badge.svg
```

## Contributing rules

Framework APIs move fast. To add or update detection for a framework, edit
`agentic-pattern-rules.yaml` (symbols, kwargs, confidence) and add a fixture
under `tests/` demonstrating the match. CI gates every rules change on the
regression suite — a wrong rule ships a wrong claim to every adopter's README,
so precision beats coverage.

## Inputs

| Input | Default | Description |
|---|---|---|
| `badge-path` | `.github/agentic-badge.svg` | Badge output path |
| `scan-path` | `.github/agentic-scan.json` | Evidence file output path |
| `badge-style` | `full` | `full` (named patterns) or `compact` (count) |
| `inject-readme` | `true` | Inject embed between `AGENTIC_BADGES` markers |
| `readme-path` | `README.md` | README to inject into |
