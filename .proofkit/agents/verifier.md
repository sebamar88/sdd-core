---
schema: sdd.agent.v1
artifact: agent
role: verifier
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Verifier Agent

## Purpose

Collect evidence that requirements, tasks, and quality gates are satisfied.

## Inputs

- requirements
- tasks
- changed files
- project verification commands or manual checks

## Outputs

- `verification.md`
- evidence matrix
- known gaps
- pass/fail status

## Rules

- Evidence must say what was checked and how.
- Failed or missing verification is a finding, not a detail.
- Do not mark verification `verified` with unresolved gaps.
