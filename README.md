# SSD-Core

**Governance layer for AI-driven development.**

SSD-Core prevents the two worst failure modes of agent-assisted coding:

- **Hallucinated completion** — "the agent said it passed" with no evidence
- **Vanishing intent** — decisions and specs disappear when the chat scrolls away

It does this by inserting a protocol between the agent and the repository. The agent must write down the change before implementing it, must close all tasks before verifying, and must produce real checksummed evidence before archiving. The protocol is file-based, version-controlled, and agent-agnostic.

```text
Idea → Spec → Design → Tasks → Verified Change → Living Specs → Archive
```

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

## When To Use It

Use SSD-Core for:

- teams shipping agent-assisted code to production
- multi-agent workflows that need shared ground truth
- risky changes where "the agent said it passed" is not enough
- projects that need auditable specs and verification history
- orgs evaluating multiple coding agents without rewriting workflow rules

Do not use SSD-Core for:

- throwaway prototypes
- solo scripts where chat history is enough
- teams that do not want specs, tasks, or verification gates
- projects looking for an agent runtime instead of a protocol layer

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

### Repository Contract

```text
.sdd/
  adapters/      agent/runtime capability manifests
  agents/        portable role contracts
  archive/       completed change records
  changes/       active governed changes
  evidence/      command execution logs and checksums
  profiles/      rigor levels by change type
  schemas/       metadata and evidence schemas
  skills/        portable workflow capabilities
  specs/         living behavior specs
  state.json     declared workflow phases and artifact checksums
```

Core rule: no archive without verification evidence.

### Profiles

SSD-Core ships six profiles:

- `quick`: low-risk, obvious implementation path
- `standard`: default feature/change flow
- `bugfix`: regression-first repair flow
- `refactor`: behavior lock before cleanup
- `enterprise`: higher governance and approval weight
- `research`: evidence-first investigation flow

Use the smallest safe profile for the change type.

### Adapters

The generic baseline is `.sdd/adapters/generic-markdown.json`.

Concrete capability manifests included in v0.1:

- Claude Code: `.sdd/adapters/claude-code.json`
- Codex: `.sdd/adapters/codex.json`
- Cursor: `.sdd/adapters/cursor.json`
- Gemini CLI: `.sdd/adapters/gemini-cli.json`
- GitHub Copilot: `.sdd/adapters/github-copilot.json`
- OpenCode: `.sdd/adapters/opencode.json`
- Qwen Code: `.sdd/adapters/qwen-code.json`

See [docs/adapters-v0.1.md](docs/adapters-v0.1.md) and [docs/adapter-authoring-v0.1.md](docs/adapter-authoring-v0.1.md).

### Principles

- DRY: avoid duplicated logic, contracts, and workflow decisions
- KISS: choose the simplest design that preserves correctness
- YAGNI: do not ship speculative mechanisms
- SOLID: prefer focused modules and stable boundaries

SSD-Core specifics:

- keep the core small
- push runtime specifics into adapters
- prefer files over chat memory
- prefer evidence over confidence
- never archive incomplete work quietly

### Team Path

1. Read the protocol baseline: [docs/sdd-core-protocol-v0.1.md](docs/sdd-core-protocol-v0.1.md)
2. Align adapter boundaries: [docs/adapter-contract-v0.1.md](docs/adapter-contract-v0.1.md)
3. Pick default profiles for change types
4. Require `ssd-core check` before merge or archive
5. Run `python scripts/release_check.py` in CI for SSD-Core itself

### Production Readiness

Run the full release gate locally:

```text
python scripts/release_check.py
```

See:

- [docs/production-readiness-v0.1.md](docs/production-readiness-v0.1.md)
- [docs/superpowers/plans/2026-05-03-v0.1-closure-week.md](docs/superpowers/plans/2026-05-03-v0.1-closure-week.md)

---

## Current Status

Current release: `v0.23.0`

Production-ready:

- protocol, constitution, profiles, schemas
- concrete adapter manifests for major runtimes (Codex, Claude Code, Gemini CLI, OpenCode, Qwen Code)
- dependency-free reference CLI
- packaged templates and docs
- cross-platform release check and CI
- npm package published as `ssd-core`
- workflow binding through `ssd-core run`
- importable strict orchestrator through `SDDWorkflow`
- agent execution loop through `WorkflowEngine.next_step()` → `EngineStep`
- hard enforcement through `ssd-core guard` and git pre-commit hooks
- explicit `.sdd/state.json` registry with validated phase transitions and artifact checksums
- executable verification evidence through `ssd-core verify --command`
- annotated Golden Path demo through `ssd-core demo`
- `--trace` mode for component-level debugging (`ENGINE → REGISTRY → EVIDENCE → INFERENCE`)
- 133 tests including 10 cross-module contract tests
- modular architecture: no module > 500 lines

Deferred to future versions:

- deeper artifact JSON Schema validation
- semantic living spec merge
- executable runtime command wrappers for adapters
- richer profile templates
- a full demo repository with real application code

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
