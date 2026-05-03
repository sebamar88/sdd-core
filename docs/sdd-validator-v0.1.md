---
schema: sdd.tooling-doc.v1
title: SDD-Core Reference Tooling v0.1
status: draft
date: 2026-05-03
audience: adapter-authors
scope: reference-tooling
---

# SDD-Core Reference Tooling v0.1

## Purpose

`scripts/sdd.py` is a dependency-free reference utility for validating the repository's SDD-Core artifacts and creating change artifact sets.

It is not the protocol. It is a small portable tool that proves the initial artifact layout can be checked without requiring a specific agent, shell, package manager, or operating system.

## Usage

Validate the current repository:

```text
python scripts/sdd.py validate
```

Validate another repository root:

```text
python scripts/sdd.py validate --root path-to-repository
```

Create a standard change:

```text
python scripts/sdd.py new add-search --profile standard --title "Add search"
```

Create a change in another repository root:

```text
python scripts/sdd.py new fix-login --profile bugfix --root path-to-repository
```

## Checks

The validator checks:

- required `.sdd/` directories
- required protocol and constitution files
- required profile files
- required schema files
- Markdown frontmatter presence
- common frontmatter keys
- artifact status values
- profile names
- JSON syntax for schema files
- required top-level JSON Schema metadata
- protocol pointer to the canonical v0.1 spec

## Change Creation

`sdd new` creates `.sdd/changes/<change-id>/` and writes initial artifacts for the selected profile.

Supported profiles:

- `quick`
- `standard`
- `bugfix`
- `refactor`
- `enterprise`
- `research`

Rules:

- `change-id` must be kebab-case.
- The selected profile file must exist in `.sdd/profiles/`.
- Existing change directories are never overwritten.
- Generated artifacts use Markdown frontmatter and logical repository paths.

## Limits

The validator intentionally does not perform full JSON Schema validation of arbitrary artifacts yet. It validates the schema files themselves and the frontmatter contract for Markdown artifacts.

Full artifact schema validation belongs in a future increment after artifact examples and adapter workflows stabilize.

## Portability Notes

The tool uses Python standard library modules only. It uses `pathlib` for host-native filesystem behavior and treats protocol paths as logical repository paths.
