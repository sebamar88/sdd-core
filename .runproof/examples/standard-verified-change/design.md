---
schema: sdd.artifact.v1
artifact: design
change_id: standard-verified-change
profile: standard
status: ready
created: 2026-05-03
updated: 2026-05-03
---

# Design

## Approach

- Use Markdown artifacts only.
- Keep the example outside `.sdd/changes/` so it is not treated as active work.
- Make the example pass the same frontmatter validation rules as live artifacts.

## Decisions

- Store the example under `.sdd/examples/standard-verified-change/`.
- Use `status: verified` only for verification because the evidence matrix is complete.

## Alternatives Rejected

- Store the example under `.sdd/changes/` | it would appear as active work.
- Store the example only in docs | it would not exercise `.sdd` artifact validation.
