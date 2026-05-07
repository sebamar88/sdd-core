---
schema: sdd.profile.v1
artifact: profile
profile: standard
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Standard Profile

## Use When

- The change is a normal feature or meaningful product behavior change.
- Requirements, design, tasks, and verification should be separately reviewable.
- The work is not broad enough for enterprise-level ceremony.

## Required Artifacts

- `proposal.md`
- `delta-spec.md`
- `design.md`
- `tasks.md`
- `verification.md`
- `archive.md`

## Allowed Shortcuts

- Exploration notes may be embedded in `proposal.md`.
- Critique may be embedded in `verification.md` for low-risk changes.

## Hard Gates

- Every task should trace to a requirement, scenario, or design decision.
- Archive is blocked until verification exists.
- Behavior changes must sync into living specs.

## Completion Evidence

- Requirement-to-evidence matrix.
- Completed or explicitly deferred tasks.
- Archive record.
