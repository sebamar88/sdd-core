Verify the active RunProof change.

1. Run `runproof status` to find the `change_id`.
2. Run `runproof verify <change_id> --discover` — this auto-detects the test runner, executes it, captures cryptographic evidence, and advances to VERIFY if all tests pass.
3. If `--discover` doesn't find the right command, run `runproof verify <change_id> --command "<your-test-command>"` instead.
4. Fix any failures and re-run until the phase advances.
