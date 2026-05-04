---
schema: sdd.adapter-authoring.v1
title: SSD-Core Adapter Authoring Guide v0.1
status: draft
date: 2026-05-03
audience: adapter-authors
scope: adapter-guide
---

# SSD-Core Adapter Authoring Guide v0.1

## Purpose

An SSD-Core adapter maps portable Markdown contracts to a concrete runtime without changing the protocol.

Adapters may target agent CLIs, IDEs, CI systems, local scripts, or manual team workflows.

## Minimum Adapter

A minimum adapter must:

- read `.sdd/constitution.md`
- read `.sdd/profiles/`
- read `.sdd/agents/`
- read `.sdd/skills/`
- create change artifacts
- record verification evidence
- preserve archive safety rules
- resume from repository artifacts

## Capability Manifest

Adapters should publish a manifest compatible with `.sdd/schemas/adapter-capabilities.schema.json`.

The reference manifest is:

```text
.sdd/adapters/generic-markdown.json
```

## Mapping Agents

Each file in `.sdd/agents/` is a role contract.

An adapter may map an agent to:

- a native subagent
- a prompt template
- a command
- an IDE action
- a CI job
- inline execution

## Mapping Skills

Each file in `.sdd/skills/` is a workflow capability.

An adapter may expose skills as:

- slash commands
- palette commands
- prompt snippets
- scripts
- workflow stages

## Non-Negotiable Rules

- Artifacts remain the source of truth.
- Verification evidence must be written back to the repo.
- `status`-like operations must stay read-only.
- Archive must not overwrite existing records.
- Runtime state must not replace `.sdd/` artifacts.

## Recommended Build Order

1. Implement `validate`.
2. Implement `new`.
3. Implement `status`.
4. Implement `check`.
5. Implement `sync-specs`.
6. Implement `archive`.
7. Map agents.
8. Map skills.
9. Add runtime-specific quality gates.
