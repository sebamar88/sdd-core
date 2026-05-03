---
schema: sdd.tooling-doc.v1
title: SDD-Core Validator v0.1
status: draft
date: 2026-05-03
audience: adapter-authors
scope: reference-tooling
---

# SDD-Core Validator v0.1

## Purpose

`scripts/sdd.py` is a dependency-free reference utility for validating the repository's SDD-Core artifacts.

It is not the protocol. It is a small portable tool that proves the initial artifact layout can be checked without requiring a specific agent, shell, package manager, or operating system.

## Usage

```text
python scripts/sdd.py validate
```

Validate another repository root:

```text
python scripts/sdd.py validate --root path-to-repository
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

## Limits

The validator intentionally does not perform full JSON Schema validation of arbitrary artifacts yet. It validates the schema files themselves and the frontmatter contract for Markdown artifacts.

Full artifact schema validation belongs in a future increment after artifact examples and adapter workflows stabilize.

## Portability Notes

The tool uses Python standard library modules only. It uses `pathlib` for host-native filesystem behavior and treats protocol paths as logical repository paths.
