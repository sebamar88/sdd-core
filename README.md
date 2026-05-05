# SSD-Core

Governance anti-hallucination for AI-assisted software teams.

SSD-Core turns agent work into a governed development trail: intent, specs, design, tasks, verification, critique, and archive. The point is simple: agents can move fast, but production code needs evidence.

```text
Idea -> Spec -> Design -> Tasks -> Verified Change -> Living Specs -> Archive
```

Use SSD-Core when you want AI-generated work to be reviewable, repeatable, and hard to fake.

## Why It Exists

AI coding agents are excellent at producing code. They are much weaker at preserving intent, proving behavior, and remembering why a decision was made after the chat scrolls away.

SSD-Core gives teams a repository-native control layer:

- the agent must write down the change before implementing it
- tasks must map back to specs
- verification evidence must exist before archive
- living specs are updated after behavior changes
- adapter-specific runtime details stay outside the protocol core

This is not a bigger prompt. It is a small governance system for agentic development.

## What You Get Immediately

After install, any repository can get:

- `.sdd/` protocol artifacts for specs, changes, profiles, adapters, agents, and skills
- a CLI that initializes, validates, opens, checks, syncs, and archives SDD changes
- concrete adapter manifests for Codex, Claude Code, Gemini CLI, OpenCode, and Qwen Code
- six rigor profiles: `quick`, `standard`, `bugfix`, `refactor`, `enterprise`, and `research`
- a release gate that runs on Windows, Linux, and macOS

No agent lock-in. No operating-system lock-in. No hidden state as the source of truth.

## Golden Path: Guard A Login Change

This is the “I need this to work today” path.

### 1) Install

Published npm path:

```text
npm install -g ssd-core
```

One-shot npm path:

```text
npx -y ssd-core@latest version
```

Source checkout path:

```text
uv tool install .
```

or:

```text
npm install -g .
```

The npm package delegates to the same Python core and requires Python 3.11+ on `PATH`.

### 2) Initialize Your Repository

```text
ssd-core init --root my-app
ssd-core validate --root my-app
```

Result:

```text
my-app/.sdd/
  adapters/
  agents/
  changes/
  profiles/
  schemas/
  skills/
  specs/
```

### 3) Run A Governed Change

```text
ssd-core run harden-login-rate-limit --profile standard --title "Harden login rate limits" --root my-app
```

Result:

```text
my-app/.sdd/changes/harden-login-rate-limit/
  proposal.md
  delta-spec.md
  design.md
  tasks.md
  verification.md
  archive.md
```

The `run` command is the binding layer: it creates the change if needed, reads the artifact state, names the current phase, and tells the agent or human the next allowed action.

### 4) Give The Agent A Real Contract

Instead of “fix login security”, point the agent at the change folder:

```text
Run `ssd-core run harden-login-rate-limit --root .` before each handoff.
Follow the phase it reports.
Do not archive until `ssd-core run` reports `sync-specs` or `archive`.
```

The agent now has a repository contract, not just a chat instruction.

### 5) Block Fake Completion

```text
ssd-core check harden-login-rate-limit --root my-app
```

If tasks are incomplete or verification is missing, the change cannot close cleanly.

### 6) Sync And Archive

```text
ssd-core sync-specs harden-login-rate-limit --root my-app
ssd-core archive harden-login-rate-limit --root my-app
ssd-core validate --root my-app
```

Outcome: the code change, specs, verification evidence, and archive record all stay in the repo.

## Why SSD-Core Instead Of Another SDD Template

SSD-Core is optimized for governance over convenience.

| Need | SSD-Core position |
| --- | --- |
| Avoid hallucinated completion | Verification evidence is a first-class artifact. |
| Keep agents interchangeable | Runtime behavior belongs in adapters, not the core. |
| Support teams and audits | Decisions, specs, and archive records live in git. |
| Scale rigor by risk | Profiles define how much ceremony a change needs. |
| Stay portable | The protocol avoids OS, shell, IDE, and agent assumptions. |

Use SSD-Core when correctness and traceability matter more than a flashy one-command demo.

## Real Orchestrator API

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

blocked = workflow.sync_specs("harden-login-rate-limit")
if not blocked.ok:
    print(blocked.failures[0].kind.value)
    print(blocked.failures[0].message)
```

`SDDWorkflow.sync_specs()` and `SDDWorkflow.archive()` refuse to run unless the current phase permits them. That is the difference between SSD helpers and SSD enforcement.

## When To Use It

Use SSD-Core for:

- teams shipping agent-assisted code to production
- multi-agent workflows that need shared ground truth
- risky changes where “the agent said it passed” is not enough
- projects that need auditable specs and verification history
- orgs evaluating multiple coding agents without rewriting workflow rules

Do not use SSD-Core for:

- throwaway prototypes
- solo scripts where chat history is enough
- teams that do not want specs, tasks, or verification gates
- projects looking for an agent runtime instead of a protocol layer

## Team Path

If you are adopting SSD-Core across a team, focus on these in order:

1. Read the protocol baseline: [docs/sdd-core-protocol-v0.1.md](docs/sdd-core-protocol-v0.1.md)
2. Align adapter boundaries: [docs/adapter-contract-v0.1.md](docs/adapter-contract-v0.1.md)
3. Pick default profiles for change types
4. Require `ssd-core check` before merge or archive
5. Run `python scripts/release_check.py` in CI for SSD-Core itself

## Command Guide

```text
ssd-core version
ssd-core init --root <path>
ssd-core validate --root <path>
ssd-core status --root <path>
ssd-core new <change-id> --profile <profile> --title "Human intent" --root <path>
ssd-core run <change-id> --profile <profile> --title "Human intent" --root <path>
ssd-core check <change-id> --root <path>
ssd-core sync-specs <change-id> --root <path>
ssd-core archive <change-id> --root <path>
```

## Repository Contract

```text
.sdd/
  adapters/      agent/runtime capability manifests
  agents/        portable role contracts
  archive/       completed change records
  changes/       active governed changes
  profiles/      rigor levels by change type
  schemas/       metadata and evidence schemas
  skills/        portable workflow capabilities
  specs/         living behavior specs
```

Core rule: no archive without verification evidence.

## Profiles

SSD-Core ships six profiles:

- `quick`: low-risk, obvious implementation path
- `standard`: default feature/change flow
- `bugfix`: regression-first repair flow
- `refactor`: behavior lock before cleanup
- `enterprise`: higher governance and approval weight
- `research`: evidence-first investigation flow

Use the smallest safe profile for the change type.

## Adapters

The generic baseline is:

- `.sdd/adapters/generic-markdown.json`

Concrete capability manifests included in v0.1:

- Codex: `.sdd/adapters/codex.json`
- Claude Code: `.sdd/adapters/claude-code.json`
- Gemini CLI: `.sdd/adapters/gemini-cli.json`
- OpenCode: `.sdd/adapters/opencode.json`
- Qwen Code: `.sdd/adapters/qwen-code.json`

v0.1 includes manifests, not executable runtime wrappers.

See [docs/adapters-v0.1.md](docs/adapters-v0.1.md) and [docs/adapter-authoring-v0.1.md](docs/adapter-authoring-v0.1.md).

## Principles

- DRY: avoid duplicated logic, contracts, and workflow decisions
- KISS: choose the simplest design that preserves correctness
- YAGNI: do not ship speculative mechanisms
- SOLID: prefer focused modules and stable boundaries
- GRASP: place responsibilities where knowledge already lives
- LoD: minimize coupling to immediate collaborators

SSD-Core specifics:

- keep the core small
- push runtime specifics into adapters
- prefer files over chat memory
- prefer evidence over confidence
- never archive incomplete work quietly

## Production Readiness

For v0.1, readiness means the project can:

- install as wheel and npm wrapper
- initialize from packaged templates
- validate artifacts consistently
- run cross-platform CI checks

Run the full release gate locally:

```text
python scripts/release_check.py
```

See:

- [docs/production-readiness-v0.1.md](docs/production-readiness-v0.1.md)
- [docs/superpowers/plans/2026-05-03-v0.1-closure-week.md](docs/superpowers/plans/2026-05-03-v0.1-closure-week.md)
- [docs/superpowers/plans/2026-05-03-v0.1-closure-record.md](docs/superpowers/plans/2026-05-03-v0.1-closure-record.md)

## Current Status

Current release: `v0.1.5`

Solid in v0.1:

- protocol, constitution, profiles, schemas
- concrete adapter manifests for major runtimes
- dependency-free reference CLI
- packaged templates and docs
- cross-platform release check and CI
- npm package published as `ssd-core`
- workflow binding through `ssd-core run`
- importable strict orchestrator through `SDDWorkflow`

Deferred to future versions:

- deeper artifact JSON Schema validation
- semantic living spec merge
- executable runtime command wrappers for adapters
- richer profile templates
- a full demo repository with real application code

## Influences And Attribution

SSD-Core is original work, informed by MIT-licensed workflow ideas from:

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite)
- [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)

Attribution and compatibility notes are in [NOTICE.md](NOTICE.md).

## License

SSD-Core is released under the [MIT License](LICENSE).
