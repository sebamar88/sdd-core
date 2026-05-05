# Changelog

## Unreleased

## 0.5.0 - 2026-05-05

- Added `ssd-core auto <change>` command: advisor + executor in one call. Executes transitions, `sync-specs`, and `archive` automatically when artifacts are ready. For human-work phases (proposal, tasks, verification, etc.) prints the exact file path to edit and blocks until re-run. Exit 0 always unless the workflow is blocked.
- Added `WorkflowEngine.execute_next(change_id)` returning `AutoStep`: the programmatic equivalent of `ssd-core auto`, designed for agent-driven loops. Returns `needs_human_work=True` when a file edit is required before the engine can advance further.
- Added `AutoStep` frozen dataclass: `executed_command`, `step` (EngineStep), `is_blocked`, `is_complete`, `needs_human_work`.
- Added `_PHASE_ARTIFACT_FILE` mapping every human-work phase to its canonical artifact filename.
- Added `_auto_advance()` internal function: single-step advance logic shared by `WorkflowEngine.execute_next()` and `ssd-core auto`.
- Exported `AutoStep` from the `ssd_core` package public API.
- Updated package description to: "AI development governance engine — prevent hallucinated completion and vanishing intent in agent-assisted software teams."



- Added `ssd-core demo` command: annotated Golden Path walkthrough in a temporary directory. Runs the full `init → new → task → verify → archive` cycle with real SDD-Core logic, checksummed evidence, and automatic cleanup. Exit 0 on success, 1 on first failure.
- Added `EngineStep` frozen dataclass as the structured return type for agent-driven execution loops: `phase`, `next_action`, `suggested_command`, `allowed_commands`, `blocking_findings`, `is_blocked`, `is_complete`.
- Added `WorkflowEngine.next_step(change_id)` returning `EngineStep` — a single call that gives agent integrations and IDE tools all the context needed to advance the workflow without additional lookups.
- Added `_suggested_command()` internal helper that maps every `WorkflowPhase` to the canonical CLI command that advances past it.
- Exported `EngineStep` from the `ssd_core` package public API.
- Rewrote README: new structure (What / Why / Try It Now / Golden Path / Orchestrator API / WorkflowEngine loop / Hard Enforcement / When To Use / Reference). Opening line repositioned from "anti-hallucination" to "governance layer for AI-driven development".



- Added `WorkflowEngine` as the declarative command gate for workflow commands, including `guard()`, `allowed_commands()`, and `execute()`.
- Added `COMMAND_GATES` as the single command-to-phase policy map for `verify`, `sync-specs`, and `archive`.
- Made `workflow_state()` prefer declared `.sdd/state.json` phase while keeping artifact-only inference available through `infer_phase_from_artifacts()` and `infer_state_from_artifacts()`.
- Added semantic verification matrix validation so `verification.md` must contain a passing row before closure.
- Added executable verification evidence through `ssd-core verify --command`, including stdout/stderr logs, exit codes, and output checksums under `.sdd/evidence/`.
- Added `WorkflowEngine.execute()` and `SDDWorkflow.verify()` so the engine can run gated workflow actions, not only validate whether they are allowed.
- Added `guard --require-execution-evidence` for repositories that want verified or archived changes to require passing execution records.
- Restricted the `verify` phase to the dedicated verify command so `transition verify` can no longer reconcile manual edits into a verified state.

## 0.2.0 - 2026-05-05

- Added `gate_command()` as the central pre-execution gate for destructive workflow commands.
- Hardened `SDDWorkflow.require_phase()` with optional checksum enforcement.
- Made `sync-specs` and `archive` use command gates instead of local phase checks.
- Added tests that prove stale artifact checksums block gated commands when checksum enforcement is enabled.

## 0.1.9 - 2026-05-05

- Blocked direct transition into `verify`; the `verify` phase must go through the dedicated `ssd-core verify` command.
- Blocked direct transition into `archived`; archive must go through `ssd-core archive`.
- Added `ssd-core log` to inspect recorded workflow history from `.sdd/state.json`.
- Tightened transition tests around restricted phases and recorded history.

## 0.1.8 - 2026-05-05

- Added `ssd-core verify` as the explicit gate for recording the `verify` phase.
- Added placeholder-evidence detection so `verification.md` cannot pass with template text such as `not-run` or `pending verification evidence`.
- Added `ssd-core phase` to show declared, artifact-inferred, and effective workflow phases.
- Added git `pre-push` hook generation alongside the existing pre-commit hook.
- Exported verification helpers through the public Python API.

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
