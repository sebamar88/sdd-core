# Changelog

## 0.10.0 - 2026-05-06

- Moved `write_ci_template`, `_CI_TEMPLATES`, `_GITHUB_ACTIONS_TEMPLATE`, and `_GITLAB_CI_TEMPLATE` from `_render.py` to `_workflow.py`. These are file-I/O operations that return `list[Finding]`, not presentation layer concerns. `_render.py` is now a pure presentation module — it only contains `print_*` functions and `run_demo`/`run_fast_demo`. No behavioral changes; public API is unchanged.
- Added 9 new tests (74 total) covering the `auto --loop` engine and execution-evidence integrity: auto-advance pauses at PROPOSE when proposal is not ready; transitions to TASK when proposal is ready; pauses at TASK (cannot auto-advance to VERIFY, which requires explicit `verify_change`); full lifecycle advances to ARCHIVED after verify; cannot skip VERIFY phase; evidence records contain all required fields (`schema`, `command`, `exit_code`, `passed`, `recorded_at`, `log_path`, `output_checksum`, `duration_seconds`); tampered evidence log fails SHA-256 integrity check; failed command records evidence and blocks verify.

## 0.9.0 - 2026-05-05

- Split monolithic `ssd_core/cli.py` (3845 lines) into four focused modules with a clean dependency chain:
  - `ssd_core/_types.py` (~360 lines): `VERSION`, color helpers, all constants, enums, and dataclasses. Zero internal dependencies.
  - `ssd_core/_workflow.py` (~2300 lines): file I/O, frontmatter, validation, change management, state machine, `WorkflowEngine`, `SDDWorkflow`, and `_auto_advance`. Imports only from `_types`.
  - `ssd_core/_render.py` (~880 lines): all `print_*` functions, `_print_auto_step`, `print_auto`, CI templates, `run_demo`, `run_fast_demo`. Imports from `_types` and `_workflow`.
  - `ssd_core/cli.py` (~430 lines): `build_parser` and `main` only. Re-exports the full public surface via star imports so `__init__.py` and all downstream consumers are unaffected.
- Public Python API (`ssd_core/__init__.py`) is unchanged — all imports from `ssd_core` continue to work without modification.
- All 65 tests pass unchanged. No behavioral changes.

## 0.8.0 - 2026-05-06

- Added `ssd-core evidence <change_id>`: displays all recorded execution evidence — command, exit code, duration, timestamp, output log path, and SHA-256 checksum integrity status. Lets humans and CI systems inspect exactly what ran before a change was marked verified.
- Added `ssd-core pr-check <change_id>`: outputs a Markdown governance report ready to paste into a GitHub/GitLab PR description. Shows phase, profile, evidence summary with a hash chain, and exits 0 only when the change is safe to merge. Exits 1 if the change is missing passing evidence.
- Added `ssd-core auto --verify-with <cmd>` flag: when `--loop` reaches the verify phase, runs the supplied command automatically instead of pausing for human input. Enables a fully unattended lifecycle: `ssd-core auto my-fix --loop --verify-with 'pytest -x'`. May be repeated for multiple commands.
- Added `ssd-core verify --commands-file <path>`: reads verification commands from a plain text file, one per line. Blank lines and lines starting with `#` are ignored. Composes with repeated `--command` flags.
- Added `ssd-core demo --fast`: 30-second anti-hallucination proof. Creates a change in a temp directory, simulates an agent claiming completion three times, shows each governance block with the exact reason, then closes the change with real evidence. Designed as a CI-friendly "wow in 30 seconds" demo.
- Added visual phase pipeline to `ssd-core phase` output: a horizontal `○ propose → ◎ task → ◉ verify → ○ archive` line shows where the change sits in the lifecycle at a glance.
- Added `print_evidence` and `print_pr_check` to the public Python API.
- Bumped `print_auto` public signature: new `verify_commands: list[str] | None` keyword argument mirrors the `--verify-with` CLI flag.

## 0.7.0 - 2026-05-05

- Added `ssd-core verify --discover`: auto-detects the project's test runner (pytest, npm test, cargo test, go test, make test) and runs it as the verification command. The discovered command is shown in `ssd-core auto` guidance when the workflow reaches the verify phase.
- Added `ssd-core ci-template`: writes a plug-and-play CI workflow file under the repository root. Supports `--type github-actions` (default, writes `.github/workflows/sdd-guard.yml`) and `--type gitlab-ci` (writes `.gitlab-ci-sdd.yml`). Fails if the file already exists.
- Added `write_ci_template` and `discover_test_command` to the public Python API.
- Added execution timing to evidence records: `run_verification_command` now captures `duration_seconds` in each `sdd.execution-evidence.v1` record and includes it in the log header (`duration: 0.123s`). The evidence line in `verification.md` now includes the duration and shows a 12-char SHA-256 prefix for the output checksum.
- Added ANSI color and icon output across all CLI commands. Colors are gated by `sys.stdout.isatty()`, `NO_COLOR`, and `TERM=dumb` so CI output stays clean. Key additions: phase icons (`○ ◎ ◉ ✔ ✗ ⟳`) on every phase line, green/yellow/red severity on findings, bold command names and change IDs in success messages.
- Updated `_print_auto_step`: when the workflow is at the verify phase, also prints the discovered test runner command (if any) as a ready-to-copy suggestion.
- Updated `run_demo` to use the new color helpers throughout.
- Fixed `_auto_advance` catch-up path: when the catch-up target is `SYNC_SPECS` or `ARCHIVE`, the engine now correctly records a phase transition first and lets the next iteration execute the actual command. Previously it called `sync_specs` / `archive_change` directly, which failed because those commands require the declared phase to already be recorded as their gate phase in `state.json`.

## 0.6.0 - 2026-05-05

- Added `--loop` flag to `ssd-core auto`: drains all auto-executable steps in sequence, stopping at the first phase that requires human input, at completion, or on a blocking finding. No file watchers, no polling, no new dependencies.
- Extracted `_print_auto_step()` internal helper to share rendering logic between single-step and loop modes.
- Rewrote `ssd-core demo` to showcase the `auto --loop` narrative: engine pauses visibly at proposal and task phases (human-work gates), drives through transitions automatically, and closes the change with checksummed evidence. Removes the old manual step-by-step walkthrough.

## 0.5.0 - 2026-05-05

- Added `ssd-core auto <change>` command: advisor + executor in one call. Executes transitions, `sync-specs`, and `archive` automatically when artifacts are ready. For human-work phases (proposal, tasks, verification, etc.) prints the exact file path to edit and blocks until re-run. Exit 0 always unless the workflow is blocked.
- Added `WorkflowEngine.execute_next(change_id)` returning `AutoStep`: the programmatic equivalent of `ssd-core auto`, designed for agent-driven loops. Returns `needs_human_work=True` when a file edit is required before the engine can advance further.
- Added `AutoStep` frozen dataclass: `executed_command`, `step` (EngineStep), `is_blocked`, `is_complete`, `needs_human_work`.
- Added `_PHASE_ARTIFACT_FILE` mapping every human-work phase to its canonical artifact filename.
- Added `_auto_advance()` internal function: single-step advance logic shared by `WorkflowEngine.execute_next()` and `ssd-core auto`.
- Exported `AutoStep` from the `ssd_core` package public API.
- Updated package description to: "AI development governance engine — prevent hallucinated completion and vanishing intent in agent-assisted software teams."

## 0.4.0 - 2026-05-05

- Added `ssd-core demo` command: annotated Golden Path walkthrough in a temporary directory. Runs the full `init → new → task → verify → archive` cycle with real SDD-Core logic, checksummed evidence, and automatic cleanup. Exit 0 on success, 1 on first failure.
- Added `EngineStep` frozen dataclass as the structured return type for agent-driven execution loops: `phase`, `next_action`, `suggested_command`, `allowed_commands`, `blocking_findings`, `is_blocked`, `is_complete`.
- Added `WorkflowEngine.next_step(change_id)` returning `EngineStep` — a single call that gives agent integrations and IDE tools all the context needed to advance the workflow without additional lookups.
- Added `_suggested_command()` internal helper that maps every `WorkflowPhase` to the canonical CLI command that advances past it.
- Exported `EngineStep` from the `ssd_core` package public API.
- Rewrote README: new structure (What / Why / Try It Now / Golden Path / Orchestrator API / WorkflowEngine loop / Hard Enforcement / When To Use / Reference). Opening line repositioned from "anti-hallucination" to "governance layer for AI-driven development".

## 0.3.0 - 2026-05-05

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
