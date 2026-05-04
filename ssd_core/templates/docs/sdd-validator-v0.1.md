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

`scripts/sdd.py` is a dependency-free reference utility for validating the repository's SDD-Core artifacts, showing SDD status, creating change artifact sets, checking archive readiness, syncing living specs, and archiving verified changes.

It is not the protocol. It is a small portable tool that proves the initial artifact layout can be checked without requiring a specific agent, shell, package manager, or operating system.

## Usage

Install from the repository:

```text
python -m pip install -e .
```

Show the installed CLI version:

```text
ssd-core version
```

Validate the current repository:

```text
ssd-core validate
```

Initialize SSD-Core in a repository:

```text
ssd-core init --root path-to-repository
```

Validate another repository root:

```text
ssd-core validate --root path-to-repository
```

Show current SDD status:

```text
ssd-core status
```

Check whether a change is ready to archive:

```text
ssd-core check add-search
```

Archive a verified change:

```text
ssd-core archive add-search
```

Sync a verified delta spec into living specs:

```text
ssd-core sync-specs add-search
```

Create a standard change:

```text
ssd-core new add-search --profile standard --title "Add search"
```

Create a change in another repository root:

```text
ssd-core new fix-login --profile bugfix --root path-to-repository
```

## Checks

The validator checks:

- required `.sdd/` directories
- required adapter manifests
- required agent files
- required protocol and constitution files
- required profile files
- required skill files
- required schema files
- Markdown frontmatter presence
- common frontmatter keys
- `created` and `updated` ISO date validation
- artifact status values
- profile names
- change artifact consistency (`change_id`, `profile`, and `artifact` name)
- living spec consistency (`change_id` and `artifact` name)
- JSON syntax for schema files
- required top-level JSON Schema metadata
- protocol pointer to the canonical v0.1 spec

## Status

`sdd status` summarizes repository health and active changes.

It reports:

- validation pass or fail
- active change count
- detected profile for each active change
- present Markdown artifacts
- missing artifacts required by the detected profile
- validation errors and warnings

`status` is read-only. It never creates, updates, archives, or deletes artifacts.

## Readiness Check

`sdd check <change-id>` evaluates whether a change is ready to archive.

The first readiness gate is intentionally conservative:

- the change directory must exist
- the profile must be detectable from artifact frontmatter
- all profile-required artifacts must exist
- artifacts must not be `blocked`
- `tasks.md` must not contain open checkbox tasks
- `verification.md` frontmatter status must be `verified`
- `verification.md` must not contain `not-run`
- `verification.md` must not contain `pending verification evidence`

The command exits with status code `0` only when the change is ready.

## Archive

`sdd archive <change-id>` first runs the same readiness gate as `sdd check`.

When the change is ready, it copies the active change directory to `.sdd/archive/<date>-<change-id>/` and removes the active change directory from `.sdd/changes/`.

Rules:

- archive is blocked when readiness checks fail
- archive is blocked when the destination already exists
- archive does not run `sync-specs` automatically
- archive does not overwrite existing archive records

## Spec Sync

`sdd sync-specs <change-id>` copies a verified `delta-spec.md` into `.sdd/specs/<change-id>/spec.md` as a living spec snapshot and records the sync in `archive.md` when that file exists.

Rules:

- sync uses the same readiness gate as `sdd check`
- `delta-spec.md` is required
- existing living specs are not overwritten
- sync is conservative and does not perform semantic merge yet

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
