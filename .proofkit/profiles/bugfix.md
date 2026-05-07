---
schema: sdd.profile.v1
artifact: profile
profile: bugfix
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Bugfix Profile

## Use When

- Existing behavior is incorrect.
- A failure, regression, or defect needs to be reproduced and fixed.
- The main risk is changing too much while fixing too little.

## Required Artifacts

- `proposal.md`
- `tasks.md`
- `verification.md`

## Required Evidence

- Reproduction notes or failure description.
- Expected behavior.
- Regression test or documented reason automated regression coverage is not practical.
- Verification after the fix.

## Hard Gates

- Do not implement before the expected behavior is clear.
- Do not close without evidence that the defect no longer reproduces.
- Do not broaden scope beyond the defect unless a new profile is selected.

## Completion Evidence

- Failing-before or reproduced-before evidence when practical.
- Passing-after evidence.
- Regression protection or explicit test gap.
