---
schema: sdd.skill.v1
artifact: skill
skill: archive
status: active
created: 2026-05-03
updated: 2026-05-03
---

# Archive Skill

## Purpose

Archive a completed change and remove it from active work.

## Inputs

- verified change artifacts
- sync record
- critique result

## Outputs

- archived change folder
- clean active changes directory

## Completion

Archive is complete when history is preserved and the active change no longer appears in `.sdd/changes/`.
