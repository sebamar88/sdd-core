---
schema: sdd.profile.v1
artifact: profile
profile: refactor
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Refactor Profile

## Use When

- The intended behavior should not change.
- The goal is simplification, cleanup, boundary repair, or internal structure improvement.
- Existing behavior needs to be locked before edits.

## Required Artifacts

- `proposal.md`
- `tasks.md`
- `verification.md`

## Required Evidence

- Behavior lock through tests, snapshots, examples, characterization notes, or manual checks.
- Simplification plan.
- Verification that public behavior did not drift.

## Hard Gates

- Do not mix behavior changes into refactor work without changing profile or opening a separate change.
- Prefer deletion and reuse over new abstractions.
- Document any unavoidable behavior drift.

## Completion Evidence

- Before-and-after verification evidence.
- Summary of simplifications made.
- Known residual risks.
