---
schema: sdd.adapter-contract.v1
title: SDD-Core Adapter Contract v0.1
status: draft
date: 2026-05-03
audience: adapter-authors
scope: protocol-adapter
---

# SDD-Core Adapter Contract v0.1

## 1. Purpose

An SDD-Core adapter connects the protocol to a concrete agent environment, IDE, automation runtime, or command surface without changing the protocol core.

The adapter contract defines what an integration must preserve so SDD-Core remains agent-agnostic and operating-system-agnostic.

## 2. Adapter Responsibilities

An adapter MUST:

- Preserve `.sdd/` artifact semantics.
- Read and honor `.sdd/constitution.md`.
- Support at least one profile from `.sdd/profiles/`.
- Translate logical paths to host-native paths.
- Translate verification actions to host-native process execution or manual evidence capture.
- Record outputs in SDD-Core artifacts instead of relying only on chat history.
- Report unsupported capabilities explicitly.

An adapter MUST NOT:

- Require changes to SDD-Core schemas to support one agent.
- Encode one operating system as the protocol default.
- Treat a checked task as sufficient verification evidence.
- Archive a behavior-changing change without updating living specs or documenting why no update is needed.

## 3. Capability Declaration

Every adapter SHOULD expose a capability declaration.

Example:

```yaml
adapter: example-agent
schema: sdd.adapter-capabilities.v1
version: 0.1.0
host:
  agents:
    delegation: optional
    native_subagents: false
  platform:
    path_translation: true
    process_execution: true
    filesystem_watch: false
profiles:
  supported:
    - quick
    - standard
    - bugfix
verification:
  command_execution: true
  manual_evidence: true
  screenshot_evidence: false
schemas:
  validate_json_schema: true
state:
  resume_active_change: true
```

Capability declarations may be stored in adapter-specific locations, but they should be exportable as plain text.

SSD-Core includes a baseline manifest at `.sdd/adapters/generic-markdown.json`.

## 4. Path Translation

SDD-Core examples use logical repository paths such as `.sdd/changes/add-dark-mode/tasks.md`.

Adapters MUST translate logical paths into the host platform's native file access behavior.

Rules:

- Logical path identity is case-sensitive unless the adapter documents host limitations.
- Logical paths must remain repository-relative unless the artifact explicitly declares an external reference.
- Adapters must preserve artifact identity when displaying paths to humans.
- Adapters may normalize separators internally.

## 5. Process And Verification Translation

The protocol refers to verification actions, not specific shell commands.

Adapters MAY satisfy verification through:

- host-native process execution
- IDE task runners
- CI systems
- test framework integrations
- manual evidence capture
- screenshots
- logs
- structured review reports

Verification records MUST include:

- what was checked
- how it was checked
- outcome
- evidence reference when available
- known gaps

## 6. Artifact Access

Adapters MUST support reading and writing repository artifacts needed by the selected profile.

Minimum artifact operations:

- read file
- write file
- list profile files
- list active changes
- detect living specs
- create change directory
- archive or copy completed changes

Adapters SHOULD avoid passing full artifact contents between agents when a file reference is enough.

## 7. Delegation Model

SDD-Core does not require subagents.

Adapters may implement one of these models:

- `single-agent`: one agent executes all phases.
- `delegated`: an orchestrator dispatches phase work to subagents.
- `hybrid`: some phases are delegated and others are inline.
- `external`: phases are executed by external tools or CI jobs.

Regardless of model, the adapter MUST preserve phase result records when phase boundaries matter.

## 8. Profile Selection

Adapters SHOULD choose the smallest profile that safely fits the task.

Profile selection inputs:

- user intent
- affected behavior breadth
- risk level
- security or compliance impact
- existing test coverage
- brownfield or greenfield context

Adapters MUST let users or governing instructions override profile selection when the override is safe.

## 9. State Recovery

Adapters SHOULD recover from interrupted sessions by reading artifacts, not chat history.

Recovery order:

1. Read `.sdd/constitution.md`.
2. List `.sdd/changes/`.
3. Identify active changes and artifact statuses.
4. Determine selected profile.
5. Resume at the next incomplete phase.

If multiple active changes exist, adapters must disambiguate by explicit change ID or safe project policy.

## 10. Schema Validation

Adapters SHOULD support validation levels from the core protocol:

- Level 0: layout-readable
- Level 1: frontmatter-valid
- Level 2: JSON-schema-valid

An adapter that cannot perform Level 2 validation must still preserve artifacts and report that schema validation is unavailable.

## 11. Approval Gates

Adapters MAY support human approval gates, autonomous gates, or both.

Approval decisions must be recorded when they affect lifecycle progression.

Examples:

- Proceed from proposal to specification.
- Proceed from design to implementation.
- Waive an automated test gap.
- Archive with documented residual risk.

Fully autonomous adapters must replace approval gates with explicit policy checks and recorded rationale.

## 12. Compliance Checklist

An adapter is SDD-Core compliant when it can:

- initialize or detect `.sdd/`
- read the constitution
- map supported agent role contracts
- map supported skill contracts
- select or accept a profile
- create a change artifact set
- write phase results or equivalent artifact updates
- record verification evidence
- archive completed changes
- recover state from artifacts
- report unsupported capabilities

## 13. Adapter Boundary

The adapter may define:

- command names
- UI flows
- model routing
- agent mappings
- skill mappings
- subagent prompts
- process execution mechanics
- installation details
- host permissions

The adapter may not redefine:

- core artifact meaning
- profile required artifacts without declaring a profile extension
- verification evidence requirements
- archive safety requirements
- constitution precedence

## 14. Open Questions

- Should adapter capability declarations live under `.sdd/adapters/` or remain adapter-owned?
- Should adapters register profile extensions in a shared manifest?
- Should phase result records be mandatory for single-agent adapters?
- Should approval records use a dedicated schema in v0.2?
- Should path identity rules become stricter for case-insensitive filesystems?
