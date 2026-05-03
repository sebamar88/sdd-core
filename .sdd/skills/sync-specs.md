---
schema: sdd.skill.v1
artifact: skill
skill: sync-specs
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Sync Specs Skill

## Purpose

Synchronize verified behavior changes into living specs.

## Inputs

- verified delta spec
- living specs
- archive record

## Outputs

- updated living specs
- sync record

## Completion

Sync is complete when the behavior change is represented in `.sdd/specs/` and the change records what was updated.
