---
schema: sdd.protocol.v1
title: ProofKit Protocol v0.1
status: draft
date: 2026-05-03
audience: agent-framework-builders
scope: protocol
---

# ProofKit Protocol v0.1

## 1. Purpose

ProofKit is an agent-agnostic and operating-system-agnostic protocol for spec-driven development. It defines the minimum artifacts, lifecycle states, validation contracts, and adapter boundaries needed for AI coding agents to build software from explicit intent instead of chat-only context.

The protocol is Markdown-first so humans can read and edit it directly. It is also machine-validable through required frontmatter, stable artifact names, and optional JSON schemas.

## 2. Goals

- Make specifications the durable source of intent.
- Keep the protocol independent from any single AI tool, IDE, model, or orchestration runtime.
- Keep the protocol independent from any operating system, shell, package manager, path separator, or process runner.
- Support both greenfield and brownfield projects.
- Use delta specs for proposed changes and archive completed changes into living specs.
- Let agents work from file references instead of large pasted context.
- Require verification evidence before a change is considered complete.
- Keep the core small while allowing opinionated profiles for different work types.

## 3. Non-Goals

- Define a full CLI implementation.
- Require one agent platform or subagent mechanism.
- Require Unix, Windows, macOS, POSIX shells, PowerShell, Bash, or any specific command runner.
- Force every change through heavyweight PRD and architecture phases.
- Replace local engineering conventions, test frameworks, or repository guidance.
- Store hidden state that cannot be inspected in the repository.

## 4. Influences

ProofKit distills four existing patterns:

- GitHub Spec Kit: constitution-driven development, phase gates, task traceability, and executable specifications.
- OpenSpec: artifact store, delta specs, active changes, and archive/sync workflow.
- Agent Teams Lite / gentle-ai: lightweight orchestrator, phase-specific agents, fresh context, and result envelopes.
- BMAD Method: scale-adaptive tracks, specialist roles, and story-centric implementation.

The protocol intentionally does not clone any one of these systems.

## 5. Platform Independence

ProofKit uses logical repository paths in examples. Logical paths use `/` as a portable notation, not as an operating-system requirement.

Adapters MUST translate logical paths, commands, environment access, file permissions, and process execution into the host platform's native behavior.

The core protocol MUST NOT require:

- POSIX paths
- Windows paths
- Bash
- PowerShell
- a specific package manager
- a specific terminal
- a specific filesystem case-sensitivity model
- a specific line ending convention

Artifacts SHOULD be UTF-8 Markdown with stable frontmatter. Adapters MAY normalize line endings and path separators as long as artifact identity and schema fields remain stable.

## 6. Repository Layout

An initialized project SHOULD use this layout:

```text
.sdd/
  adapters/
    generic-markdown.json
  agents/
    orchestrator.md
    explorer.md
    specifier.md
    architect.md
    planner.md
    implementer.md
    verifier.md
    critic.md
    archivist.md
  protocol.md
  constitution.md
  profiles/
    quick.md
    standard.md
    bugfix.md
    refactor.md
    enterprise.md
    research.md
  schemas/
    agent.schema.json
    artifact.schema.json
    phase-result.schema.json
    skill.schema.json
    verification.schema.json
  skills/
    propose.md
    specify.md
    design.md
    task.md
    implement.md
    verify.md
    critique.md
    sync-specs.md
    archive.md
  specs/
    <domain>/
      spec.md
  changes/
    <change-id>/
      proposal.md
      delta-spec.md
      design.md
      tasks.md
      verification.md
      critique.md
      archive.md
  archive/
    <date>-<change-id>/
  examples/
    standard-verified-change/
```

Required directories:

- `.sdd/specs/`
- `.sdd/changes/`
- `.sdd/archive/`

Recommended directories:

- `.sdd/adapters/`
- `.sdd/agents/`
- `.sdd/examples/`
- `.sdd/profiles/`
- `.sdd/schemas/`
- `.sdd/skills/`

## 7. Core Concepts

### Constitution

`.sdd/constitution.md` defines stable project rules. It is not decorative documentation. Agents and adapters MUST treat it as an execution constraint.

Recommended sections:

- Principles
- Engineering Constraints
- Testing Policy
- Security Policy
- UX Policy
- Dependency Policy
- Git and Commit Policy
- Definition of Done
- Amendment Process

### Living Specs

`.sdd/specs/` describes current system behavior. Specs are organized by domain.

Living specs answer: "What does the system do today?"

### Change

`.sdd/changes/<change-id>/` describes a proposed or active modification.

A change answers:

- Why are we changing the system?
- What behavior is added, modified, or removed?
- How will it be implemented?
- What evidence proves it is done?

### Delta Spec

`delta-spec.md` describes the behavioral difference between the living specs and the intended future behavior.

It uses three change types:

- `ADDED`
- `MODIFIED`
- `REMOVED`

### Profile

A profile is an opinionated lifecycle variant built on top of the core protocol. Profiles define how much ceremony is required for a work type.

The core protocol stays minimal; profiles provide practical defaults.

### Adapter

An adapter maps the protocol to a concrete agent environment: Codex, Claude Code, Cursor, OpenCode, Copilot, Kiro, Windsurf, or another tool.

Adapters MAY provide slash commands, skills, prompts, MCP tools, CLI commands, or IDE workflows. They MUST preserve the artifact contracts.

### Agent

An agent is a portable role contract under `.sdd/agents/`. It defines responsibilities, inputs, outputs, and rules. Adapters may map agents to native subagents, prompts, menus, jobs, or inline execution.

### Skill

A skill is a portable workflow capability under `.sdd/skills/`. It defines a phase action such as proposing, specifying, verifying, syncing specs, or archiving. Adapters may expose skills through their native command or workflow mechanisms.

### Adapter Manifest

An adapter manifest is a machine-readable capability declaration under `.sdd/adapters/`. It tells humans and tooling which profiles, agents, skills, verification mechanisms, and state recovery behaviors an adapter supports.

## 8. Required Artifact Metadata

Every ProofKit artifact SHOULD begin with frontmatter.

Minimum fields:

```yaml
---
schema: sdd.artifact.v1
artifact: proposal
change_id: add-dark-mode
status: draft
created: 2026-05-03
updated: 2026-05-03
---
```

Common artifact statuses:

- `draft`
- `ready`
- `in_progress`
- `blocked`
- `verified`
- `archived`

Adapters MUST NOT infer completion from a checked box alone. Completion requires status plus evidence.

## 9. Change Lifecycle

Canonical lifecycle:

```text
explore -> propose -> specify -> design -> task -> implement -> verify -> critique -> archive
```

Lifecycle phases:

| Phase | Purpose | Primary Output |
| --- | --- | --- |
| explore | Understand context, constraints, affected areas | exploration notes or proposal context |
| propose | Define intent, scope, non-scope, risks | `proposal.md` |
| specify | Define observable behavior | `delta-spec.md` |
| design | Define technical approach and decisions | `design.md` |
| task | Convert plan into executable work | `tasks.md` |
| implement | Change code and mark task progress | code + task updates |
| verify | Prove behavior and quality gates | `verification.md` |
| critique | Challenge specs, code, tests, risks | `critique.md` |
| archive | Sync living specs and preserve history | `archive.md` + archive folder |

Profiles MAY skip phases only when their profile rules say how the skipped information is captured.

## 10. Profiles

### quick

Use for small, clear, low-risk work.

Required artifacts:

- `proposal.md` or embedded mini-proposal
- `tasks.md`
- `verification.md`

Allowed shortcuts:

- `delta-spec.md` MAY be omitted if no living spec exists or the change is purely internal.
- `design.md` MAY be omitted if implementation path is obvious and low risk.

### standard

Use for normal feature work.

Required artifacts:

- `proposal.md`
- `delta-spec.md`
- `design.md`
- `tasks.md`
- `verification.md`
- `archive.md`

### bugfix

Use when fixing incorrect behavior.

Required evidence:

- reproduction or failure description
- expected behavior
- regression test or explicit reason no automated regression test is practical
- verification output

### refactor

Use when behavior should not change.

Required evidence:

- behavior lock: tests, snapshots, examples, or characterization notes
- simplification plan
- verification that public behavior did not drift

### enterprise

Use for broad, security-sensitive, compliance-heavy, or multi-team changes.

Additional artifacts SHOULD include:

- research notes
- architecture decision records
- security review
- test strategy
- rollout plan
- operational risks

### research

Use for discovery without implementation.

Required output:

- research question
- sources inspected
- findings
- recommendations
- unresolved questions

## 11. Phase Agent Contract

An SDD phase agent receives artifact references and produces a structured result. It SHOULD NOT receive full repository dumps unless the adapter has no better option.

Example result envelope:

```yaml
---
schema: sdd.phase-result.v1
change_id: add-dark-mode
phase: specify
status: complete
reads:
  - .sdd/changes/add-dark-mode/proposal.md
writes:
  - .sdd/changes/add-dark-mode/delta-spec.md
next:
  - design
risk: low
blocking_issues: []
---
```

Required result fields:

- `schema`
- `change_id`
- `phase`
- `status`
- `reads`
- `writes`
- `next`

Allowed statuses:

- `complete`
- `partial`
- `blocked`
- `failed`

If status is `partial`, `blocked`, or `failed`, the result MUST include concrete next actions.

## 12. Orchestrator Contract

The orchestrator is a state machine over artifacts.

It MUST:

- choose a profile
- identify required artifacts
- record declared workflow state in `.sdd/state.json`
- dispatch phases to capable agents or execute them directly if no delegation exists
- pass artifact references, not unnecessary full context
- enforce dependencies between phases
- reject phase transitions that are not supported by artifact readiness
- execute verification commands when a workflow requires executable evidence
- show phase summaries
- prevent archive before verification

It MUST NOT:

- treat chat history as the only durable source of truth
- mark a change complete without verification evidence
- silently ignore constitution violations
- overwrite unrelated user changes

The state registry is not hidden runtime memory. It is a repository artifact that records the declared phase, transition history, and artifact checksum for each governed change. Tooling SHOULD compare this registry with the artifacts on disk before privileged actions such as sync, archive, commit hooks, or CI gates.

Execution evidence is also repository-native. Commands executed by the workflow engine SHOULD record exit code, stdout/stderr log path, and output checksum under `.sdd/evidence/<change-id>/`.

## 13. Task Contract

`tasks.md` SHOULD contain tasks that are small, ordered, and traceable.

Each task SHOULD include:

- stable ID
- description
- requirement or scenario link
- dependencies
- parallelization marker when safe
- completion status

Example:

```markdown
- [ ] T-004 [P] Add theme preference persistence
  - Requirement: REQ-001
  - Scenario: SCN-001
  - Depends on: T-002
```

Parallel work is allowed only when dependencies and touched areas are clear.

## 14. Verification Contract

`verification.md` maps requirements to evidence.

Minimum structure:

```markdown
# Verification

## Matrix

| Requirement | Scenario | Tasks | Evidence | Status |
| --- | --- | --- | --- | --- |
| REQ-001 | SCN-001 | T-002, T-004 | project test command | pass |

## Commands

- `project test command`
- `project lint command`

## Manual Checks

- Checked theme toggle persists across reload.

## Gaps

- None.
```

Verification evidence MAY include:

- tests
- typecheck
- lint
- build
- static analysis
- screenshots
- manual checks
- logs
- review findings

Adapters MUST report known verification gaps.

When executable evidence is required, `verification.md` is not enough by itself. The workflow MUST also include passing execution records under `.sdd/evidence/<change-id>/`, and those records MUST point to logs whose checksums still match.

## 15. Critique Contract

The critique phase challenges the change before closure.

It SHOULD inspect:

- spec ambiguity
- missed acceptance criteria
- task/spec traceability gaps
- test adequacy
- security risks
- performance risks
- over-engineering
- behavior drift
- archive readiness

For low-risk quick changes, critique MAY be merged into verification.

For enterprise changes, critique SHOULD be a hard gate.

## 16. Archive and Sync Contract

Archiving a change means:

1. Apply `delta-spec.md` to `.sdd/specs/`.
2. Record verification and critique status.
3. Write `archive.md`.
4. Move or copy the completed change to `.sdd/archive/<date>-<change-id>/`.
5. Mark the active change as archived or remove it from `.sdd/changes/`.

Archive MUST NOT occur when:

- required verification is missing
- open blockers remain
- delta specs cannot be applied unambiguously
- the constitution has unresolved violations

## 17. Adapter Contract

An adapter integrates ProofKit into a concrete tool.

An adapter SHOULD define:

- installation location
- command names
- supported profiles
- delegation mechanism
- artifact read/write permissions
- verification command discovery
- host operating system path and process translation
- schema validation support
- state recovery behavior

Adapter examples:

- Codex: skills, AGENTS.md guidance, native subagents, verification runner integration.
- Claude Code: slash commands and Task subagents.
- Cursor: rules, commands, and native agents.
- OpenCode: commands, profiles, and per-phase model routing.
- Copilot: prompt files and workspace instructions.
- Kiro: steering docs and native agents.

The adapter can vary. The artifact contract must remain stable.

## 18. Validation Levels

ProofKit supports three validation levels:

### Level 0: Human-readable

Artifacts exist and follow the documented layout.

### Level 1: Frontmatter-valid

Required metadata fields are present and coherent.

### Level 2: Schema-valid

Artifacts validate against JSON schemas.

The protocol SHOULD start at Level 1 and evolve toward Level 2.

## 19. Definition of Done

A change is done only when:

- required profile artifacts exist
- tasks are complete or explicitly deferred
- verification evidence exists
- known gaps are documented
- critique is complete or explicitly waived by profile rules
- living specs are updated when behavior changes
- archive record exists

## 20. Open Questions

- Should `.sdd/protocol.md` be copied per project, or should projects pin a protocol version externally?
- Should archive move completed changes or copy them and leave tombstones in `.sdd/changes/`?
- Should JSON schemas be normative in v0.1 or introduced in v0.2?
- How should adapters represent approval gates in fully autonomous environments?
- Should profiles be composable, for example `bugfix + security`?
- Should artifact IDs be global or scoped per change?
- Should path normalization be specified in v0.2 as a formal schema rule or remain adapter-defined?

## 21. v0.1 Recommendation

Start with:

- Markdown artifacts with required frontmatter.
- Core layout and lifecycle.
- Profiles: `quick`, `standard`, `bugfix`, `refactor`, `enterprise`, `research`.
- Manual schema examples, not mandatory schema enforcement.
- One reference adapter after the protocol stabilizes.

The first implementation should validate layout and metadata before it tries to automate full lifecycle execution.
