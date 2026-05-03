# SSD-Core

**Spec-driven development for any agent, on any operating system.**

SSD-Core is a portable SDD framework for teams that want AI coding agents to build from durable specifications instead of fragile chat history.

It gives you a small protocol, a repository-native artifact layout, profile-driven workflows, and dependency-free reference tooling. Use it with Codex, Claude Code, Cursor, OpenCode, Copilot, Kiro, a local script, or an agent you have not invented yet. The protocol does not care. Your specs remain plain Markdown in your repo.

```text
Intent -> Spec -> Design -> Tasks -> Verification -> Archive
```

No lock-in. No hidden state. No tool-specific magic as the source of truth.

## Why This Exists

AI agents are fast, but speed without shared intent creates drift:

- requirements live in a chat window
- implementation starts before behavior is agreed
- tests prove the code runs, not that the right thing was built
- handoffs lose context
- each agent reinvents process from scratch

SSD-Core fixes the workflow layer. It makes the repository carry the intent, evidence, and lifecycle.

## What You Get Today

```text
.sdd/
  agents/
  constitution.md
  protocol.md
  profiles/
  schemas/
  skills/
  specs/
  changes/
  archive/

docs/
  sdd-core-protocol-v0.1.md
  adapter-contract-v0.1.md
  sdd-validator-v0.1.md

scripts/
  sdd.py
```

The current reference utility supports:

```text
python scripts/sdd.py validate
python scripts/sdd.py status
python scripts/sdd.py new <change-id> --profile <profile> --title "Human intent"
python scripts/sdd.py check <change-id>
python scripts/sdd.py archive <change-id>
python scripts/sdd.py sync-specs <change-id>
```

## Core Ideas

### Markdown First

Every important artifact is readable, editable Markdown. Machines can validate it, but humans can still understand it without a dashboard.

### Agent Agnostic

The protocol defines artifacts and lifecycle contracts. Adapters decide how to integrate with a concrete agent or IDE.

### Operating System Agnostic

Protocol paths are logical repository paths. Adapters translate paths, commands, permissions, and process execution to the host platform.

### Profile Driven

Not every change needs enterprise ceremony. SSD-Core ships profiles for:

- `quick`
- `standard`
- `bugfix`
- `refactor`
- `enterprise`
- `research`

### Evidence Gated

A checked task is not proof. Verification artifacts must record what was checked, how it was checked, the outcome, and known gaps.

## Quick Start

Validate the SDD foundation:

```text
python scripts/sdd.py validate
```

Create a change:

```text
python scripts/sdd.py new add-search --profile standard --title "Add search"
```

Inspect current state:

```text
python scripts/sdd.py status
```

Check whether the change is ready to archive:

```text
python scripts/sdd.py check add-search
```

Archive only after verification is complete:

```text
python scripts/sdd.py archive add-search
```

Sync a verified delta into living specs:

```text
python scripts/sdd.py sync-specs add-search
```

## The Lifecycle

```text
explore -> propose -> specify -> design -> task -> implement -> verify -> critique -> archive
```

Profiles can compress or expand that lifecycle. The core rule stays the same: a change needs clear intent, traceable tasks, and verification evidence before it closes.

## Example Change Layout

```text
.sdd/changes/add-search/
  proposal.md
  delta-spec.md
  design.md
  tasks.md
  verification.md
  archive.md
```

Each artifact has frontmatter so future tooling can validate and route work without parsing prose blindly.

## Status

Current maturity: **foundation / early reference tooling**.

Solid:

- protocol v0.1
- constitution
- agnostic agent catalog
- agnostic skill catalog
- profile set
- agent and skill schemas
- adapter contract
- portable reference CLI
- validation/status/new/check/archive commands
- conservative living spec sync

Still early:

- full JSON Schema validation
- semantic living spec merge
- successful archive fixture for a verified real change
- packaged CLI
- concrete adapters
- richer templates per profile

## Design Principles

- Keep the core small.
- Push tool-specific behavior into adapters.
- Prefer files over chat memory.
- Prefer evidence over confidence.
- Make the smallest workflow that preserves quality.
- Never archive incomplete work quietly.

## Agents And Skills

SSD-Core separates roles from runtimes.

Agents live under `.sdd/agents/`. They define portable role contracts for orchestration, exploration, specification, architecture, planning, implementation, verification, critique, and archiving.

Skills live under `.sdd/skills/`. They define portable workflow capabilities for proposing, specifying, designing, tasking, implementing, verifying, critiquing, syncing specs, and archiving.

Adapters can turn these Markdown contracts into prompts, commands, menus, subagents, jobs, or scripts. The protocol does not require any specific agent platform.

## Influences And Attribution

SSD-Core is a new framework, but it intentionally distills lessons from existing MIT-licensed SDD and agent workflow projects:

- [GitHub Spec Kit](https://github.com/github/spec-kit) — constitution-driven SDD, phase gates, and traceability.
- [OpenSpec](https://github.com/Fission-AI/OpenSpec) — change folders, delta specs, and archive/sync workflow.
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) — lightweight orchestrator patterns and phase-specific agents.
- [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD) — adaptive workflows, specialist roles, and scale-aware delivery.

All four projects are MIT licensed as of the license files checked on 2026-05-03. See [NOTICE.md](NOTICE.md) for attribution details.

SSD-Core does not claim endorsement by these projects and does not use their trademarks as product names. BMAD-related names are trademarks of BMad Code, LLC; they are referenced only for attribution.

## License

SSD-Core is released under the [MIT License](LICENSE).

Third-party inspiration and license notices are tracked in [NOTICE.md](NOTICE.md).
