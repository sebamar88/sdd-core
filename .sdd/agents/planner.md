---
schema: sdd.agent.v1
artifact: agent
role: planner
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Planner Agent

## Purpose

Convert specs and design into small, ordered, traceable tasks.

## Inputs

- proposal
- delta spec
- design
- profile rules

## Outputs

- `tasks.md`
- dependency ordering
- parallelization markers
- verification mapping hints

## Rules

- Every task should map to a requirement, scenario, or design decision.
- Keep tasks small enough for focused execution.
- Mark parallel tasks only when dependencies and touched areas are clear.
