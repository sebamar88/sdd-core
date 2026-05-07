---
schema: sdd.profile.v1
artifact: profile
profile: quick
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Quick Profile

## Use When

- The change is small, clear, and low risk.
- The affected behavior is narrow.
- The implementation path is already constrained by existing project patterns.

## Required Artifacts

- `proposal.md` or an embedded mini-proposal in `tasks.md`
- `tasks.md`
- `verification.md`

## Allowed Shortcuts

- `delta-spec.md` may be omitted when no living spec exists or the change is purely internal.
- `design.md` may be omitted when the implementation path is obvious and low risk.
- `critique.md` may be merged into `verification.md`.

## Hard Gates

- Intent must be explicit.
- Verification evidence must exist.
- Known gaps must be recorded.

## Completion Evidence

- Completed tasks.
- Verification matrix or concise equivalent.
- Commands, checks, or review evidence appropriate to the host project.
