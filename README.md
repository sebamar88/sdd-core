# ProofKit

> **Make AI prove it works.**

ProofKit is a verification engine for AI-driven development.

It prevents agents from claiming work is complete without real execution evidence.

If a command didn’t run — or failed — the system blocks progress.

---

## Why not existing SDD frameworks?

| Feature                          | SDD-Core / ProofKit | Spec-Kit | OpenSpec | BMAD | Agent Teams |
|----------------------------------|--------------------|----------|----------|------|-------------|
| Spec-driven workflow             | ✅                 | ✅       | ✅       | ✅   | ⚠️ Partial  |
| Structured artifacts             | ✅                 | ✅       | ✅       | ✅   | ⚠️ Partial  |
| Persistent state (on disk)       | ✅                 | ❌       | ⚠️ Partial | ⚠️ Partial | ❌          |
| Execution verification           | ✅                 | ❌       | ❌       | ❌   | ❌          |
| Blocks fake completion           | ✅                 | ❌       | ❌       | ❌   | ❌          |
| Command execution evidence       | ✅                 | ❌       | ❌       | ❌   | ❌          |
| Checksum validation              | ✅                 | ❌       | ❌       | ❌   | ❌          |
| Enforced workflow transitions    | ✅                 | ⚠️ Soft  | ⚠️ Soft  | ⚠️ Soft | ❌          |
| CI / Git hook enforcement        | ✅                 | ❌       | ❌       | ❌   | ❌          |
| Anti-hallucination guarantees    | ✅                 | ❌       | ❌       | ❌   | ❌          |

> ⚠️ Partial = supported conceptually but not enforced or persisted

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

## ✅ With ProofKit

```bash
proofkit verify --require-execution-evidence
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

ProofKit turns "the agent said it passed" into structured, checksummed evidence stored in your repository. No lock-in. No operating-system lock-in. The workflow state is explicit, versioned, and repository-native in `.sdd/state.json`.

---

## Try It Now (30 seconds, no setup)

Runs the full Golden Path in a temp directory and cleans up after itself:

```text
npx -y proofkit@latest demo
```

What you will see:

```text
── Step 1/7: proofkit init
   ✓ Initialized .sdd/ (adapters, agents, profiles, schemas, skills, specs)
── Step 2/7: proofkit new demo-harden-login --profile quick
   ✓ Created .sdd/changes/demo-harden-login/ (proposal.md, tasks.md, verification.md)
   ✓ Phase automatically recorded → propose
── Step 3/7: Agent fills proposal.md → status: ready
── Step 4/7: Agent closes tasks.md → status: ready
── Step 5/7: proofkit transition demo-harden-login task
   ✓ Phase recorded in .sdd/state.json → task
── Step 6/7: proofkit verify --command 'echo all-tests-pass'
   ✓ Command executed; output checksummed → .sdd/evidence/
   ✓ verification.md updated automatically → status: verified
── Step 7/7: proofkit transition archive  &&  proofkit archive
   ✓ Change closed → .sdd/archive/2026-05-05-demo-harden-login/
── proofkit validate
   ✓ Repository governance passed — zero errors
```

---

## Install

```text
uv tool install proofkit-cli
```

Or with `pipx`:

```text
pipx install proofkit-cli
```

Or via the Node wrapper:

```text
npm install -g proofkit
```

Or one-shot:

```text
npx -y proofkit@latest version
```

Or from source (requires Python 3.11+):

```text
uv tool install proofkit-cli --from git+https://github.com/sebamar88/ProofKit.git
```

---

## User Guide

Detailed bilingual user guides live in Notion:

- [ProofKit User Guide](https://www.notion.so/ProofKit-User-Guide-3593bc50b138807f9b5dec77aaea32aa?source=copy_link)

The guide includes:

- `Quick Start for Engineers`
- `Team Workflow Guide`
- `Production Rollout Guide`

Each guide is split into `EN` and `ES` subpages.

---

## Golden Path: Guard A Real Change

### 1) Initialize your repository

```text
proofkit init --root my-app
proofkit validate --root my-app
```

### 2) Open a governed change

```text
proofkit run harden-login-rate-limit --profile standard --title "Harden login rate limits" --root my-app
```

Result: `.sdd/changes/harden-login-rate-limit/` with six artifacts — `proposal.md`, `delta-spec.md`, `design.md`, `tasks.md`, `verification.md`, `archive.md`.

`run` creates the change if needed, reads the artifact state, names the current phase, and tells the agent the next allowed action.

### 3) Give the agent a repository contract

Instead of "fix login security", point the agent at the change folder:

```text
Run `proofkit run harden-login-rate-limit --root .` before each handoff.
Follow the phase it reports.
After each completed artifact phase, record it with `proofkit transition`.
Do not archive until `proofkit run` reports `sync-specs` or `archive`.
```

The agent now has a repository contract, not just a chat instruction.

### 4) Block fake completion

```text
proofkit check harden-login-rate-limit --root my-app
```

Open tasks or missing evidence will surface here. The change cannot close cleanly.

### 5) Record state, verify, sync, and archive

```text
proofkit transition harden-login-rate-limit specify --root my-app
proofkit transition harden-login-rate-limit design --root my-app
proofkit transition harden-login-rate-limit task --root my-app
proofkit verify harden-login-rate-limit --command "pytest -q" --root my-app
proofkit transition harden-login-rate-limit archive-record --root my-app
proofkit transition harden-login-rate-limit sync-specs --root my-app
proofkit sync-specs harden-login-rate-limit --root my-app
proofkit archive harden-login-rate-limit --root my-app
proofkit validate --root my-app
```

Outcome: the code change, specs, executed verification evidence, state transitions, checksums, and archive record all stay in the repo.

---

## Orchestrator API (Python)

The CLI is not the only binding layer. The Python core exposes a strict workflow object for tools, adapters, and IDE integrations:

```python
from proofkit import SDDWorkflow, WorkflowPhase

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
from proofkit import WorkflowEngine

engine = WorkflowEngine("my-repo")
step = engine.next_step("harden-login-rate-limit")

# EngineStep(
#   phase=WorkflowPhase.TASK,
#   next_action="Complete tasks.md, close all task checkboxes, and set status to ready.",
#   suggested_command="proofkit transition harden-login-rate-limit task",
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

ProofKit can enforce governance at git/CI boundaries:

```text
proofkit guard --root my-app --require-active-change --strict-state
proofkit guard --root my-app --require-execution-evidence
proofkit install-hooks --root my-app
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
proofkit guard --require-active-change --strict-state
```

That makes ungoverned commits fail locally. CI can run the same `guard` command server-side.

---

## Reference

### Command Guide

```text
proofkit version
proofkit demo
proofkit init --root <path>
proofkit validate --root <path>
proofkit status --root <path>
proofkit new <change-id> --profile <profile> --title "Human intent" --root <path>
proofkit run <change-id> --profile <profile> --title "Human intent" --root <path>
proofkit transition <change-id> <phase> --root <path>
proofkit verify <change-id> --command "pytest -q" --root <path>
proofkit guard --require-active-change --strict-state --root <path>
proofkit install-hooks --root <path>
proofkit check <change-id> --root <path>
proofkit sync-specs <change-id> --root <path>
proofkit archive <change-id> --root <path>
proofkit phase <change-id> --root <path>
proofkit log <change-id> --root <path>
```

Add `--trace` to any command for component-level diagnostic output:

```text
proofkit --trace transition my-change specify --root .
# [TRACE] REGISTRY     → transition my-change → specify
# [TRACE] REGISTRY     → require_phase my-change expected=propose
# [TRACE] INFERENCE    → workflow_state my-change
```

---

## Current Status

Current release: `v0.25.0`

Production-ready:

- contract-tested modular architecture
- execution-verified workflows with checksummed evidence
- strict guard enforcement for CI and git hooks
- `--trace` mode for component-level debugging
- Golden Path demo and CLI tooling

---

## Influences And Attribution

ProofKit is original work, informed by MIT-licensed workflow ideas from:

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite)
- [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)

Attribution and compatibility notes are in [NOTICE.md](NOTICE.md).

## License

ProofKit is released under the [MIT License](LICENSE).
