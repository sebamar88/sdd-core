"""Auto-advance loop, demo runners, and ``print_auto``.

Split from _render.py to keep each file under 500 lines.
Depends on _types and _workflow; no circular imports.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from ._types import (
    Finding,
    WorkflowPhase,
    SDD_DIR,
    _PHASE_ICON,
    _green,
    _yellow,
    _red,
    _cyan,
    _bold,
    _dim,
)
from ._workflow import (
    init_project,
    create_change,
    archive_change,
    change_directory,
    transition_workflow,
    set_frontmatter_value,
    verify_change,
    validate,
    discover_test_command,
    _auto_advance,
    _PHASE_ARTIFACT_FILE,
    AutoStep,
)


def run_fast_demo() -> int:
    """30-second proof: an agent says 'done' — governance says 'prove it'."""
    change_id = "agent-claims-done"
    profile = "quick"

    def line(msg: str) -> None:
        print(msg)

    with tempfile.TemporaryDirectory(prefix="sdd-fast-") as tmpdir:
        root = Path(tmpdir)

        print(_bold("ProofKit — Proof: agent can't lie about being done"))
        print(_dim("=" * 54))
        print("")
        print("Scenario: an AI agent finishes coding and calls 'proofkit archive'.")
        print("Watch what happens at each attempt.")
        print("")

        # Setup silently
        init_project(root)
        create_change(root, change_id, profile, "Agent claims to be done")

        # Attempt 1: archive before doing any work
        line(_bold("\nAttempt 1") + "  Agent calls: " + _cyan(f"proofkit archive {change_id}"))
        findings = archive_change(root, change_id)
        if not findings:
            print(_red("UNEXPECTED: archive should have been blocked"))
            return 1
        print(_red("  \u2717 BLOCKED:") + " " + findings[0].message)

        # Attempt 2: fill proposal, advance to task, try to archive
        change_dir = change_directory(root, change_id)
        proposal_path = change_dir / "proposal.md"
        text = proposal_path.read_text(encoding="utf-8")
        text = set_frontmatter_value(text, "status", "ready")
        text = text.replace("- Define the intended change.", "- Return 401 on bad credentials.")
        proposal_path.write_text(text, encoding="utf-8")

        tasks_path = change_dir / "tasks.md"
        text = tasks_path.read_text(encoding="utf-8")
        text = text.replace("- [ ]", "- [x]")
        text = set_frontmatter_value(text, "status", "ready")
        tasks_path.write_text(text, encoding="utf-8")

        transition_workflow(root, change_id, WorkflowPhase.PROPOSE)
        transition_workflow(root, change_id, WorkflowPhase.TASK)

        line(_bold("\nAttempt 2") + "  Agent marks tasks done, calls: " + _cyan(f"proofkit archive {change_id}"))
        findings = archive_change(root, change_id)
        if not findings:
            print(_red("UNEXPECTED: archive should have been blocked"))
            return 1
        print(_red("  \u2717 BLOCKED:") + " " + findings[0].message)

        # Attempt 3: verify with real command
        line(_bold("\nAttempt 3") + "  Agent provides evidence: " + _cyan(f"proofkit verify {change_id} --command 'echo auth-tests-pass'"))
        v_findings = verify_change(root, change_id, ["echo auth-tests-pass"])
        if v_findings:
            for f in v_findings:
                print(_red("  \u2717") + " " + f.format(root))
            return 1
        print(_green("  \u2714 Evidence recorded") + " — command output checksummed and stored")

        # Now advance and archive via auto --loop
        line(_bold("\nAttempt 4") + "  Engine closes it: " + _cyan(f"proofkit auto {change_id} --loop"))
        rc = print_auto(root, change_id, loop=True)
        if rc != 0:
            return 1

        print("")
        print(_dim("=" * 54))
        print(_bold("Result:"))
        print(f"  {_red(chr(0x2717))} 3 blocked attempts  — the agent could not skip governance")
        print(f"  {_green(chr(0x2714))} 1 successful archive — only after checksummed proof")
        print("")
        print(_bold("What was enforced:"))
        print(f"  phase order       : archive required verify first")
        print(f"  evidence quality  : verification.md could not contain placeholders")
        print(f"  execution proof   : output log + sha256 stored before phase recorded")
        print("")
        print(f"  {_cyan('proofkit evidence ' + change_id)}  \u2190 inspect what was recorded")
    return 0


def run_demo() -> int:
    """Run an annotated Golden Path demo in a temporary directory."""

    def section(label: str) -> None:
        print(f"\n{_dim('──')} {_bold(label)}")

    def ok(msg: str) -> None:
        print(f"   {_green(chr(0x2713))} {msg}")

    def fail(what: str, findings_: list[Finding], root_: Path) -> int:
        print(f"   {_red(chr(0x2717))} {what}")
        for f in findings_:
            print(f"     {_red(chr(0x2192))} {f.format(root_)}")
        return 1

    change_id = "demo-harden-login"
    profile = "quick"
    title = "Harden login error handling"

    with tempfile.TemporaryDirectory(prefix="sdd-demo-") as tmpdir:
        root = Path(tmpdir)

        print(_bold("ProofKit — AI Development Governance Engine"))
        print(_dim("=" * 52))
        print("Problem: AI agents produce code but lose intent, skip verification,")
        print("         and claim completion without evidence.")
        print("Solution: a governance layer that enforces the protocol automatically.")
        print(f"\n{_dim('Temp root:')} {_dim(str(root))}")

        section("proofkit init  (one-time repository setup)")
        findings = init_project(root)
        if findings:
            return fail("init failed", findings, root)
        ok(f"Initialized {SDD_DIR}/ — adapters, agents, profiles, schemas, skills, specs")

        section(f"proofkit new {change_id} --profile quick --title '{title}'")
        findings = create_change(root, change_id, profile, title)
        if findings:
            return fail("create_change failed", findings, root)
        ok(f"Created {SDD_DIR}/changes/{change_id}/ — proposal.md, tasks.md, verification.md")

        section(f"proofkit auto {change_id} --loop  (engine runs; pauses for human input)")
        result = _auto_advance(root, change_id)
        print(f"   \u2192 phase: {result.step.phase.value}")
        if result.needs_human_work:
            change_dir = change_directory(root, change_id)
            artifact_file = _PHASE_ARTIFACT_FILE.get(result.step.phase, "proposal.md")
            artifact_path = (change_dir / artifact_file).relative_to(root).as_posix()
            print(f"   \u2192 Engine paused. Needs human input.")
            print(f"     Edit: {artifact_path}")

        section("Agent fills proposal.md \u2192 status: ready  (simulated)")
        change_dir = change_directory(root, change_id)
        proposal_path = change_dir / "proposal.md"
        text = proposal_path.read_text(encoding="utf-8")
        text = set_frontmatter_value(text, "status", "ready")
        text = text.replace(
            "- Define the intended change.",
            "- Reject weak error codes; return structured error objects.",
        )
        proposal_path.write_text(text, encoding="utf-8")
        ok("proposal.md: intent recorded, status \u2192 ready")

        section(f"proofkit auto {change_id} --loop  (engine resumes after human edit)")
        loop_steps = 0
        while True:
            r = _auto_advance(root, change_id)
            if r.executed_command:
                print(f"   \u2192 Executed: {r.executed_command}")
                loop_steps += 1
            if r.needs_human_work or r.step.is_complete or r.step.is_blocked or not r.executed_command:
                break
        print(f"   \u2192 phase: {r.step.phase.value} ({loop_steps} step(s) executed)")
        if r.needs_human_work:
            artifact_file = _PHASE_ARTIFACT_FILE.get(r.step.phase, "tasks.md")
            artifact_path = (change_dir / artifact_file).relative_to(root).as_posix()
            print(f"   \u2192 Engine paused. Needs human input.")
            print(f"     Edit: {artifact_path}")

        section("Agent closes tasks in tasks.md \u2192 status: ready  (simulated)")
        tasks_path = change_dir / "tasks.md"
        text = tasks_path.read_text(encoding="utf-8")
        text = text.replace("- [ ]", "- [x]")
        text = text.replace(
            "T-001 Define the first concrete task.",
            "T-001 Return structured error object on login failure.",
        )
        text = set_frontmatter_value(text, "status", "ready")
        tasks_path.write_text(text, encoding="utf-8")
        ok("tasks.md: T-001 closed, status \u2192 ready")

        section(f"proofkit auto {change_id} --loop  (advances to verify, cannot skip it)")
        loop_steps = 0
        while True:
            r = _auto_advance(root, change_id)
            if r.executed_command:
                print(f"   \u2192 Executed: {r.executed_command}")
                loop_steps += 1
            if r.needs_human_work or r.step.is_complete or r.step.is_blocked or not r.executed_command:
                break
        print(f"   \u2192 phase: {r.step.phase.value} ({loop_steps} step(s) executed)")
        if r.step.phase == WorkflowPhase.VERIFY:
            print("   \u2192 Engine paused. Verification requires a real command.")
            print(f"     Run: proofkit verify {change_id} --command '<your-test-command>'")

        section(f"proofkit verify {change_id} --command 'echo tests-pass'")
        print(f"   {_dim('(captures stdout/stderr, SHA-256 checksums output log, records timing)')}")
        findings = verify_change(root, change_id, ["echo tests-pass"])
        if findings:
            return fail("verify failed", findings, root)
        ok(f"Command executed; output stored \u2192 {SDD_DIR}/evidence/<id>.log")
        ok("verification.md updated automatically \u2192 status: verified")
        ok(f"Phase recorded in {SDD_DIR}/state.json \u2192 verify")

        section(f"proofkit auto {change_id} --loop  (engine closes the change)")
        loop_steps = 0
        while True:
            r = _auto_advance(root, change_id)
            if r.executed_command:
                print(f"   \u2192 Executed: {r.executed_command}")
                loop_steps += 1
            if r.needs_human_work or r.step.is_complete or r.step.is_blocked or not r.executed_command:
                break
        if r.step.is_complete:
            archived = next(p for p in (root / SDD_DIR / "archive").iterdir() if p.is_dir())
            ok(f"Change closed \u2192 {SDD_DIR}/archive/{archived.name}/  ({loop_steps} step(s))")
        else:
            return fail("expected archived", r.step.blocking_findings, root)

        section("proofkit validate  (full repository integrity check)")
        val_findings = [f for f in validate(root) if f.severity == "error"]
        if val_findings:
            return fail("validate failed", val_findings, root)
        ok("Repository governance passed — zero errors")

    print()
    print(_dim("=" * 52))
    print(_bold("Demo complete.") + " Temp directory cleaned up.")
    print()
    print(_bold("What the engine prevented:"))
    print(f"  {_red(chr(0x2192))} Hallucinated completion — archive required checksummed evidence")
    print(f"  {_red(chr(0x2192))} Phase skipping — ALLOWED_TRANSITIONS enforced every step")
    print(f"  {_red(chr(0x2192))} Stale state — state.json required before gated commands ran")
    print(f"  {_red(chr(0x2192))} Ungoverned commits — guard + install-hooks can enforce this in CI")
    print()
    print(_bold("Next:"))
    print(f"  {_cyan('proofkit init --root <your-repo>')}")
    print(f"  {_cyan('proofkit auto <change-id> --loop')}")
    print(f"  {_cyan('proofkit ci-template --root <your-repo>')}")
    return 0


def _print_auto_step(root: Path, change_id: str, result: "AutoStep") -> int:
    """Render a single AutoStep result to stdout. Returns exit code."""
    step = result.step
    icon = _PHASE_ICON.get(step.phase.value, " ")

    if result.executed_command:
        print(_cyan("\u2192") + " Executed: " + _bold(result.executed_command))

    if step.phase == WorkflowPhase.ARCHIVED:
        print(_green(icon) + " " + _bold(f"phase: {step.phase.value}"))
        print("  " + _green("Change is complete (archived)."))
        return 0

    if step.phase == WorkflowPhase.NOT_STARTED:
        print(_dim(icon) + f" phase: {step.phase.value}")
        print(f"  {step.next_action}")
        return 0

    if step.is_blocked:
        print(_red(icon) + " " + _bold(f"phase: {step.phase.value}") + " " + _red("[BLOCKED]"))
        for f in step.blocking_findings:
            print("  " + _red("\u2717") + " " + f.format(root))
        return 1

    if step.phase == WorkflowPhase.VERIFY:
        print(_yellow(icon) + " " + _bold(f"phase: {step.phase.value}") + " " + _yellow("[needs command]"))
        print(f"  {step.next_action}")
        print(f"  " + _cyan(f"Run: proofkit verify {change_id} --command '<your-test-command>'"))
        discovered = discover_test_command(root)
        if discovered:
            print(f"  " + _green(f"Discovered runner: proofkit verify {change_id} --command '{discovered}'"))
        return 0

    artifact_file = _PHASE_ARTIFACT_FILE.get(step.phase)
    if artifact_file:
        change_dir = change_directory(root, change_id)
        artifact_path = (change_dir / artifact_file).relative_to(root).as_posix()
        print(_yellow(icon) + " " + _bold(f"phase: {step.phase.value}") + " " + _yellow("[needs edit]"))
        print(f"  {step.next_action}")
        print(f"  " + _cyan(f"Edit: {artifact_path}"))
        print(f"  Re-run " + _dim(f"proofkit auto {change_id}") + " when done.")
        return 0

    print(_cyan(icon) + " " + _bold(f"phase: {step.phase.value}"))
    print(f"  {step.next_action}")
    if step.suggested_command:
        print("  " + _cyan(f"Run: {step.suggested_command}"))
    return 0


def print_auto(
    root: Path,
    change_id: str,
    *,
    loop: bool = False,
    verify_commands: list[str] | None = None,
) -> int:
    """Advance *change_id* and print the result."""
    if not loop:
        return _print_auto_step(root, change_id, _auto_advance(root, change_id))

    print(_bold(f"ProofKit auto loop: {change_id}"))
    print(_dim("-" * 44))
    steps_taken = 0
    result = _auto_advance(root, change_id)  # ensure defined
    while True:
        result = _auto_advance(root, change_id)
        if (
            result.needs_human_work
            and result.step.phase == WorkflowPhase.VERIFY
            and verify_commands
        ):
            print(_cyan("\u2192") + f" Auto-verifying with: {_bold(', '.join(verify_commands))}")
            v_findings = verify_change(root, change_id, verify_commands)
            if v_findings:
                print(_red("\u2717") + " " + _bold("verify failed:"))
                for f in v_findings:
                    print("  " + _red("\u2717") + " " + f.format(root))
                print(_dim("-" * 44))
                print(f"Auto loop stopped. {_bold(str(steps_taken))} step(s) executed.")
                return 1
            steps_taken += 1
            print(_green("\u2714") + f" Verification recorded: {_bold(change_id)}")
            continue

        rc = _print_auto_step(root, change_id, result)
        if result.executed_command:
            steps_taken += 1
        if rc != 0 or result.step.is_complete or result.needs_human_work or not result.executed_command:
            break
    print(_dim("-" * 44))
    print(f"Auto loop finished. {_bold(str(steps_taken))} step(s) executed.")
    return 0 if not result.step.is_blocked else 1
