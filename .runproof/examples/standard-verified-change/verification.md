---
schema: sdd.verification.v1
artifact: verification
change_id: standard-verified-change
profile: standard
status: verified
created: 2026-05-03
updated: 2026-05-03
---

# Verification

## Matrix

| Requirement | Scenario | Tasks | Evidence | Status |
| --- | --- | --- | --- | --- |
| standard example exists | artifacts present | T-001 | example files under `.sdd/examples/standard-verified-change/` | pass |
| example is structurally valid | repository validation | T-002 | `python scripts/sdd.py validate` | pass |

## Commands

- `python scripts/sdd.py validate`

## Manual Checks

- Confirmed the example is outside `.sdd/changes/`.

## Gaps

- None.
