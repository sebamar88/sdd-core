# Changelog

## Unreleased

## 0.3.0 - 2026-05-05

- Added executable verification evidence through `ssd-core verify --command`, including stdout/stderr logs, exit codes, and output checksums under `.sdd/evidence/`.
- Added `WorkflowEngine.execute()` and `SDDWorkflow.verify()` so the engine can run gated workflow actions, not only validate whether they are allowed.
- Added `guard --require-execution-evidence` for repositories that want verified or archived changes to require passing execution records.
- Restricted the `verify` phase to the dedicated verify command so `transition verify` can no longer reconcile manual edits into a verified state.
- Added semantic verification checks for placeholder evidence and passing verification matrix rows.

## 0.1.7 - 2026-05-05

- Added `.sdd/state.json` as the explicit workflow registry for declared phases, transition history, and artifact checksums.
- Added `ssd-core transition` and `SDDWorkflow.transition()` to enforce state-machine phase moves instead of trusting inferred Markdown state alone.
- Hardened `sync-specs` and `archive` so they require recorded workflow phases before running.
- Added `guard --strict-state` and upgraded installed pre-commit hooks to block stale artifact checksums and unrecorded active changes.
- Extended release checks to smoke-test strict guard enforcement from wheel and npm wrapper installs.

## 0.1.6 - 2026-05-05

- Added `ssd-core guard` for CI and hook enforcement of repository governance.
- Added `ssd-core install-hooks` to install a pre-commit hook that blocks commits without an active SDD change.
- Hardened `archive` so changes with `delta-spec.md` cannot archive until living specs are synced.
- Extended release checks to smoke-test guard and hook installation from wheel and npm wrapper installs.

## 0.1.5 - 2026-05-05

- Added `SDDWorkflow` as the importable strict orchestrator API for tools, adapters, and IDE integrations.
- Added `WorkflowResult`, `WorkflowFailure`, and `WorkflowFailureKind` to make phase-order failures explicit instead of implicit findings only.
- Documented real orchestrator usage in the README with importable Python code.

## 0.1.4 - 2026-05-05

- Added `ssd-core run` as the workflow binding layer that creates or inspects a governed change and reports the enforced current phase.
- Added explicit workflow state types for not-started, propose, specify, design, task, verify, critique, archive-record, sync-specs, archive, archived, and blocked states.
- Updated the Golden Path to use the real `ssd-core run` entrypoint instead of separate primitive commands only.
- Extended release checks to smoke-test `ssd-core run` from both wheel installs and npm wrapper installs.

## 0.1.3 - 2026-05-05

- Repositioned the README around governance anti-hallucination for production agent workflows.
- Added a Golden Path that shows a concrete login hardening change from init to archive.
- Clarified when to use SSD-Core, when not to use it, and how it differs from generic SDD templates.

## 0.1.2 - 2026-05-05

- Updated install instructions for the published npm package, including global install and one-shot `npx` usage.

## 0.1.1 - 2026-05-05

- Fixed the npm wrapper so relative `--root` paths resolve from the caller's current directory instead of the installed package directory.
- Added a release gate that smoke-tests npm-installed wrapper behavior with a relative project root.
- Aligned production-readiness wording with v0.1 scope: concrete adapter manifests are included, executable runtime wrappers are deferred.
- Added explicit DRY, KISS, YAGNI, SOLID, GRASP, and LoD principles to project guidance and constitutions.
- Hardened frontmatter validation with ISO date checks and consistency checks for change and living spec artifacts.
- Added regression tests for validation edge cases and mismatch scenarios.
- Added one-week closure plan and closure record artifacts under `docs/superpowers/plans/`.
- Updated npm publish workflow to use `--access public` with provenance publishing.

## 0.1.0 - 2026-05-03

Initial SSD-Core production candidate.

- Added protocol v0.1, constitution, profiles, schemas, adapter contract, agent contracts, and skill contracts.
- Added dependency-free reference CLI with `init`, `validate`, `status`, `new`, `check`, `sync-specs`, `archive`, and `version`.
- Added packaged `ssd-core` command with bundled templates and docs.
- Added concrete adapter manifests for Codex, Claude Code, Gemini CLI, OpenCode, and Qwen Code.
- Added a portable release readiness script and CI workflow.
- Added an npm wrapper package that delegates to the Python core.
- Added a GitHub Actions npm publish workflow using `NPM_REPOSITORY_TOKEN`.
- Added release-time version consistency checks across Python, npm, and Git tags.
- Added a `uv venv --seed` fallback for Linux environments without `python3-venv`.
- Added end-to-end lifecycle tests and a standard verified change example.
- Added MIT license and attribution notices for the MIT-licensed projects that influenced SSD-Core.
