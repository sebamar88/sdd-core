# Changelog

## 0.23.0 - 2026-05-07

**Trace mode + contract tests (133 tests pass, 1 skipped)**

### `--trace` debug mode

- New top-level flag `sdd-core --trace <command>` emits component-level flow to stderr.
- Trace infrastructure added to `ssd_core/_types.py`: `enable_trace()`, `trace(component, message)`.
- Trace calls added to five workflow sub-modules:
  - `ENGINE` — `guard_repository`, `_auto_advance`, `WorkflowEngine.guard`, `WorkflowEngine.execute`
  - `VALIDATION` — `validate`
  - `REGISTRY` — `transition_workflow`, `gate_command`, `require_recorded_phase`
  - `EVIDENCE` — `verify_change`, `run_verification_command`
  - `INFERENCE` — `workflow_state`, `run_workflow`
- Output format: `[TRACE] ENGINE       → guard_repository root=...` (stderr only; stdout unchanged).

### Contract tests

- New `tests/test_contracts.py` — 10 tests covering cross-module behavioral guarantees:
  - `REGISTRY` atomicity: blocked transition never mutates `state.json`.
  - `EVIDENCE→REGISTRY`: `verify_change` does not advance phase when any command fails.
  - `ENGINE` gates: `archive_change` and `sync_specs` each block until the required phase is recorded.
  - `INFERENCE→REGISTRY`: `workflow_state` matches `transition_workflow` result after each transition.
  - `EVIDENCE`: multiple commands in one `verify_change` call write one record per command.
  - `INFERENCE`: `infer_phase_from_artifacts` and `workflow_state` are independently stable.
  - `VALIDATION`: `validate()` reports errors on `change_id` frontmatter mismatches.
  - Trace mode: `[TRACE]` output goes to stderr only and does not alter exit code.

### Documentation

- README updated for v0.23.0: `--trace` usage with example output, "Current Status" modernized, stale version reference removed.

## 0.22.0 - 2026-05-06

**Modular refactor — no module exceeds 500 lines (123 tests pass, 1 skipped)**

Split three monolithic files into focused sub-modules to comply with the 500-line hard limit.

- **`_workflow.py` → 10 sub-modules + thin aggregator:**
  - `_wf_artifacts.py` — frontmatter generation and parsing.
  - `_wf_templates.py` — template helpers, memory API, install-commands.
  - `_wf_validation.py` — structural validation and `init_project`.
  - `_wf_changeops.py` — change directory I/O, `create_change`, `archive_change`, `sync_specs`.
  - `_wf_evidence.py` — execution evidence recording and `verify_change`.
  - `_wf_discovery.py` — repository discovery and profile suggestion.
  - `_wf_registry.py` — `state.json` I/O, phase gate, transition logic.
  - `_wf_inference.py` — workflow state inference and `run_workflow`.
  - `_wf_engine.py` — `SDDWorkflow`, `WorkflowEngine`, `EngineStep`, `AutoStep`, `_auto_advance`.
  - `_wf_infra.py` — git hooks and CI templates.
  - `_workflow.py` reduced to a 28-line aggregator (`from ._wf_xxx import *`).
- **`_render.py` → `_render.py` + `_render_auto.py`:** `run_fast_demo`, `run_demo`, `_print_auto_step`, and `print_auto` moved to `_render_auto.py`; `_render.py` trimmed to 477 lines.
- **`tests/test_sdd.py` (2246 lines) → 7 focused test files:**
  - `test_core.py` — version, templates, profiles, validation, init.
  - `test_workflow.py` — E2E standard change, transitions, guard, hooks.
  - `test_verify.py` — `verify_change`, engine, matrix validation.
  - `test_inference.py` — state inference, auto-loop.
  - `test_execution_evidence.py` — evidence records, checksums, anti-hallucination.
  - `test_golden.py` — full lifecycle golden paths (success and failure).
  - `test_features.py` — install-commands, extensions, memory, discovery, dispatch.
- Circular import dependencies (registry ↔ changeops ↔ inference) resolved with function-level lazy imports.
- All 123 tests pass unchanged. No behavioral changes. Public API is unaffected.

## 0.21.0 - 2026-05-06

**Multi-agent Runner (123 tests pass, 1 skipped)**

New `_dispatch.py` module with a pluggable agent dispatcher interface.

- **`DispatchRequest`** — frozen dataclass: `agent`, `prompt`, `working_dir`, `timeout_seconds`.
- **`DispatchResult`** — frozen dataclass: `exit_code`, `stdout`, `stderr`, `elapsed_seconds`, `.success` property.
- **`ShellAgentDispatcher`** — runs any prompt as a shell command via `subprocess.run(shell=True)`. Handles timeouts and OS errors, returning a failed `DispatchResult` rather than raising.
- **`ClaudeCodeDispatcher`** — runs the `claude` CLI with `--print` for non-interactive automation. Returns exit_code=127 with a clear error message when `claude` is not on `PATH`.
- All four symbols re-exported from `ssd_core` public API and `ssd_core.cli`.

## 0.20.0 - 2026-05-06

**Scale Adaptivity (118 tests pass)**

New `suggest_profile()` function and `profile="auto"` support in `bootstrap_change()`.

- **`suggest_profile(title)`** — tokenizes the change title into whole words and scores against a keyword table to select the best profile: `quick` (hotfix/urgent), `bugfix` (fix/crash/regression), `refactor` (refactor/cleanup/restructure), `research` (research/spike/evaluate), `standard` (default). Ties are broken by specificity order.
- **`bootstrap_change(root, title, *, profile="auto")`** — accepts `profile="auto"` (now the default) which calls `suggest_profile(title)` internally before creating the scaffold.
- `_PROFILE_KEYWORDS` scoring table added to `_workflow.py` (private constant).

## 0.19.0 - 2026-05-06

**Brownfield Bootstrap (112 tests pass)**

New `discover_repository()` and `bootstrap_change()` API for onboarding existing codebases.

- **`discover_repository(root)`** — detects languages (`python`, `node`, `rust`, `go`, `java`) from manifest signal files; detects CI presence (GitHub Actions, GitLab CI, CircleCI, Jenkins, Travis); returns a `RepositoryInfo` frozen dataclass with `languages`, `test_command`, `has_ci`, `has_sdd`.
- **`bootstrap_change(root, title, *, profile)`** — slugifies *title* into a change-id and calls `create_change()`. Returns `(change_id, findings)`; returns an error Finding if `.sdd/` has not been initialized.
- **`RepositoryInfo`** — new frozen dataclass added to `_types.py` and re-exported from the public API.

## 0.18.0 - 2026-05-06

**Persistent Project Memory (106 tests pass)**

New `ssd-core memory show|add` subcommand and `append_memory` / `read_memory_entry` API.

- **`init_project()`** — now copies `memory/project.md` and `memory/decisions.md` templates into `.sdd/memory/` on first init.
- **`read_memory_entry(root, key)`** — reads `.sdd/memory/<key>.md` and returns its text (or `None`).
- **`append_memory(root, key, content)`** — appends a timestamped entry to the named memory file; returns error Findings on unknown key.
- **`print_memory(root, key)`** — CLI helper that pretty-prints one or all memory files.
- **`print_status()`** — now shows total memory word count in the project summary.
- **`validate_markdown_frontmatter()`** — now skips `.sdd/memory/` (free-form Markdown, no frontmatter required).
- **`_ensure_gitignore_entry(root, entry)`** — idempotently adds a path to `.gitignore`; used by `install_commands` with `scope="local"`.
- `MEMORY_KEYS`, `MEMORY_COPY_FILES` constants added to `_types.py`.

## 0.17.0 - 2026-05-06

**Extension System (100 tests pass)**

New `ssd-core extension install|list|remove` subcommand plus a Python lifecycle hook system.

- **`install_extension(root, path)`** — copies an extension source directory into `.sdd/extensions/<name>/`. Validates `manifest.json` against `sdd.extension.v1` schema before installing. Warns if the extension ships `hooks.py` without a `TRUSTED` marker.
- **`remove_extension(root, name)`** — deletes the installed extension directory; returns an error Finding if not installed.
- **`load_extensions(root)`** — discovers all installed extensions and returns `list[Extension]` dataclass instances.
- **`run_extension_hooks(root, hook_name, **kwargs)`** — calls `hook_name` on every *trusted* extension's `hooks.py`. Untrusted extensions are skipped with a warning (never auto-executes third-party code). Results are accumulated and returned as additional `Finding` items.
- **Trust model** — hooks require a `TRUSTED` marker file at `.sdd/extensions/<name>/TRUSTED`. The operator creates this manually after reviewing the hook code.
- **`on_verify` hook** — called at the end of `verify_change()`; can append Findings.
- **`on_guard` hook** — called at the end of `guard_repository()`; can append Findings.
- **New schema** — `extension.schema.json` added to `.sdd/schemas/` (required by `validate()`).
- **New directory** — `.sdd/extensions/` added to `REQUIRED_DIRECTORIES` and `EMPTY_STATE_DIRECTORIES`; created by `init_project()`.
- **CLI** — `ssd-core extension install <path>`, `ssd-core extension list`, `ssd-core extension remove <name>`.
- **Public API** — `Extension`, `load_extensions`, `install_extension`, `remove_extension`, `run_extension_hooks`, `print_extension_list` exported from `ssd_core`.

## 0.16.0 - 2026-05-06

**`install-commands` — AI command scaffolds with scope control (92 tests pass)**

New subcommand `ssd-core install-commands --integration <agent> [--scope repo|user|local]`
installs six conversational scaffold files into the agent-native command directory.

- **Three installation scopes:**
  - `repo` (default) — installs inside the project root, committed to VCS.
  - `user` — installs under the OS home directory (`~/<tool-dir>/`), global across all projects.
  - `local` — same on-disk path as `repo` but adds a `.gitignore` entry so the files are not committed.

- **Six integrations supported:** `claude-code`, `copilot`, `opencode`, `codex`, `gemini-cli`, `generic`.
  Each maps to the agent-native command directory for each scope (e.g. claude-code repo → `.claude/commands/`; user → `~/.claude/commands/`).

- **Six conversational scaffold files:** `sdd-propose.md`, `sdd-specify.md`, `sdd-design.md`,
  `sdd-tasks.md`, `sdd-verify.md`, `sdd-status.md`. Each asks clarifying questions before
  writing the artifact — spec-kit-style guided authoring rather than passive instruction dumps.

- **Idempotent:** second call skips files that already exist; custom local scaffolds are preserved.

- **`.gitignore` deduplication for `local` scope:** entry is written only once regardless of how many times the command is re-run.

- **New public API:** `install_commands()`, `list_available_integrations()`,
  `template_commands_root()`, `COMMAND_SCOPES` exported from `ssd_core`.

## 0.15.0 - 2026-05-06


Code review fixes — 8 issues found, all resolved (83 tests pass):

- **Critical: `NameError` on `ssd-core evidence`** — `hashlib` was not imported in `_render.py`. `print_evidence()` would crash with `NameError: name 'hashlib' is not defined` whenever a valid log file was present. Added `import hashlib` to `_render.py`.
- **Critical: `NameError` on `ssd-core transition` (success path)** — `workflow_registry_path` was missing from the `from ._workflow import (...)` block in `_render.py`. `print_transition()` crashed on the success path. Added `workflow_registry_path` to the import block.
- **Bug: `_pyproject_has_pytest` false-positive** — `[tool.setuptools]` in `pyproject.toml` was incorrectly treated as signal for pytest. A project using setuptools without pytest would trigger `python -m pytest` discovery even if pytest was not installed. Removed the `[tool.setuptools]` check.
- **Warning: overbroad `str.replace("not-run", "pass")`** — `append_execution_evidence_to_verification()` replaced every occurrence of `"not-run"` in the document, including user prose that happened to contain that term. Replaced with `re.sub(r"(\|\s*)not-run(\s*\|)", ...)` so only table cell values are substituted.
- **Minor: duplicate code block in `_auto_advance`** — the `if target == SYNC_SPECS or target == ARCHIVE:` branch and its `else` were identical Python code. Collapsed into a single block with a clarifying comment.
- **Minor: `VERIFICATION_EVIDENCE_BLOCKERS` typed as mutable list** — changed to `frozenset[str]` to communicate intent and prevent accidental mutation.
- **Minor: magic number `25` in `record_workflow_state`** — extracted to `_MAX_HISTORY_ENTRIES = 25` module-level constant.
- **Minor: non-deterministic test fixture path** — `test_init_project_creates_valid_foundation_in_new_root` used a fixed path `"init-fixture"` instead of a uuid-suffixed path like every other test. Fixed to `f"init-fixture-{uuid.uuid4().hex}"`.

## 0.14.0 - 2026-05-06

Failure golden path — the system proof's counterpart (83 tests total):

- **`test_golden_path_failure_system_stays_consistent`**: the same end-to-end standard-profile lifecycle as the success golden path, but the verification command **fails** (exit 7). Proves the system stays perfectly consistent under failure: phase stays at TASK, failure evidence is recorded with valid SHA-256 checksum, no archive or spec sync happens, change directory still exists. Then the agent retries with a passing command — verify succeeds, both the failure AND retry records exist in the evidence log, auto-loop closes the change, and `guard --strict-state --require-execution-evidence` passes. If both golden path tests pass, the system is safe under success AND failure.

## 0.13.0 - 2026-05-06

Golden path end-to-end test + evidence edge-case coverage (82 tests total):

- **`test_golden_path_idea_to_archive_with_execution_evidence`**: the definitive system proof. A standard-profile change goes from idea to archived in a single test: `init` → `create_change` → agent fills proposal → auto-loop advances through SPECIFY/DESIGN → agent fills tasks → auto-loop pauses at TASK (verify gate) → `verify_change` with real command execution (sentinel string in stdout) → evidence persisted with valid SHA-256 checksum → agent fills archive record → auto-loop drives through ARCHIVE_RECORD/SYNC_SPECS to ARCHIVED → `guard --strict-state --require-execution-evidence` passes on the archive → change directory is gone, living spec synced, archive exists. If this test passes, the system works.
- **`test_execution_allows_empty_stdout_for_successful_command`**: documents that commands producing zero stdout (e.g. `true`, `test -f file`) are valid evidence. Evidence strength comes from `exit_code` + persisted log + SHA-256 checksum chain — not from output volume.

## 0.12.0 - 2026-05-06

Anti-hallucination lie detection tests — three narrative tests that prove the system's core guarantee (80 tests total):

- **`test_require_command_flag_blocks_verify_when_no_commands_given`**: asserts that `verify_change(..., require_command=True)` with an empty command list returns an error and leaves the change at TASK. This is the enforcement path for CI policy (`ssd-core verify --require-command`): an agent cannot skip execution evidence by simply omitting `--command`.
- **`test_guard_require_evidence_catches_verify_without_command`**: the core anti-hallucination test. Agent manually writes a legitimate-looking `verification.md` (correct status, no placeholders, passing matrix row) and calls `verify_change` without any commands — which succeeds, as manual evidence is accepted. Then `guard --require-execution-evidence` blocks with an evidence error. This is the "I ran the tests" lie caught by governance: the claim has no cryptographic proof.
- **`test_partial_command_failure_blocks_verify_but_records_all_evidence`**: when multiple commands are given, ALL are executed and ALL are recorded in the evidence log — governance does not stop at the first pass. A single failure blocks verify. Asserts that both passing and failing records exist in the JSONL, with correct `passed` and `exit_code` values. This prevents the lie: "the first test passed so the change is verified" while a later, critical test was silently failing.

## 0.11.0 - 2026-05-06

Execution truth hardening — three black-box behavioral tests close the last QA gap around evidence integrity (77 tests total):

- **`test_execution_evidence_records_exact_exit_code`**: asserts that `rec["exit_code"]` equals the real process exit code (e.g. `sys.exit(42)` → `exit_code == 42`). Previous tests only checked `passed=False`; this proves the raw value is captured correctly.
- **`test_execution_evidence_log_captures_stdout`**: runs a command that prints a known sentinel string, then asserts the string appears verbatim in the persisted log file and that the log's SHA-256 checksum is still valid after reading. Proves the full stdout → log → checksum chain.
- **`test_execution_evidence_log_captures_stderr`**: same for stderr. Proves stderr is captured separately from stdout and stored in the same log.

These tests are black-box behavioral assertions — they drive the public API (`verify_change`, `execution_evidence_records`) and inspect only persisted artifacts, with no coupling to internal implementation.

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
