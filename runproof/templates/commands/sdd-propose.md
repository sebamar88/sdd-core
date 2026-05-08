Draft a proposal for the active RunProof change.

1. Run `runproof status` to find the active `change_id`.
2. Ask the user: **"What are you trying to change and why?"** — skip if the intent is already clear from context.
3. Write `.runproof/changes/<change_id>/proposal.md`. Keep it tight: one-sentence intent, explicit scope, and how success is measured. No fluff.
4. Run `runproof ready <change_id>` to mark the proposal ready and advance to SPECIFY.
