# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

ProofKit is a Python CLI tool (also published as an npm wrapper) that enforces AI development governance. It prevents agents from claiming work is complete without real execution evidence — commands must actually run and pass before phases advance.

Published as `proofkit-cli` on PyPI and `proofkit` on npm. No runtime dependencies (`dependencies = []`).

## Commands

### Development setup

```bash
# Install for local development
pip install -e .
# or
uv pip install -e .
```

### Running tests

```bash
# All tests
pytest

# Single test file
pytest tests/test_workflow.py

# Single test by name
pytest tests/test_workflow.py -k "test_transition"

# With output
pytest -s tests/test_sdd.py
```

### Release check (what CI runs)

```bash
python scripts/release_check.py
```

This script installs the package into a venv, runs the CLI smoke tests, packs the npm tarball, and verifies the Node wrapper — cross-platform (ubuntu, macos, windows).

### CLI (after install)

```bash
proofkit version
proofkit --trace <command>   # component-level debug output to stderr
```

## Architecture

### Python package (`proofkit/`)

`cli.py` is the entry point and re-exports the entire public surface via `*`. The public API is assembled in `__init__.py`.

Internal modules follow a `_wf_*` prefix convention for workflow subsystems:

| Module | Responsibility |
|--------|---------------|
| `_types.py` | Core types: `WorkflowPhase`, `Finding`, `WorkflowState`, `WorkflowResult`, all constants |
| `_workflow.py` | Top-level workflow functions (`run_workflow`, `transition_workflow`, `verify_change`, etc.) |
| `_wf_engine.py` | `WorkflowEngine` — agent execution loop API (`next_step`, `guard`, `execute`) |
| `_wf_registry.py` | `SDDWorkflow` — object-oriented Python API |
| `_wf_inference.py` | Phase inference from artifact frontmatter (infers phase without `state.json`) |
| `_wf_evidence.py` | Command execution, SHA-256 checksumming, evidence storage under `.proofkit/evidence/` |
| `_wf_changeops.py` | Change lifecycle: create, archive, sync-specs, `mark_artifact_ready` |
| `_wf_artifacts.py` | Artifact read/write, frontmatter parsing |
| `_wf_discovery.py` | Auto-detect test runner (pytest, npm test, cargo test, …) |
| `_wf_validation.py` | Repository and artifact validation logic |
| `_wf_infra.py` | Directory initialization, git hook installation |
| `_wf_templates.py` | Template rendering for artifact scaffolding |
| `_render.py` | CLI output (color, phase pipeline display) |
| `_render_auto.py` | `auto` command rendering |
| `_dispatch.py` | Agent dispatchers: `ShellAgentDispatcher`, `ClaudeCodeDispatcher` |
| `_extensions.py` | Extension install/list/remove |

### State directory (`.proofkit/`)

ProofKit manages its own governance state under `.proofkit/` in any target repository. This repo uses ProofKit on itself. Key subdirectories:

- `adapters/` — per-agent JSON capability configs (claude-code, cursor, gemini-cli, codex, github-copilot, opencode, qwen-code, generic-markdown)
- `agents/` — agent role prompts (orchestrator, explorer, specifier, architect, planner, implementer, verifier, critic, archivist)
- `profiles/` — artifact sets per profile (quick, standard, bugfix, refactor, enterprise, research)
- `skills/` — per-phase skill instructions (propose, specify, design, task, implement, verify, critique, sync-specs, archive)
- `changes/` — active change artifacts
- `evidence/` — checksummed command execution records
- `archive/` — closed changes
- `specs/` — living specs updated by `sync-specs`
- `state.json` — declared workflow phases

### Workflow phase order

```
not-started → propose → specify → design → task → verify → critique → archive-record → sync-specs → archive → archived
```

Phase transitions are enforced by `ALLOWED_TRANSITIONS` in `_types.py`. `verify` can only be recorded via `proofkit verify` (not `proofkit transition`).

### Node wrapper (`bin/`)

`bin/proofkit.js` is a thin Node.js shim that locates Python and delegates to `proofkit.cli:main`. Published as the `proofkit` npm package for teams that prefer `npx`.

## Test Suite

Tests are in `tests/`. The largest file is `test_sdd.py` (~118KB), which covers the full integration surface. Narrower unit suites:

- `test_contracts.py` — adapter/schema contract tests
- `test_core.py` — core type and constant tests
- `test_execution_evidence.py` — evidence recording and checksumming
- `test_features.py` — CLI feature coverage
- `test_golden.py` — Golden Path end-to-end
- `test_inference.py` — phase inference from artifacts
- `test_verify.py` — verification command execution
- `test_workflow.py` — phase transition enforcement

## Version Management

`VERSION` is declared as a string in `proofkit/_types.py` and must match `version` in both `pyproject.toml` and `package.json`. The `scripts/release_check.py` verifies this alignment. Update all three when bumping.

## CI

CI (`ci.yml`) runs `python scripts/release_check.py` on ubuntu, macos, and windows with Python 3.11 and Node 20. There is no separate `pytest` step in CI — the release check script drives the test surface.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
