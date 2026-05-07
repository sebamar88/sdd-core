# SDD-Core

> **Make AI prove it works.**

SDD-Core is a verification engine for AI-driven development.

It prevents agents from claiming work is complete without real execution evidence.

If a command didn’t run — or failed — the system blocks progress.

---

## 🚫 The problem

AI says:

> "Done"

Reality:

```bash
npm test
# FAIL
```

---

## ✅ With SDD-Core

```bash
ssd-core verify --require-execution-evidence
```

**Result:**

```text
BLOCKED: command failed (exit_code=1)
```

The system forces real execution before accepting completion.

---

## Why It Exists

AI coding agents are excellent at producing code. They are much weaker at:

- remembering *why* a decision was made after the chat scrolls away
- proving that tests ran, rather than saying they did
- keeping specs in sync when behavior changes

SSD-Core turns "the agent said it passed" into structured, checksummed evidence stored in your repository. No lock-in. No operating-system lock-in. The workflow state is explicit, versioned, and repository-native in `.sdd/state.json`.

---

## Try It Now (30 seconds, no setup)

Runs the full Golden Path in a temp directory and cleans up after itself:

```text
npx -y ssd-core@latest demo
```

What you will see:

```text
── Step 1/7: ssd-core init
   ✓ Initialized .sdd/ (adapters, agents, profiles, schemas, skills, specs)
── Step 2/7: ssd-core new demo-harden-login --profile quick
   ✓ Created .sdd/changes/demo-harden-login/ (proposal.md, tasks.md, verification.md)
   ✓ Phase automatically recorded → propose
── Step 3/7: Agent fills proposal.md → status: ready
── Step 4/7: Agent closes tasks.md → status: ready
── Step 5/7: ssd-core transition demo-harden-login task
   ✓ Phase recorded in .sdd/state.json → task
── Step 6/7: ssd-core verify --command 'echo all-tests-pass'
   ✓ Command executed; output checksummed → .sdd/evidence/
   ✓ verification.md updated automatically → status: verified
── Step 7/7: ssd-core transition archive  &&  ssd-core archive
   ✓ Change closed → .sdd/archive/2026-05-05-demo-harden-login/
── ssd-core validate
   ✓ Repository governance passed — zero errors
```

---

## Install

```text
npm install -g ssd-core
```

Or one-shot:

```text
npx -y ssd-core@latest version
```

Or from source (requires Python 3.11+):

```text
uv tool install .
```

---

## Golden Path: Guard A Real Change

### 1) Initialize your repository

```text
ssd-core init --root my-app
ssd-core validate --root my-app
```

### 2) Open a governed change

```text
ssd-core run harden-login-rate-limit --profile standard --title "Harden login rate limits" --root my-app
```

Result: `.sdd/changes/harden-login-rate-limit/` with six artifacts — `proposal.md`, `delta-spec.md`, `design.md`, `tasks.md`, `verification.md`, `archive.md`.

`run` creates the change if needed, reads the artifact state, names the current phase, and tells the agent the next allowed action.

### 3) Give the agent a repository contract

Instead of "fix login security", point the agent at the change folder:

```text
Run `ssd-core run harden-login-rate-limit --root .` before each handoff.
Follow the phase it reports.
After each completed artifact phase, record it with `ssd-core transition`.
Do not archive until `ssd-core run` reports `sync-specs` or `archive`.
```

The agent now has a repository contract, not just a chat instruction.

### 4) Block fake completion

```text
ssd-core check harden-login-rate-limit --root my-app
```

Open tasks or missing evidence will surface here. The change cannot close cleanly.

### 5) Record state, verify, sync, and archive

```text
ssd-core transition harden-login-rate-limit specify --root my-app
ssd-core transition harden-login-rate-limit design --root my-app
ssd-core transition harden-login-rate-limit task --root my-app
ssd-core verify harden-login-rate-limit --command "pytest -q" --root my-app
ssd-core transition harden-login-rate-limit archive-record --root my-app
ssd-core transition harden-login-rate-limit sync-specs --root my-app
ssd-core sync-specs harden-login-rate-limit --root my-app
ssd-core archive harden-login-rate-limit --root my-app
ssd-core validate --root my-app
```

Outcome: the code change, specs, executed verification evidence, state transitions, checksums, and archive record all stay in the repo.

---

## Orchestrator API (Python)

The CLI is not the only binding layer. The Python core exposes a strict workflow object for tools, adapters, and IDE integrations:

```python
from ssd_core import SDDWorkflow, WorkflowPhase

workflow = SDDWorkflow("my-app")

result = workflow.run(
    "harden-login-rate-limit",
    profile="standard",
    title="Harden login rate limits",
)

if result.state.phase == WorkflowPhase.PROPOSE:
    print(result.state.next_action)

transitioned = workflow.transition("harden-login-rate-limit", WorkflowPhase.SPECIFY)
verified = workflow.verify(
    "harden-login-rate-limit",
    commands=["pytest -q"],
    require_command=True,
)
```

`transition()`, `verify()`, `sync_specs()`, and `archive()` refuse invalid phase order. `verify` executes commands and stores reproducible logs under `.sdd/evidence/` with SHA-256 checksums. That is the difference between SDD helpers and SDD enforcement.

---

## WorkflowEngine — Agent Execution Loop

`WorkflowEngine.next_step()` gives agent integrations everything they need in a single call — no N+1 lookups:

```python
from ssd_core import WorkflowEngine

engine = WorkflowEngine("my-repo")
step = engine.next_step("harden-login-rate-limit")

# EngineStep(
#   phase=WorkflowPhase.TASK,
#   next_action="Complete tasks.md, close all task checkboxes, and set status to ready.",
#   suggested_command="ssd-core transition harden-login-rate-limit task",
#   allowed_commands=[],
#   blocking_findings=[],
# )

# Agent-driven loop:
while not step.is_complete and not step.is_blocked:
    agent_do_work(step.next_action)
    run_command(step.suggested_command)
    step = engine.next_step("harden-login-rate-limit")
```

`engine.guard(change_id, "archive")` checks the phase gate only. `engine.execute(change_id, "archive")` checks the gate and executes. `engine.allowed_commands(change_id)` returns the gated commands that would pass right now.

---

## Hard Enforcement

SSD-Core can enforce governance at git/CI boundaries:

```text
ssd-core guard --root my-app --require-active-change --strict-state
ssd-core guard --root my-app --require-execution-evidence
ssd-core install-hooks --root my-app
```

`guard` fails when:

- the repository foundation is invalid
- a workflow is blocked
- an archived delta was not synced into living specs
- the policy requires an active `.sdd/changes/*` record and none exists
- strict state finds stale artifact checksums
- execution evidence is required but missing

`install-hooks` writes a pre-commit hook that runs:

```text
ssd-core guard --require-active-change --strict-state
```

That makes ungoverned commits fail locally. CI can run the same `guard` command server-side.

---

## Reference

### Command Guide

```text
ssd-core version
ssd-core demo
ssd-core init --root <path>
ssd-core validate --root <path>
ssd-core status --root <path>
ssd-core new <change-id> --profile <profile> --title "Human intent" --root <path>
ssd-core run <change-id> --profile <profile> --title "Human intent" --root <path>
ssd-core transition <change-id> <phase> --root <path>
ssd-core verify <change-id> --command "pytest -q" --root <path>
ssd-core guard --require-active-change --strict-state --root <path>
ssd-core install-hooks --root <path>
ssd-core check <change-id> --root <path>
ssd-core sync-specs <change-id> --root <path>
ssd-core archive <change-id> --root <path>
ssd-core phase <change-id> --root <path>
ssd-core log <change-id> --root <path>
```

Add `--trace` to any command for component-level diagnostic output:

```text
ssd-core --trace transition my-change specify --root .
# [TRACE] REGISTRY     → transition my-change → specify
# [TRACE] REGISTRY     → require_phase my-change expected=propose
# [TRACE] INFERENCE    → workflow_state my-change
```

---

## Current Status

Current release: `v0.23.0`

Production-ready:

- contract-tested modular architecture
- execution-verified workflows with checksummed evidence
- strict guard enforcement for CI and git hooks
- `--trace` mode for component-level debugging
- Golden Path demo and CLI tooling

---

## Influences And Attribution

SSD-Core is original work, informed by MIT-licensed workflow ideas from:

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite)
- [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)

Attribution and compatibility notes are in [NOTICE.md](NOTICE.md).

## License

SSD-Core is released under the [MIT License](LICENSE).
