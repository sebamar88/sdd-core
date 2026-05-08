Write the design for the active RunProof change.

1. Run `runproof status` to find the `change_id`, then read `proposal.md` and `delta-spec.md`.
2. Derive the implementation approach from the spec — chosen approach, key components and data flow, edge cases. Note rejected alternatives only if the choice is non-obvious.
3. Write `.runproof/changes/<change_id>/design.md`. Be precise and brief.
4. Run `runproof ready <change_id>` to mark the design ready and advance to TASK.
