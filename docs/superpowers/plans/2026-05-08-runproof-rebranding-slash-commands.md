# RunProof — Rebranding + Slash Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the tool from ProofKit/SDD to RunProof across every layer (CLI, PyPI, npm, state dir, templates, schemas, generated content), add `runproof next` and `runproof status --json`, auto-detect active change_id, add `constitution` memory key, and ship native slash command templates for Copilot and Claude Code.

**Architecture:** Rename the Python package `proofkit/` → `runproof/` and update every string literal that leaks old brand names, including generated/scaffolded content. Add three new features on top of the renamed base: `runproof next` (single-command advance), `status --json` (machine-readable output), and active-change auto-detection. Slash command templates are plain markdown files with per-integration formatting.

**Tech Stack:** Python 3.11+, argparse, setuptools, Node.js (npm wrapper). Tests use `unittest` + `tmp_path` pattern via `uuid`. No new dependencies.

---

## File map

| File | Action | Purpose |
|---|---|---|
| `proofkit/` → `runproof/` | Rename dir | Python package root |
| `runproof/_types.py` | Modify | `SDD_DIR`, `MEMORY_KEYS`, `VERSION`, all brand strings |
| `runproof/_wf_templates.py` | Modify | `_INTEGRATION_COMMAND_DIRS` paths, `_COMMAND_FILES`, add Copilot template support |
| `runproof/_wf_infra.py` | Modify | Hook/CI template strings `proofkit` → `runproof` |
| `runproof/_wf_changeops.py` | Modify | `resolve_active_change_id()` helper |
| `runproof/_render.py` | Modify | `print_status_json()`, update all output strings |
| `runproof/cli.py` | Modify | Add `next` subcommand, add `--json` to `status`, update brand strings |
| `runproof/_workflow.py` | Modify | Export `resolve_active_change_id`, update brand strings |
| `runproof/templates/sdd/` → `runproof/templates/runproof/` | Rename dir | Template assets |
| `runproof/templates/runproof/**/*.json` | Modify | `schema: "runproof.*"` and command strings |
| `runproof/templates/runproof/agents/*.md` | Modify | `proofkit` → `runproof` in body |
| `runproof/templates/runproof/skills/*.md` | Modify | `proofkit` → `runproof` in body |
| `runproof/templates/runproof/memory/constitution.md` | Create | New constitution template |
| `runproof/templates/commands/runproof-next.md` | Create | Claude Code slash command |
| `runproof/templates/commands/runproof-new.md` | Create | Claude Code slash command |
| `runproof/templates/commands/runproof-status.md` | Create | Claude Code slash command |
| `runproof/templates/commands/runproof-verify.md` | Create | Claude Code slash command |
| `runproof/templates/commands/runproof-constitution.md` | Create | Claude Code slash command |
| `runproof/templates/commands/copilot/runproof-next.prompt.md` | Create | Copilot slash command |
| `runproof/templates/commands/copilot/runproof-new.prompt.md` | Create | Copilot slash command |
| `runproof/templates/commands/copilot/runproof-status.prompt.md` | Create | Copilot slash command |
| `runproof/templates/commands/copilot/runproof-verify.prompt.md` | Create | Copilot slash command |
| `runproof/templates/commands/copilot/runproof-constitution.prompt.md` | Create | Copilot slash command |
| `bin/proofkit.js` → `bin/runproof.js` | Rename+modify | npm wrapper, env var names |
| `pyproject.toml` | Modify | `name`, `scripts`, `authors`, `keywords` |
| `package.json` | Modify | `name`, `bin`, `files`, `keywords` |
| `scripts/sdd.py` | Modify | Brand strings |
| `tests/test_core.py` | Modify | All `proofkit`/`sdd` references, `_COMMAND_FILE_NAMES` |
| `tests/test_workflow.py` | Modify | All `proofkit`/`sdd` references |
| `tests/test_*.py` (remaining) | Modify | All `proofkit`/`sdd` references |
| `CLAUDE.md` | Modify | Brand strings |

---

## Task 1: Rename Python package directory and fix imports

**Files:**
- Rename: `proofkit/` → `runproof/`
- Modify: `runproof/__init__.py`

- [ ] **Step 1: Rename the package directory**

```bash
git mv proofkit runproof
```

- [ ] **Step 2: Update `__init__.py` internal import paths**

Open `runproof/__init__.py`. Every `from proofkit` or `from .` reference is fine since they're relative — just verify no absolute `proofkit.*` imports remain:

```bash
grep -rn "from proofkit\|import proofkit" runproof/
```

Expected: zero results (all imports inside the package are relative).

- [ ] **Step 3: Update `runproof/__main__.py` if it exists**

```bash
grep -rn "proofkit" runproof/__main__.py 2>/dev/null || echo "no __main__.py"
```

If found, replace `proofkit` with `runproof`.

- [ ] **Step 4: Run tests to verify import chain still works**

```bash
pip install -e . && python -m runproof version
```

Expected: version number printed (or error about `proofkit` not found — that's the next task).

- [ ] **Step 5: Commit**

```bash
git add runproof/ proofkit/
git commit -m "refactor: rename Python package proofkit → runproof"
```

---

## Task 2: Rebrand `_types.py` — constants and strings

**Files:**
- Modify: `runproof/_types.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py` inside `TestCore`:

```python
def test_runproof_brand_constants(self) -> None:
    self.assertEqual(sdd.SDD_DIR, ".runproof")
    self.assertIn("constitution", sdd.MEMORY_KEYS)
    self.assertNotIn("proofkit", sdd.VERSION.lower())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::TestCore::test_runproof_brand_constants -v
```

Expected: FAIL — `SDD_DIR` is `.proofkit`, `constitution` not in `MEMORY_KEYS`.

- [ ] **Step 3: Update `SDD_DIR` and `MEMORY_KEYS`**

In `runproof/_types.py`:

```python
# was: SDD_DIR = ".proofkit"
SDD_DIR = ".runproof"

# was: MEMORY_KEYS = ["project", "decisions"]
MEMORY_KEYS = ["project", "decisions", "constitution"]

# was: MEMORY_COPY_FILES = ["project.md", "decisions.md"]
MEMORY_COPY_FILES = ["project.md", "decisions.md", "constitution.md"]
```

- [ ] **Step 4: Update `REQUIRED_DIRECTORIES` list**

```python
REQUIRED_DIRECTORIES = [
    ".runproof",
    ".runproof/adapters",
    ".runproof/agents",
    ".runproof/memory",
    ".runproof/profiles",
    ".runproof/schemas",
    ".runproof/skills",
    ".runproof/specs",
    ".runproof/changes",
    ".runproof/archive",
    ".runproof/evidence",
    ".runproof/extensions",
]
```

- [ ] **Step 5: Update `PHASE_NEXT_ACTIONS` strings**

Replace all `proofkit` in action strings:

```python
PHASE_NEXT_ACTIONS: dict[WorkflowPhase, str] = {
    WorkflowPhase.NOT_STARTED:    "Create the governed change artifacts.",
    WorkflowPhase.PROPOSE:        "Complete proposal.md and set status to ready.",
    WorkflowPhase.SPECIFY:        "Complete delta-spec.md and set status to ready.",
    WorkflowPhase.DESIGN:         "Complete design.md and set status to ready.",
    WorkflowPhase.TASK:           "Complete tasks.md — check off all tasks and set status to ready.",
    WorkflowPhase.VERIFY:         "Record evidence in verification.md and set status to verified.",
    WorkflowPhase.CRITIQUE:       "Resolve critique.md and set status to ready or verified.",
    WorkflowPhase.ARCHIVE_RECORD: "Complete archive.md and set status to ready.",
    WorkflowPhase.SYNC_SPECS:     "Run `runproof sync-specs <change_id> --root <repo>`.",
    WorkflowPhase.ARCHIVE:        "Run `runproof archive <change_id> --root <repo>`.",
    WorkflowPhase.ARCHIVED:       "Review archived change evidence.",
    WorkflowPhase.BLOCKED:        "Resolve blocking findings before continuing.",
}
```

- [ ] **Step 6: Update `FOUNDATION_DOC_FILES` — remove `proofkit-protocol` reference**

```python
FOUNDATION_DOC_FILES = [
    "adapter-contract-v0.1.md",
    "adapter-authoring-v0.1.md",
    "adapters-v0.1.md",
    "production-readiness-v0.1.md",
    "runproof-protocol-v0.1.md",
    "sdd-validator-v0.1.md",
]
```

- [ ] **Step 7: Run test to verify it passes**

```bash
pytest tests/test_core.py::TestCore::test_runproof_brand_constants -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add runproof/_types.py tests/test_core.py
git commit -m "refactor: update SDD_DIR to .runproof, add constitution MEMORY_KEY"
```

---

## Task 3: Rebrand `pyproject.toml`, `package.json`, and `bin/runproof.js`

**Files:**
- Modify: `pyproject.toml`, `package.json`
- Rename+Modify: `bin/proofkit.js` → `bin/runproof.js`

- [ ] **Step 1: Write the failing test**

In `tests/test_core.py`, update the existing version test:

```python
def test_version_is_consistent_across_pyproject_and_package_json(self) -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

    self.assertEqual(pyproject["project"]["version"], sdd.VERSION)
    self.assertEqual(package["version"], sdd.VERSION)
    self.assertEqual(pyproject["project"]["name"], "runproof-cli")
    self.assertEqual(package["name"], "runproof-cli")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::TestCore::test_version_is_consistent_across_pyproject_and_package_json -v
```

Expected: FAIL — names are still `proofkit-cli`.

- [ ] **Step 3: Update `pyproject.toml`**

```toml
[project]
name = "runproof-cli"
version = "0.27.0"
description = "AI development governance engine — prevent hallucinated completion and vanishing intent in agent-assisted software teams."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [
  { name = "RunProof contributors" }
]
keywords = ["runproof", "spec-driven-development", "agents", "ai", "workflow", "governance"]

[project.scripts]
runproof = "runproof.cli:main"

[tool.setuptools.packages.find]
include = ["runproof*"]

[tool.setuptools.package-data]
runproof = ["templates/**/*"]
```

- [ ] **Step 4: Update `package.json`**

```json
{
  "name": "runproof-cli",
  "version": "0.27.0",
  "description": "AI development governance engine — prevent hallucinated completion and vanishing intent in agent-assisted software teams.",
  "license": "MIT",
  "bin": {
    "runproof": "bin/runproof.js"
  },
  "files": [
    "bin/",
    "runproof/",
    "scripts/",
    "README.md",
    "LICENSE",
    "NOTICE.md",
    "CHANGELOG.md",
    "docs/",
    "!**/__pycache__/**",
    "!**/*.pyc",
    "!docs/superpowers/**"
  ],
  "keywords": ["runproof", "spec-driven-development", "agents", "ai", "workflow"],
  "engines": { "node": ">=18" }
}
```

- [ ] **Step 5: Rename and update `bin/runproof.js`**

```bash
git mv bin/proofkit.js bin/runproof.js
```

Edit `bin/runproof.js`:

```javascript
#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");
const args = process.argv.slice(2);

function pythonCandidates() {
  const configuredPython = process.env.RUNPROOF_PYTHON;
  if (configuredPython) {
    return [[configuredPython, []]];
  }
  if (process.platform === "win32") {
    return [["py", ["-3"]], ["python", []], ["python3", []]];
  }
  return [["python3", []], ["python", []]];
}

function runPython(command, prefixArgs) {
  const env = { ...process.env };
  env.PYTHONPATH = env.PYTHONPATH
    ? `${packageRoot}${path.delimiter}${env.PYTHONPATH}`
    : packageRoot;
  return spawnSync(command, [...prefixArgs, "-m", "runproof", ...args], {
    cwd: process.cwd(),
    env,
    stdio: "inherit",
  });
}

for (const [command, prefixArgs] of pythonCandidates()) {
  const result = runPython(command, prefixArgs);
  if (!result.error) {
    process.exit(result.status === null ? 1 : result.status);
  }
  if (result.error.code !== "ENOENT") {
    console.error(`runproof failed to launch Python via ${command}: ${result.error.message}`);
    process.exit(1);
  }
}

console.error("runproof requires Python 3.11+ on PATH. Set RUNPROOF_PYTHON to a Python executable if needed.");
process.exit(1);
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pip install -e . && pytest tests/test_core.py::TestCore::test_version_is_consistent_across_pyproject_and_package_json -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml package.json bin/
git commit -m "refactor: rename package to runproof-cli, update bin wrapper"
```

---

## Task 4: Rebrand templates — rename `sdd/` dir and update all internal strings

**Files:**
- Rename: `runproof/templates/sdd/` → `runproof/templates/runproof/`
- Modify: all `*.json`, `*.md` files inside

- [ ] **Step 1: Rename the template directory**

```bash
git mv runproof/templates/sdd runproof/templates/runproof
```

- [ ] **Step 2: Update all `schema: "sdd.*"` in JSON adapter files**

```bash
sed -i 's/"schema": "sdd\./"schema": "runproof./g' runproof/templates/runproof/adapters/*.json
sed -i 's/"schema": "sdd\./"schema": "runproof./g' runproof/templates/runproof/schemas/*.json
```

- [ ] **Step 3: Update `required_core_commands` in adapter JSONs**

```bash
grep -rn "ssd-core\|proofkit" runproof/templates/runproof/adapters/
```

For each match, replace with `runproof`. Example — `github-copilot.json`:

```json
"required_core_commands": ["runproof validate", "runproof status", "runproof next"]
```

- [ ] **Step 4: Update `proofkit` command references in agents and skills**

```bash
find runproof/templates/runproof/agents runproof/templates/runproof/skills -name "*.md" \
  -exec sed -i 's/proofkit /runproof /g; s/`proofkit/`runproof/g' {} \;
```

- [ ] **Step 5: Update `template_sdd_root()` in `_wf_templates.py`**

```python
def template_sdd_root() -> TemplateResource:
    source_checkout_template = Path(__file__).resolve().parents[1] / SDD_DIR
    if source_checkout_template.is_dir():
        return source_checkout_template
    return files("runproof").joinpath("templates", "runproof")  # type: ignore[return-value]


def template_docs_root() -> TemplateResource:
    source_checkout_docs = Path(__file__).resolve().parents[1] / "docs"
    if source_checkout_docs.is_dir():
        return source_checkout_docs
    return files("runproof").joinpath("templates", "docs")


def template_commands_root() -> TemplateResource:
    source_checkout = Path(__file__).resolve().parent / "templates" / "commands"
    if source_checkout.is_dir():
        return source_checkout
    return files("runproof").joinpath("templates", "commands")


def template_memory_root() -> TemplateResource:
    source_checkout = Path(__file__).resolve().parent / "templates" / "runproof" / "memory"
    if source_checkout.is_dir():
        return source_checkout
    return files("runproof").joinpath("templates", "runproof", "memory")
```

- [ ] **Step 6: Update `test_packaged_templates_are_present` in `test_core.py`**

```python
def test_packaged_templates_are_present(self) -> None:
    template_root = files("runproof").joinpath("templates")

    self.assertTrue(template_root.joinpath("runproof", "constitution.md").is_file())
    self.assertTrue(template_root.joinpath("runproof", "state.json").is_file())
    self.assertTrue(template_root.joinpath("runproof", "evidence", ".gitkeep").is_file())
    self.assertTrue(template_root.joinpath("runproof", "adapters", "claude-code.json").is_file())
    self.assertTrue(template_root.joinpath("runproof", "adapters", "github-copilot.json").is_file())
    self.assertTrue(template_root.joinpath("docs", "adapters-v0.1.md").is_file())
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_core.py -v
```

Expected: all pass.

- [ ] **Step 8: Grep check — no legacy strings in templates**

```bash
grep -r "ssd-core\|proofkit" runproof/templates/runproof/ | grep -v ".gitkeep"
```

Expected: zero results.

- [ ] **Step 9: Commit**

```bash
git add runproof/templates/ runproof/_wf_templates.py tests/test_core.py
git commit -m "refactor: rename templates/sdd → templates/runproof, update all internal brand strings"
```

---

## Task 5: Rebrand `_wf_infra.py` — git hooks and CI templates

**Files:**
- Modify: `runproof/_wf_infra.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_core.py`:

```python
def test_git_hooks_use_runproof_command(self) -> None:
    from runproof._wf_infra import pre_commit_hook_text, pre_push_hook_text
    from pathlib import Path
    hook = pre_commit_hook_text(Path("/tmp/repo"))
    self.assertIn("runproof guard", hook)
    self.assertNotIn("proofkit", hook)
    push_hook = pre_push_hook_text(Path("/tmp/repo"))
    self.assertIn("runproof guard", push_hook)

def test_ci_templates_use_runproof_command(self) -> None:
    from runproof._wf_infra import _GITHUB_ACTIONS_TEMPLATE, _GITLAB_CI_TEMPLATE
    self.assertIn("runproof-cli", _GITHUB_ACTIONS_TEMPLATE)
    self.assertIn("runproof guard", _GITHUB_ACTIONS_TEMPLATE)
    self.assertNotIn("proofkit", _GITHUB_ACTIONS_TEMPLATE)
    self.assertIn("runproof-cli", _GITLAB_CI_TEMPLATE)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_core.py::TestCore::test_git_hooks_use_runproof_command tests/test_core.py::TestCore::test_ci_templates_use_runproof_command -v
```

Expected: FAIL.

- [ ] **Step 3: Update `_wf_infra.py`**

```python
def pre_commit_hook_text(root: Path) -> str:
    root_arg = root.as_posix()
    command = f"runproof guard --root {shlex.quote(root_arg)} --require-active-change --strict-state"
    return "\n".join(["#!/bin/sh", "# Generated by RunProof. Edit with care.", command, ""])


def pre_push_hook_text(root: Path) -> str:
    root_arg = root.as_posix()
    command = f"runproof guard --root {shlex.quote(root_arg)} --strict-state"
    return "\n".join(["#!/bin/sh", "# Generated by RunProof. Edit with care.", command, ""])
```

Also update `_GITHUB_ACTIONS_TEMPLATE` and `_GITLAB_CI_TEMPLATE` — replace every `proofkit-cli` → `runproof-cli` and `proofkit guard` → `runproof guard`. Update the job name strings from `SDD governance guard` → `RunProof governance guard`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_core.py::TestCore::test_git_hooks_use_runproof_command tests/test_core.py::TestCore::test_ci_templates_use_runproof_command -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add runproof/_wf_infra.py tests/test_core.py
git commit -m "refactor: update git hook and CI template strings to runproof"
```

---

## Task 6: Rebrand `cli.py` — all output strings and parser descriptions

**Files:**
- Modify: `runproof/cli.py`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_help_mentions_runproof(self) -> None:
    import io, contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            sdd.main(["--help"])
    except SystemExit:
        pass
    output = buf.getvalue()
    self.assertIn("runproof", output.lower())
    self.assertNotIn("proofkit", output.lower())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::TestCore::test_cli_help_mentions_runproof -v
```

Expected: FAIL.

- [ ] **Step 3: Update parser descriptions in `build_parser()`**

In `runproof/cli.py`, replace:
- `description="ProofKit utility"` → `description="RunProof utility"`
- All `help=` strings with `proofkit <cmd>` → `runproof <cmd>`
- All `epilog=` example strings: `proofkit` → `runproof`
- `"Which AI agent will you use with ProofKit?"` → `"Which AI agent will you use with RunProof?"`
- Error message `"proofkit requires ..."` references (in main or error handlers)

- [ ] **Step 4: Update `_render.py` output strings**

```bash
grep -n "SDD\|ProofKit\|proofkit\|sdd" runproof/_render.py
```

Replace:
- `"SDD status"` → `"RunProof status"`
- `"SDD log:"` → `"RunProof log:"`
- `"SDD guard passed."` → `"RunProof guard passed."`
- `"SDD guard blocked."` → `"RunProof guard blocked."`
- `"SDD validation passed."` → `"RunProof validation passed."`
- `"proofkit init"` references in prompts → `"runproof init"`

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_core.py::TestCore::test_cli_help_mentions_runproof -v
```

Expected: PASS.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass or only pre-existing failures.

- [ ] **Step 7: Commit**

```bash
git add runproof/cli.py runproof/_render.py tests/test_core.py
git commit -m "refactor: update CLI and render output strings to RunProof brand"
```

---

## Task 7: Update remaining tests for new brand

**Files:**
- Modify: `tests/test_workflow.py`, `tests/test_core.py`, all other `tests/test_*.py`

- [ ] **Step 1: Update `_COMMAND_FILE_NAMES` in test files**

In `tests/test_core.py` and `tests/test_workflow.py`, replace:

```python
_COMMAND_FILE_NAMES = [
    "runproof-next.md",
    "runproof-new.md",
    "runproof-status.md",
    "runproof-verify.md",
    "runproof-constitution.md",
]
```

- [ ] **Step 2: Update `.proofkit` path references in test assertions**

```bash
grep -rn "\.proofkit" tests/
```

Replace all `".proofkit"` → `".runproof"` in test assertion strings like:
```python
# was: self.assertTrue((root / ".proofkit" / "constitution.md").is_file())
self.assertTrue((root / ".runproof" / "constitution.md").is_file())
```

- [ ] **Step 3: Update `import proofkit` → `import runproof`**

```bash
sed -i 's/import proofkit/import runproof/g; s/from proofkit/from runproof/g' tests/*.py
```

- [ ] **Step 4: Update `schema: sdd.artifact.v1` in test string assertions**

```bash
grep -rn "schema: sdd\." tests/
```

Replace `"schema: sdd.artifact.v1"` → `"schema: runproof.artifact.v1"` where referenced in test assertions.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: update all test references from proofkit/sdd to runproof"
```

---

## Task 8: Add `resolution_active_change_id()` and update commands to use it

**Files:**
- Modify: `runproof/_wf_changeops.py`, `runproof/cli.py`, `runproof/_render.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_workflow.py`:

```python
def test_resolve_active_change_id_returns_single_active(self) -> None:
    root = REPO_ROOT / ".tmp-tests" / f"resolve-{uuid.uuid4().hex}"
    with contextlib.redirect_stdout(io.StringIO()):
        sdd.init_project(root)
        sdd.create_change(root, "my-change", "quick", "My change")
    result = sdd.resolve_active_change_id(root)
    self.assertEqual(result, "my-change")
    shutil.rmtree(root, ignore_errors=True)

def test_resolve_active_change_id_returns_none_when_no_changes(self) -> None:
    root = REPO_ROOT / ".tmp-tests" / f"resolve-empty-{uuid.uuid4().hex}"
    with contextlib.redirect_stdout(io.StringIO()):
        sdd.init_project(root)
    result = sdd.resolve_active_change_id(root)
    self.assertIsNone(result)
    shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_workflow.py::TestWorkflow::test_resolve_active_change_id_returns_single_active tests/test_workflow.py::TestWorkflow::test_resolve_active_change_id_returns_none_when_no_changes -v
```

Expected: FAIL — `resolve_active_change_id` not defined.

- [ ] **Step 3: Add `resolve_active_change_id()` to `_wf_changeops.py`**

```python
def resolve_active_change_id(root: Path) -> str | None:
    """Return the single active change_id, or None if zero or multiple active changes exist."""
    dirs = active_change_directories(root)
    if len(dirs) == 1:
        return dirs[0].name
    return None
```

- [ ] **Step 4: Export from `runproof/__init__.py`**

Add `resolve_active_change_id` to the imports list in `__init__.py`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_workflow.py::TestWorkflow::test_resolve_active_change_id_returns_single_active tests/test_workflow.py::TestWorkflow::test_resolve_active_change_id_returns_none_when_no_changes -v
```

Expected: PASS.

- [ ] **Step 6: Wire into `cli.py` — make `change_id` optional on relevant commands**

In `build_parser()`, update `auto`, `verify`, `log`, `evidence`, `pr-check` parsers to make `change_id` optional with `nargs="?"`:

```python
auto_parser.add_argument("change_id", nargs="?", default=None, help="kebab-case change identifier; inferred if only one active change exists")
```

In `main()`, add resolution before each command:

```python
if args.command == "auto":
    root = Path(args.root).resolve()
    change_id = args.change_id or resolve_active_change_id(root)
    if change_id is None:
        print(_red("✗") + " No active changes. Create one with 'runproof new'.")
        return 1
    return print_auto(root, change_id, loop=args.loop, verify_commands=args.verify_with or None)
```

Apply the same pattern to `verify`, `log`, `evidence`, `pr-check`.

- [ ] **Step 7: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add runproof/_wf_changeops.py runproof/cli.py runproof/__init__.py tests/test_workflow.py
git commit -m "feat: add resolve_active_change_id, make change_id optional on all commands"
```

---

## Task 9: Add `runproof status --json`

**Files:**
- Modify: `runproof/cli.py`, `runproof/_render.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_workflow.py`:

```python
def test_status_json_returns_valid_json(self) -> None:
    root = REPO_ROOT / ".tmp-tests" / f"status-json-{uuid.uuid4().hex}"
    with contextlib.redirect_stdout(io.StringIO()):
        sdd.init_project(root)
        sdd.create_change(root, "test-change", "quick", "Test change")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sdd.main(["status", "--json", "--root", str(root)])

    self.assertEqual(rc, 0)
    data = json.loads(buf.getvalue())
    self.assertIn("change_id", data)
    self.assertIn("phase", data)
    self.assertIn("next_action", data)
    self.assertIn("can_auto_advance", data)
    self.assertIn("missing_artifacts", data)
    self.assertEqual(data["change_id"], "test-change")
    shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_workflow.py::TestWorkflow::test_status_json_returns_valid_json -v
```

Expected: FAIL — no `--json` flag.

- [ ] **Step 3: Add `--json` flag to status parser in `cli.py`**

```python
status_parser.add_argument(
    "--json",
    action="store_true",
    default=False,
    help="output status as machine-readable JSON",
)
```

Update the dispatch in `main()`:

```python
if args.command == "status":
    root = Path(args.root).resolve()
    if getattr(args, "json", False):
        return print_status_json(root)
    return print_status(root)
```

- [ ] **Step 4: Add `print_status_json()` to `_render.py`**

```python
def print_status_json(root: Path) -> int:
    import json as _json
    findings, changes = status(root)
    errors = [f for f in findings if f.severity == "error"]

    if not changes:
        data = {
            "change_id": None,
            "phase": None,
            "profile": None,
            "next_action": "No active changes. Create one with 'runproof new'.",
            "missing_artifacts": [],
            "can_auto_advance": False,
        }
        print(_json.dumps(data))
        return 0

    # Report first active change (most common case — single active change)
    change = changes[0]
    from ._wf_inference import workflow_state
    state = workflow_state(root, change.change_id)

    auto_phases = {
        WorkflowPhase.SYNC_SPECS,
        WorkflowPhase.ARCHIVE,
    }
    can_auto = state.phase in auto_phases and not state.is_blocked

    data = {
        "change_id": state.change_id,
        "phase": state.phase.value,
        "profile": state.profile,
        "next_action": state.next_action,
        "missing_artifacts": change.missing,
        "can_auto_advance": can_auto,
    }
    print(_json.dumps(data))
    return 1 if errors else 0
```

- [ ] **Step 5: Export `print_status_json` from `__init__.py`**

Add to imports in `runproof/__init__.py`.

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_workflow.py::TestWorkflow::test_status_json_returns_valid_json -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add runproof/cli.py runproof/_render.py runproof/__init__.py tests/test_workflow.py
git commit -m "feat: add runproof status --json for machine-readable output"
```

---

## Task 10: Add `runproof next` command

**Files:**
- Modify: `runproof/cli.py`, `runproof/_render.py`, `runproof/_wf_changeops.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_workflow.py`:

```python
def test_runproof_next_advances_auto_phases(self) -> None:
    root = REPO_ROOT / ".tmp-tests" / f"next-{uuid.uuid4().hex}"
    change_id = "test-next"
    with contextlib.redirect_stdout(io.StringIO()):
        sdd.init_project(root)
        sdd.create_change(root, change_id, "quick", "Test next")

    # Mark proposal ready so auto can advance
    change_dir = root / ".runproof" / "changes" / change_id
    proposal = change_dir / "proposal.md"
    proposal.write_text(
        proposal.read_text(encoding="utf-8").replace("status: draft", "status: ready"),
        encoding="utf-8",
    )

    with contextlib.redirect_stdout(io.StringIO()):
        rc = sdd.main(["next", "--root", str(root)])

    self.assertEqual(rc, 0)
    shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_workflow.py::TestWorkflow::test_runproof_next_advances_auto_phases -v
```

Expected: FAIL — `next` command not found.

- [ ] **Step 3: Add `next` parser in `cli.py`**

In `build_parser()`:

```python
next_parser = subcommands.add_parser(
    "next",
    help="advance the active change: auto-execute ready steps, stop at phases requiring human input",
    epilog="example:\n  runproof next\n  runproof next add-dark-mode\n  runproof next --verify-with 'pytest -x'",
)
next_parser.add_argument(
    "change_id",
    nargs="?",
    default=None,
    help="kebab-case change identifier; inferred if only one active change exists",
)
next_parser.add_argument(
    "--verify-with",
    action="append",
    default=[],
    metavar="CMD",
    help="verification command to run automatically at the verify phase; may be repeated",
)
next_parser.add_argument(
    "--root",
    default=".",
    help="repository root; defaults to the current directory",
)
```

- [ ] **Step 4: Add dispatch in `main()`**

```python
if args.command == "next":
    root = Path(args.root).resolve()
    change_id = args.change_id or resolve_active_change_id(root)
    if change_id is None:
        print(_red("✗") + " No active changes. Create one with 'runproof new'.")
        return 1
    return print_auto(root, change_id, loop=True, verify_commands=args.verify_with or None)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_workflow.py::TestWorkflow::test_runproof_next_advances_auto_phases -v
```

Expected: PASS.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add runproof/cli.py tests/test_workflow.py
git commit -m "feat: add runproof next command — single-command phase advance"
```

---

## Task 11: Add `constitution` template and memory key support

**Files:**
- Create: `runproof/templates/runproof/memory/constitution.md`
- Modify: `runproof/_wf_templates.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_core.py`:

```python
def test_constitution_memory_key_is_supported(self) -> None:
    root = REPO_ROOT / ".tmp-tests" / f"constitution-{uuid.uuid4().hex}"
    with contextlib.redirect_stdout(io.StringIO()):
        sdd.init_project(root)
    constitution_path = root / ".runproof" / "memory" / "constitution.md"
    self.assertTrue(constitution_path.is_file())
    content = constitution_path.read_text(encoding="utf-8")
    self.assertIn("RunProof Constitution", content)
    shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::TestCore::test_constitution_memory_key_is_supported -v
```

Expected: FAIL — `constitution.md` not written by `init_project`.

- [ ] **Step 3: Create `runproof/templates/runproof/memory/constitution.md`**

```markdown
---
schema: runproof.artifact.v1
artifact: constitution
status: active
---

# RunProof Constitution

## Tech Stack
<!-- Languages, frameworks, runtimes, and key libraries in this project. -->

## Testing Standards
<!-- Required test coverage, test runner, naming conventions, TDD policy. -->

## Code Quality
<!-- Linting rules, formatting standards, forbidden patterns, review requirements. -->

## AI Agent Guidelines
<!-- What agents may and may not do autonomously in this repo. -->
```

- [ ] **Step 4: Ensure `init_project` writes `constitution.md`**

In `runproof/_wf_templates.py`, verify `MEMORY_COPY_FILES` includes `"constitution.md"` (done in Task 2). Confirm `init_project` (in `_workflow.py`) iterates `MEMORY_COPY_FILES` when writing memory files. If not, add:

```python
for filename in MEMORY_COPY_FILES:
    src = tmpl_memory / filename
    dst = memory_dir / filename
    if not dst.exists():
        copy_template_file(src, dst)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_core.py::TestCore::test_constitution_memory_key_is_supported -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add runproof/templates/runproof/memory/constitution.md runproof/_wf_templates.py tests/test_core.py
git commit -m "feat: add constitution memory key and template"
```

---

## Task 12: Fix `_INTEGRATION_COMMAND_DIRS` paths and add Copilot `.prompt.md` support

**Files:**
- Modify: `runproof/_wf_templates.py`

- [ ] **Step 1: Write the failing test**

In `tests/test_core.py`:

```python
def test_install_commands_copilot_uses_correct_path(self) -> None:
    root = REPO_ROOT / ".tmp-tests" / f"cmds-copilot-{uuid.uuid4().hex}"
    root.mkdir(parents=True)
    with contextlib.redirect_stdout(io.StringIO()):
        findings = sdd.install_commands(root, "copilot", "repo")
    self.assertEqual(findings, [])
    prompts_dir = root / ".github" / "prompts"
    self.assertTrue(prompts_dir.is_dir())
    prompt_files = list(prompts_dir.glob("*.prompt.md"))
    self.assertGreater(len(prompt_files), 0)
    shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_core.py::TestCore::test_install_commands_copilot_uses_correct_path -v
```

Expected: FAIL — path wrong, no `.prompt.md` files.

- [ ] **Step 3: Update `_INTEGRATION_COMMAND_DIRS` in `_wf_templates.py`**

```python
_INTEGRATION_COMMAND_DIRS: dict[str, dict[str, str]] = {
    "claude-code": {"repo": ".claude/commands",          "user": ".claude/commands",              "local": ".claude/commands"},
    "copilot":     {"repo": ".github/prompts",           "user": ".github/prompts",               "local": ".github/prompts"},
    "opencode":    {"repo": ".opencode/commands",        "user": ".config/opencode/commands",     "local": ".opencode/commands"},
    "codex":       {"repo": ".codex/commands",           "user": ".codex/commands",               "local": ".codex/commands"},
    "cursor":      {"repo": ".cursor/rules",             "user": ".cursor/rules",                 "local": ".cursor/rules"},
    "gemini-cli":  {"repo": ".gemini/commands",          "user": ".gemini/commands",              "local": ".gemini/commands"},
    "generic":     {"repo": f"{SDD_DIR}/commands",       "user": f"{SDD_DIR}/commands",           "local": f"{SDD_DIR}/commands"},
}
```

- [ ] **Step 4: Update `_COMMAND_FILES` — split by integration format**

Replace the flat `_COMMAND_FILES` list with a dict keyed by integration:

```python
_COMMAND_FILES_BY_INTEGRATION: dict[str, list[str]] = {
    "copilot": [
        "runproof-next.prompt.md",
        "runproof-new.prompt.md",
        "runproof-status.prompt.md",
        "runproof-verify.prompt.md",
        "runproof-constitution.prompt.md",
    ],
    "_default": [
        "runproof-next.md",
        "runproof-new.md",
        "runproof-status.md",
        "runproof-verify.md",
        "runproof-constitution.md",
    ],
}


def command_files_for(integration: str) -> list[str]:
    return _COMMAND_FILES_BY_INTEGRATION.get(integration, _COMMAND_FILES_BY_INTEGRATION["_default"])
```

- [ ] **Step 5: Update `install_commands()` to use the new function**

```python
def install_commands(root, integration, scope="repo", *, _home=None):
    ...
    for filename in command_files_for(integration):
        # For copilot, source from templates/commands/copilot/
        if integration == "copilot":
            src = tmpl / "copilot" / filename
        else:
            src = tmpl / filename
        dst = target_dir / filename
        ...
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_core.py::TestCore::test_install_commands_copilot_uses_correct_path -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add runproof/_wf_templates.py tests/test_core.py
git commit -m "fix: correct install-commands paths and add .prompt.md support for Copilot"
```

---

## Task 13: Create all slash command templates

**Files:**
- Create: `runproof/templates/commands/runproof-next.md`
- Create: `runproof/templates/commands/runproof-new.md`
- Create: `runproof/templates/commands/runproof-status.md`
- Create: `runproof/templates/commands/runproof-verify.md`
- Create: `runproof/templates/commands/runproof-constitution.md`
- Create: `runproof/templates/commands/copilot/runproof-next.prompt.md`
- Create: `runproof/templates/commands/copilot/runproof-new.prompt.md`
- Create: `runproof/templates/commands/copilot/runproof-status.prompt.md`
- Create: `runproof/templates/commands/copilot/runproof-verify.prompt.md`
- Create: `runproof/templates/commands/copilot/runproof-constitution.prompt.md`

- [ ] **Step 1: Create `runproof/templates/commands/runproof-next.md`**

```markdown
Run `runproof status --json` and capture the output.

If `can_auto_advance` is true: run `runproof next` and report the new phase in one line.

If `can_auto_advance` is false:
1. Read `next_action` from the JSON output to identify what artifact needs to be written.
2. Read `.runproof/skills/<current_phase>.md` for phase-specific instructions.
3. Read `.runproof/memory/constitution.md` if it exists for project constraints.
4. Scan the repo for relevant context (recent commits, existing specs, tech stack).
5. Draft the artifact content and write it to `.runproof/changes/<change_id>/<artifact_file>`.
6. Run `runproof ready <change_id>` to mark it ready and advance the phase.
7. Report in one line: what was written and the new phase.
```

- [ ] **Step 2: Create `runproof/templates/commands/runproof-new.md`**

```markdown
Create a new RunProof governed change.

1. Convert the user's intent to a kebab-case `change_id` (e.g., "add dark mode" → "add-dark-mode").
2. Run `runproof new <change_id>`.
3. Read `.runproof/memory/constitution.md` if it exists.
4. Scan the repo for context relevant to the intent (stack, related files, recent changes).
5. Write a tight `proposal.md` in `.runproof/changes/<change_id>/proposal.md`:
   - One-sentence intent
   - Explicit scope (what's in, what's out)
   - How success is measured
   Replace the draft frontmatter `status: draft` with `status: ready`.
6. Run `runproof ready <change_id>`.
7. Report in one line: change_id created and current phase.
```

- [ ] **Step 3: Create `runproof/templates/commands/runproof-status.md`**

```markdown
Run `runproof status --json` and report in this exact format:

<change_id> | <phase> | missing: <missing_artifacts or "none"> | next: /runproof-next

If there are no active changes, report: "No active changes — use /runproof-new to start one."
```

- [ ] **Step 4: Create `runproof/templates/commands/runproof-verify.md`**

```markdown
Verify the active RunProof change.

1. Run `runproof status --json` to get the `change_id`.
2. Run `runproof verify <change_id> --discover` — this auto-detects the test runner, executes it, captures cryptographic evidence, and advances to VERIFY if all tests pass.
3. If `--discover` doesn't find the right command, run `runproof verify <change_id> --command "<test_command>"` instead. Infer the test command from the project stack (package.json scripts, pytest.ini, Makefile).
4. If tests fail: show the failure output and suggest the fix. Do not advance the phase.
5. If tests pass: report in one line — phase advanced + evidence checksum (first 12 chars).
```

- [ ] **Step 5: Create `runproof/templates/commands/runproof-constitution.md`**

```markdown
Create or update the RunProof constitution for this project.

The constitution lives at `.runproof/memory/constitution.md`.

**With arguments** (user provides directives): use them as the basis for each section.

**Without arguments**: infer the constitution by scanning:
- Language and framework (package.json, pyproject.toml, Cargo.toml, go.mod, etc.)
- Test runner and coverage config
- Linting and formatting config (.eslintrc, ruff.toml, .prettierrc, etc.)
- CI configuration (.github/workflows/, .gitlab-ci.yml)
- Existing CLAUDE.md or similar AI guidance files
- Recent commit messages (style and conventions)

Write a constitution with these sections:
- Tech Stack
- Testing Standards
- Code Quality
- AI Agent Guidelines

**If constitution already exists**: show a diff between current and proposed content, then ask the user to confirm before overwriting.

Run `runproof memory show --key constitution` after writing to confirm success.
```

- [ ] **Step 6: Create the Copilot directory and templates**

```bash
mkdir -p runproof/templates/commands/copilot
```

Create `runproof/templates/commands/copilot/runproof-next.prompt.md`:

```markdown
---
mode: agent
description: Advance the active RunProof change — auto-execute or draft missing artifacts
---

Run `runproof status --json` and capture the output.

If `can_auto_advance` is true: run `runproof next` and report the new phase in one line.

If `can_auto_advance` is false:
1. Read `next_action` from the JSON output to identify the missing artifact.
2. Read `.runproof/skills/<current_phase>.md` for phase instructions.
3. Read `.runproof/memory/constitution.md` if it exists.
4. Scan the repo for relevant context.
5. Draft and write the artifact to `.runproof/changes/<change_id>/<artifact_file>`.
6. Run `runproof ready <change_id>`.
7. Report in one line: what was written and the new phase.
```

Create `runproof/templates/commands/copilot/runproof-new.prompt.md`:

```markdown
---
mode: agent
description: Create a new RunProof governed change with a drafted proposal
---

Convert the user's intent to a kebab-case change_id.
Run `runproof new <change_id>`.
Read `.runproof/memory/constitution.md` if it exists.
Scan the repo for context relevant to the intent.
Write a tight proposal.md: one-sentence intent, explicit scope, success criteria.
Set `status: ready` in the frontmatter.
Run `runproof ready <change_id>`.
Report in one line: change_id created and current phase.
```

Create `runproof/templates/commands/copilot/runproof-status.prompt.md`:

```markdown
---
mode: agent
description: Show the active RunProof change status in one line
---

Run `runproof status --json` and report in this format:
<change_id> | <phase> | missing: <missing_artifacts or "none"> | next: /runproof-next

If no active changes: "No active changes — use /runproof-new to start one."
```

Create `runproof/templates/commands/copilot/runproof-verify.prompt.md`:

```markdown
---
mode: agent
description: Verify the active RunProof change — run tests and capture evidence
---

Run `runproof status --json` to get the change_id.
Run `runproof verify <change_id> --discover`.
If --discover fails to find the test command, infer it from the project stack and run `runproof verify <change_id> --command "<cmd>"`.
If tests fail: report the failure and suggest the fix.
If tests pass: report in one line — phase advanced + evidence checksum (first 12 chars).
```

Create `runproof/templates/commands/copilot/runproof-constitution.prompt.md`:

```markdown
---
mode: agent
description: Create or update the RunProof constitution for this project
---

If the user provided directives, use them. Otherwise scan the repo: package.json, pyproject.toml, linting configs, CI files, CLAUDE.md, recent commits.

Write `.runproof/memory/constitution.md` with sections: Tech Stack, Testing Standards, Code Quality, AI Agent Guidelines.

If the file already exists, show a diff and ask for confirmation before overwriting.

Run `runproof memory show --key constitution` to confirm success.
```

- [ ] **Step 7: Write test verifying command files exist**

In `tests/test_core.py`:

```python
def test_command_template_files_exist(self) -> None:
    from runproof._wf_templates import template_commands_root
    tmpl = template_commands_root()
    for filename in ["runproof-next.md", "runproof-new.md", "runproof-status.md",
                     "runproof-verify.md", "runproof-constitution.md"]:
        self.assertTrue(tmpl.joinpath(filename).is_file(), f"Missing: {filename}")
    for filename in ["runproof-next.prompt.md", "runproof-new.prompt.md",
                     "runproof-status.prompt.md", "runproof-verify.prompt.md",
                     "runproof-constitution.prompt.md"]:
        self.assertTrue(tmpl.joinpath("copilot", filename).is_file(), f"Missing copilot: {filename}")
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_core.py::TestCore::test_command_template_files_exist -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add runproof/templates/commands/ tests/test_core.py
git commit -m "feat: add RunProof slash command templates for Claude Code and Copilot"
```

---

## Task 14: Final grep audit and full test run

**Files:**
- Verify: all files

- [ ] **Step 1: Grep for legacy brand strings in package source**

```bash
grep -rn "ssd-core\|proofkit\|\"sdd\." runproof/ --include="*.py" --include="*.json" --include="*.md" --include="*.js" --include="*.toml"
```

For any remaining match: fix it.

- [ ] **Step 2: Grep for legacy strings in templates**

```bash
grep -rn "ssd-core\|proofkit" runproof/templates/ | grep -v ".gitkeep"
```

Expected: zero results.

- [ ] **Step 3: Verify `.runproof` path used everywhere in source**

```bash
grep -rn '".proofkit"' runproof/ --include="*.py"
```

Expected: zero results.

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Smoke test the CLI end-to-end**

```bash
pip install -e .
runproof version
runproof --help
runproof next --help
runproof status --json --root .
```

Expected: `runproof` binary works, `next` and `status --json` appear in help.

- [ ] **Step 6: Verify npm wrapper**

```bash
node bin/runproof.js version
```

Expected: same version as Python CLI.

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: RunProof rebranding complete — all brand strings updated"
```
