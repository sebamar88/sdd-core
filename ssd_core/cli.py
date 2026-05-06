from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Re-export the entire public surface through the sub-modules so that
# `from .cli import (VERSION, Finding, ...)` in __init__.py keeps working.
from ._types import *  # noqa: F401, F403
from ._workflow import *  # noqa: F401, F403
from ._render import *  # noqa: F401, F403

# Private names with leading underscore are not exported by *, import explicitly.
from ._types import _PHASE_ICON  # noqa: F401
from ._workflow import _PHASE_ARTIFACT_FILE, _auto_advance  # noqa: F401
from ._workflow import _CI_TEMPLATES  # noqa: F401



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SDD-Core utility")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate_parser = subcommands.add_parser("validate", help="validate SDD-Core repository artifacts")
    validate_parser.add_argument(
        "--root",
        default=".",
        help="repository root to validate; defaults to the current directory",
    )

    subcommands.add_parser("version", help="show SSD-Core version")

    demo_parser = subcommands.add_parser(
        "demo",
        help="run an annotated Golden Path walkthrough in a temporary directory",
    )
    demo_parser.add_argument(
        "--fast",
        action="store_true",
        help="run the 30-second anti-hallucination proof instead of the full walkthrough",
    )

    auto_parser = subcommands.add_parser(
        "auto",
        help="advance a change: execute all ready steps, stop on human-work phases",
    )
    auto_parser.add_argument("change_id", help="kebab-case change identifier")
    auto_parser.add_argument(
        "--loop",
        action="store_true",
        help="drain all auto-executable steps in sequence; stop at the first phase requiring human input",
    )
    auto_parser.add_argument(
        "--verify-with",
        action="append",
        default=[],
        metavar="CMD",
        help="verification command to run automatically when the loop reaches the verify phase; may be repeated",
    )
    auto_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    init_parser = subcommands.add_parser("init", help="initialize SDD-Core artifacts in a repository")
    init_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    status_parser = subcommands.add_parser("status", help="show SDD-Core repository status")
    status_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    check_parser = subcommands.add_parser("check", help="check whether an SDD-Core change is ready to archive")
    check_parser.add_argument("change_id", help="kebab-case change identifier")
    check_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    archive_parser = subcommands.add_parser("archive", help="archive a verified SDD-Core change")
    archive_parser.add_argument("change_id", help="kebab-case change identifier")
    archive_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    sync_parser = subcommands.add_parser("sync-specs", help="sync a verified change delta into living specs")
    sync_parser.add_argument("change_id", help="kebab-case change identifier")
    sync_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    new_parser = subcommands.add_parser("new", help="create a new SDD-Core change artifact set")
    new_parser.add_argument("change_id", help="kebab-case change identifier")
    new_parser.add_argument(
        "--profile",
        default="standard",
        choices=REQUIRED_PROFILES,
        help="profile to use for the change; defaults to standard",
    )
    new_parser.add_argument(
        "--title",
        help="human-readable change intent for the proposal",
    )
    new_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    run_parser = subcommands.add_parser("run", help="run the SDD-Core workflow gate for a change")
    run_parser.add_argument("change_id", help="kebab-case change identifier")
    run_parser.add_argument(
        "--profile",
        default="standard",
        choices=REQUIRED_PROFILES,
        help="profile to use when creating a missing change; defaults to standard",
    )
    run_parser.add_argument(
        "--title",
        help="human-readable change intent when creating a missing change",
    )
    run_parser.add_argument(
        "--no-create",
        action="store_true",
        help="inspect the workflow state without creating a missing change",
    )
    run_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    transition_parser = subcommands.add_parser("transition", help="record an enforced workflow phase transition")
    transition_parser.add_argument("change_id", help="kebab-case change identifier")
    transition_parser.add_argument(
        "phase",
        choices=[
            WorkflowPhase.PROPOSE.value,
            WorkflowPhase.SPECIFY.value,
            WorkflowPhase.DESIGN.value,
            WorkflowPhase.TASK.value,
            WorkflowPhase.CRITIQUE.value,
            WorkflowPhase.ARCHIVE_RECORD.value,
            WorkflowPhase.SYNC_SPECS.value,
            WorkflowPhase.ARCHIVE.value,
        ],
        help="target phase to record after artifacts prove readiness; use 'ssd-core verify' to record the verify phase",
    )
    transition_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    log_parser = subcommands.add_parser("log", help="show the recorded command history for a change")
    log_parser.add_argument("change_id", help="kebab-case change identifier")
    log_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    verify_parser = subcommands.add_parser("verify", help="validate evidence quality and record the verify phase")
    verify_parser.add_argument("change_id", help="kebab-case change identifier")
    verify_parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="verification command to execute from the repository root; may be repeated",
    )
    verify_parser.add_argument(
        "--discover",
        action="store_true",
        help="auto-discover the project's test runner (pytest, npm test, cargo test, …) and run it",
    )
    verify_parser.add_argument(
        "--require-command",
        action="store_true",
        help="fail unless at least one --command is provided",
    )
    verify_parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="per-command timeout in seconds; defaults to 120",
    )
    verify_parser.add_argument(
        "--commands-file",
        default=None,
        metavar="PATH",
        help="path to a text file containing one verification command per line; blank lines and lines starting with '#' are ignored",
    )
    verify_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    evidence_parser = subcommands.add_parser(
        "evidence",
        help="show execution evidence records for a change",
    )
    evidence_parser.add_argument("change_id", help="kebab-case change identifier")
    evidence_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    pr_check_parser = subcommands.add_parser(
        "pr-check",
        help="output a PR-ready governance report and exit 0 only if the change is safe to merge",
    )
    pr_check_parser.add_argument("change_id", help="kebab-case change identifier")
    pr_check_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    phase_parser = subcommands.add_parser("phase", help="show declared and inferred workflow phase for a change")
    phase_parser.add_argument("change_id", help="kebab-case change identifier")
    phase_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    guard_parser = subcommands.add_parser("guard", help="enforce SSD-Core repository governance for hooks or CI")
    guard_parser.add_argument(
        "--require-active-change",
        action="store_true",
        help="fail when no active .sdd change exists",
    )
    guard_parser.add_argument(
        "--strict-state",
        action="store_true",
        help="fail when .sdd/state.json is missing entries or artifact checksums are stale",
    )
    guard_parser.add_argument(
        "--require-execution-evidence",
        action="store_true",
        help="fail verified or archived changes without passing .sdd/evidence execution records",
    )
    guard_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    hooks_parser = subcommands.add_parser("install-hooks", help="install SSD-Core git enforcement hooks")
    hooks_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    ci_parser = subcommands.add_parser(
        "ci-template",
        help="write a CI workflow template that runs `ssd-core guard` on every push",
    )
    ci_parser.add_argument(
        "--type",
        default="github-actions",
        choices=sorted(_CI_TEMPLATES),
        help="CI provider template to generate; defaults to github-actions",
    )
    ci_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        root = Path(args.root).resolve()
        return print_findings(root, validate(root))

    if args.command == "version":
        print(f"SSD-Core {VERSION}")
        return 0

    if args.command == "demo":
        if getattr(args, "fast", False):
            return run_fast_demo()
        return run_demo()

    if args.command == "auto":
        root = Path(args.root).resolve()
        return print_auto(root, args.change_id, loop=args.loop, verify_commands=args.verify_with or None)

    if args.command == "init":
        root = Path(args.root).resolve()
        findings = init_project(root)
        if findings:
            return print_findings(root, findings)
        return print_findings(root, validate(root))

    if args.command == "status":
        root = Path(args.root).resolve()
        return print_status(root)

    if args.command == "check":
        root = Path(args.root).resolve()
        return print_check(root, args.change_id)

    if args.command == "archive":
        root = Path(args.root).resolve()
        findings = archive_change(root, args.change_id)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "sync-specs":
        root = Path(args.root).resolve()
        findings = sync_specs(root, args.change_id)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "new":
        root = Path(args.root).resolve()
        findings = create_change(root, args.change_id, args.profile, args.title)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "run":
        root = Path(args.root).resolve()
        state = run_workflow(root, args.change_id, args.profile, args.title, create=not args.no_create)
        return print_workflow(root, state)

    if args.command == "transition":
        root = Path(args.root).resolve()
        state = transition_workflow(root, args.change_id, WorkflowPhase(args.phase))
        return print_transition(root, state)

    if args.command == "log":
        root = Path(args.root).resolve()
        return print_log(root, args.change_id)

    if args.command == "verify":
        root = Path(args.root).resolve()
        commands: list[str] = list(args.command)
        if args.discover:
            discovered = discover_test_command(root)
            if discovered is None:
                print(_yellow("⚠") + " --discover: no test runner detected; add --command explicitly")
            else:
                print(_cyan("→") + f" Discovered test runner: {_bold(discovered)}")
                if discovered not in commands:
                    commands.append(discovered)
        if args.commands_file:
            cf_path = Path(args.commands_file)
            if not cf_path.is_file():
                print(_red("\u2717") + f" --commands-file not found: {cf_path}")
                return 1
            for raw in cf_path.read_text(encoding="utf-8").splitlines():
                stripped = raw.strip()
                if stripped and not stripped.startswith("#") and stripped not in commands:
                    commands.append(stripped)
        findings = verify_change(
            root,
            args.change_id,
            commands,
            require_command=args.require_command,
            timeout_seconds=args.timeout,
        )
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "ci-template":
        root = Path(args.root).resolve()
        findings = write_ci_template(root, args.type)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "phase":
        root = Path(args.root).resolve()
        return print_phase(root, args.change_id)

    if args.command == "guard":
        root = Path(args.root).resolve()
        return print_guard(
            root,
            require_active_change=args.require_active_change,
            strict_state=args.strict_state,
            require_execution_evidence=args.require_execution_evidence,
        )

    if args.command == "install-hooks":
        root = Path(args.root).resolve()
        findings = install_hooks(root)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "evidence":
        root = Path(args.root).resolve()
        return print_evidence(root, args.change_id)

    if args.command == "pr-check":
        root = Path(args.root).resolve()
        return print_pr_check(root, args.change_id)

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
