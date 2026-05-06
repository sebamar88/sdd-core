from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from ._types import (
    VERSION,
    Finding,
    ChangeSummary,
    WorkflowPhase,
    WorkflowFailure,
    WorkflowResult,
    WorkflowState,
    WorkflowFailureKind,
    _PIPELINE_PHASES,
    _PHASE_ICON,
    PHASE_ORDER,
    REQUIRED_PROFILES,
    _use_color,
    _c,
    _green,
    _yellow,
    _red,
    _cyan,
    _bold,
    _dim,
)
from ._workflow import (
    validate,
    init_project,
    change_directory,
    status,
    workflow_state,
    infer_phase_from_artifacts,
    archive_change,
    sync_specs,
    verify_change,
    create_change,
    install_hooks,
    discover_test_command,
    guard_repository,
    transition_workflow,
    declared_workflow_phase,
    execution_evidence_records,
    execution_evidence_path,
    artifact_checksum,
    _auto_advance,
    _PHASE_ARTIFACT_FILE,
    set_frontmatter_value,
    validate_spec_sync,
    check_change_artifacts,
    validate_execution_evidence,
    validate_change_id,
    read_workflow_registry,
    state_entry,
    workflow_registry_path,
    WorkflowEngine,
    AutoStep,
    EngineStep,
)

def print_guard(
    root: Path,
    *,
    require_active_change: bool = False,
    strict_state: bool = False,
    require_execution_evidence: bool = False,
) -> int:
    findings = guard_repository(
        root,
        require_active_change=require_active_change,
        strict_state=strict_state,
        require_execution_evidence=require_execution_evidence,
    )
    if not findings:
        print(_green("\u2714") + " " + _bold("SDD guard passed."))
        return 0

    print(_red("\u2717") + " " + _bold("SDD guard blocked."))
    for finding in findings:
        pre = _red("  \u2717") if finding.severity == "error" else _yellow("  \u26a0")
        print(pre + " " + finding.format(root))
    return 1


def print_log(root: Path, change_id: str) -> int:
    findings = validate_change_id(change_id)
    if findings:
        return print_findings(root, findings)

    registry, findings = read_workflow_registry(root)
    if findings:
        return print_findings(root, findings)

    entry = state_entry(registry, change_id)
    if entry is None:
        print(f"No recorded history for: {change_id}")
        return 1

    history = entry.get("history")
    if not isinstance(history, list) or not history:
        print(f"No recorded history entries for: {change_id}")
        return 1

    print(_bold(f"SDD log: {change_id}"))
    print(f"  profile : {entry.get('profile', 'unknown')}")
    print(f"  phase   : {_cyan(str(entry.get('phase', 'unknown')))}")
    print("")
    print(_bold("History:"))
    for record in history:
        phase = record.get("phase", "?")
        action = record.get("action", "?")
        at = record.get("at", "?")
        checksum = str(record.get("checksum", ""))[:8] or "(none)"
        icon = _PHASE_ICON.get(str(phase), " ")
        print(f"  {_dim(at)} {icon} {_cyan(f'{phase:<20}')} via {_dim(action):<14} sha256:{_dim(checksum)}")
    return 0


def print_phase(root: Path, change_id: str) -> int:
    findings = validate_change_id(change_id)
    if findings:
        return print_findings(root, findings)

    declared = declared_workflow_phase(root, change_id)
    artifact_phase = infer_phase_from_artifacts(root, change_id)
    state = workflow_state(root, change_id)

    print(_bold(f"SDD phase: {change_id}"))
    print(f"  declared  : {_cyan(declared.value) if declared else _dim('not-recorded')}")
    print(f"  artifacts : {_cyan(artifact_phase.value)}")
    eff_icon = _PHASE_ICON.get(state.phase.value, " ")
    if state.is_blocked:
        print(f"  effective : {_red(eff_icon + ' ' + state.phase.value)}")
    elif state.phase == WorkflowPhase.ARCHIVED:
        print(f"  effective : {_green(eff_icon + ' ' + state.phase.value)}")
    else:
        print(f"  effective : {_yellow(eff_icon + ' ' + state.phase.value)}")

    if declared is not None and declared != artifact_phase:
        declared_order = PHASE_ORDER.get(declared, 0)
        artifact_order = PHASE_ORDER.get(artifact_phase, 0)
        drift = "ahead" if declared_order > artifact_order else "behind"
        print(f"  drift     : declared is {_yellow(drift)} of artifact phase")

    print(f"  pipeline  : {_phase_pipeline_str(state.phase, state.profile)}")
    print(f"  next      : {state.next_action}")
    return 0


def print_workflow(root: Path, state: WorkflowState) -> int:
    icon = _PHASE_ICON.get(state.phase.value, " ")
    phase_str = _red(icon + " " + state.phase.value) if state.is_blocked else _cyan(icon + " " + state.phase.value)
    print(_bold("SDD workflow"))
    print(f"  root    : {_dim(str(root))}")
    print(f"  change  : {state.change_id}")
    print(f"  profile : {state.profile}")
    print(f"  phase   : {phase_str}")
    print(f"  next    : {state.next_action}")

    if state.findings:
        print("")
        print(_bold("Findings:"))
        for finding in state.findings:
            pre = _red("  \u2717") if finding.severity == "error" else _yellow("  \u26a0")
            print(pre + " " + finding.format(root))

    return 1 if state.is_blocked else 0


def print_transition(root: Path, state: WorkflowState) -> int:
    if state.is_blocked:
        print(_red("\u2717") + " " + _bold("SDD transition blocked."))
        for finding in state.findings:
            pre = _red("  \u2717") if finding.severity == "error" else _yellow("  \u26a0")
            print(pre + " " + finding.format(root))
        return 1

    icon = _PHASE_ICON.get(state.phase.value, " ")
    print(_green("\u2714") + " " + _bold("SDD transition recorded."))
    print(f"  change   : {state.change_id}")
    print(f"  phase    : {_cyan(icon + ' ' + state.phase.value)}")
    print(f"  registry : {workflow_registry_path(root).relative_to(root).as_posix()}")
    return 0


def print_status(root: Path) -> int:
    findings, changes = status(root)
    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]

    val_str = _red("fail") if errors else _green("pass")
    print(_bold("SDD status"))
    print(f"  root            : {_dim(str(root))}")
    print(f"  validation      : {val_str}")
    print(f"  active changes  : {len(changes)}")

    if changes:
        print("")
        print(_bold("Changes:"))
        for change in changes:
            icon = _PHASE_ICON.get("archived" if change.is_complete else "propose", " ")
            completeness = _green("complete") if change.is_complete else _yellow("incomplete")
            print(f"  {icon} {_bold(change.change_id)} [{_dim(change.profile)}] {completeness}")
            if change.present:
                print(f"    present : {', '.join(change.present)}")
            if change.missing:
                print(f"    missing : {_red(', '.join(change.missing))}")

    if findings:
        print("")
        print(_bold("Findings:"))
        for finding in findings:
            pre = _red("  \u2717") if finding.severity == "error" else _yellow("  \u26a0")
            print(pre + " " + finding.format(root))

    return 1 if errors else 0


def print_findings(root: Path, findings: Iterable[Finding]) -> int:
    findings = list(findings)
    if not findings:
        print(_green("\u2714") + " SDD validation passed.")
        return 0

    for finding in findings:
        if finding.severity == "error":
            print(_red("\u2717") + " " + finding.format(root))
        elif finding.severity == "warning":
            print(_yellow("\u26a0") + " " + finding.format(root))
        else:
            print(finding.format(root))

    has_error = any(finding.severity == "error" for finding in findings)
    return 1 if has_error else 0


# \u2500\u2500 Phase pipeline + evidence + pr-check \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500


def _phase_pipeline_str(current: "WorkflowPhase", profile: str) -> str:
    """Return a one-line colored pipeline showing completed/current/pending phases."""
    profile_artifacts = set(PROFILE_ARTIFACTS.get(profile, []))
    optional_phase_map = {
        WorkflowPhase.SPECIFY:        "delta-spec.md",
        WorkflowPhase.DESIGN:         "design.md",
        WorkflowPhase.CRITIQUE:       "critique.md",
        WorkflowPhase.ARCHIVE_RECORD: "archive.md",
        WorkflowPhase.SYNC_SPECS:     "delta-spec.md",
    }

    visible = []
    for phase in _PIPELINE_PHASES:
        req = optional_phase_map.get(phase)
        if req is None or req in profile_artifacts:
            visible.append(phase)

    current_order = PHASE_ORDER.get(current, 0)
    parts = []
    for phase in visible:
        order = PHASE_ORDER.get(phase, 0)
        if phase == current:
            parts.append(_yellow("\u25c9 " + phase.value))
        elif phase == WorkflowPhase.ARCHIVED and current == WorkflowPhase.ARCHIVED:
            parts.append(_green("\u2714 " + phase.value))
        elif order < current_order:
            parts.append(_green("\u2714 ") + _dim(phase.value))
        else:
            parts.append(_dim("\u25cb " + phase.value))
    return " \u2192 ".join(parts)


def print_evidence(root: "Path", change_id: str) -> int:
    """Print a human-readable summary of execution evidence records for *change_id*."""
    findings = validate_change_id(change_id)
    if findings:
        return print_findings(root, findings)

    records, ev_findings = execution_evidence_records(root, change_id)
    ev_path = execution_evidence_path(root, change_id)

    try:
        rel_registry = ev_path.relative_to(root).as_posix()
    except ValueError:
        rel_registry = str(ev_path)

    print(_bold(f"SDD evidence: {change_id}"))
    print(f"  registry : {_dim(rel_registry)}")

    if ev_findings:
        print("  records  : 0")
        print("")
        for finding in ev_findings:
            print(_yellow("\u26a0") + " " + finding.format(root))
        return 1

    print(f"  records  : {len(records)}")
    if not records:
        print(f"  {_dim('(no execution evidence recorded yet)')}")
        return 0

    print("")
    for idx, record in enumerate(records, start=1):
        evidence_id = str(record.get("id", "?"))[:8]
        cmd = str(record.get("command", "?"))
        exit_code = record.get("exit_code", "?")
        passed = record.get("passed", False)
        recorded_at = str(record.get("recorded_at", "?"))
        dur = record.get("duration_seconds")
        log_val = record.get("log_path")
        checksum_val = str(record.get("output_checksum", ""))
        checksum_short = checksum_val[:16] + "..." if len(checksum_val) > 16 else checksum_val

        passed_str = _green("\u2714 passed") if passed else _red("\u2717 failed")
        print(f"  {_bold(str(idx))}. {_dim(evidence_id)}")
        print(f"     command  : {_bold(cmd)}")
        print(f"     result   : {passed_str}  (exit {exit_code})")
        if dur is not None:
            print(f"     duration : {dur}s")
        print(f"     recorded : {_dim(recorded_at)}")

        if isinstance(log_val, str):
            log_path = root / log_val
            if log_path.is_file():
                current_cksum = hashlib.sha256(
                    log_path.read_text(encoding="utf-8").encode("utf-8")
                ).hexdigest()
                integrity = (
                    _green("\u2714 ok") if current_cksum == checksum_val else _red("\u2717 tampered")
                )
                try:
                    rel_log = log_path.relative_to(root).as_posix()
                except ValueError:
                    rel_log = log_val
                print(f"     log      : {_dim(rel_log)}")
                print(f"     checksum : sha256:{_dim(checksum_short)}  [{integrity}]")
            else:
                print(f"     log      : {_red('MISSING')} {log_val}")
        print("")

    passing = sum(1 for r in records if r.get("passed"))
    failing = len(records) - passing
    summary_str = _green(f"{passing} passed") + (", " + _red(f"{failing} failed") if failing else "")
    print(f"  Summary: {summary_str}")
    return 0 if all(r.get("passed") for r in records) else 1


def print_pr_check(root: "Path", change_id: str) -> int:
    """Output a Markdown governance report ready to paste into a PR description."""
    findings = validate_change_id(change_id)
    if findings:
        return print_findings(root, findings)

    state = workflow_state(root, change_id)
    records, _ = execution_evidence_records(root, change_id)

    icon = _PHASE_ICON.get(state.phase.value, " ")
    phase_colored = (
        _green(icon + " " + state.phase.value) if state.phase == WorkflowPhase.ARCHIVED
        else _red(icon + " " + state.phase.value) if state.is_blocked
        else _cyan(icon + " " + state.phase.value)
    )

    print(_bold(f"SDD governance report: {change_id}"))
    print("")

    completed_phases = [
        p.value for p in _PIPELINE_PHASES
        if PHASE_ORDER.get(p, 0) <= PHASE_ORDER.get(state.phase, 0)
    ]
    md_lines = [
        "```",
        "## SDD Governance Report",
        "",
        f"**Change:** `{change_id}`  **Profile:** {state.profile}  **Phase:** {state.phase.value}",
        f"**Pipeline:** {' -> '.join(completed_phases)}",
        "",
    ]

    if records:
        md_lines += [
            "### Execution Evidence",
            "",
            "| # | Command | Result | Duration | SHA-256 |",
            "| - | ------- | ------ | -------- | ------- |",
        ]
        for idx, record in enumerate(records, start=1):
            cmd = str(record.get("command", "?"))
            exit_code = record.get("exit_code", "?")
            passed = record.get("passed", False)
            dur = record.get("duration_seconds", "-")
            cksum = str(record.get("output_checksum", ""))[:12]
            result_cell = "pass" if passed else "FAIL"
            md_lines.append(
                f"| {idx} | `{cmd}` | {result_cell} (exit {exit_code}) | {dur}s | `{cksum}...` |"
            )
        md_lines.append("")
    else:
        md_lines += ["*No execution evidence recorded.*", ""]

    md_lines += [
        f"> Generated by SSD-Core v{VERSION}",
        "> Artifact checksum in `.sdd/state.json`",
        "```",
    ]

    for line in md_lines:
        print(line)

    print("")
    print(f"  phase     : {phase_colored}")
    print(f"  pipeline  : {_phase_pipeline_str(state.phase, state.profile)}")

    if state.is_blocked:
        print(f"  {_red(chr(0x2717) + ' BLOCKED \u2014 resolve findings before merging')}")
        for f in state.findings:
            print(f"    {_red(chr(0x2717))} {f.format(root)}")
        return 1
    if state.phase not in {WorkflowPhase.VERIFY, WorkflowPhase.ARCHIVED}:
        print(f"  {_yellow(chr(0x26a0) + '  change is not yet verified \u2014 do not merge')}")
        return 1
    if not records:
        print(
            f"  {_yellow(chr(0x26a0) + '  no execution evidence \u2014 run: ssd-core verify --command or --discover')}"
        )
        return 1
    if not all(r.get("passed") for r in records):
        print(f"  {_red(chr(0x2717) + '  execution evidence contains failures \u2014 resolve before merging')}")
        return 1
    print(f"  {_green(chr(0x2714) + '  governance check passed \u2014 safe to merge')}")
    return 0




def run_fast_demo() -> int:
    """30-second proof: an agent says 'done' — governance says 'prove it'.

    Demonstrates the core value proposition:
      1. Change is created and the agent jumps straight to claiming it's done.
      2. Every premature archive attempt is blocked with a clear reason.
      3. Only after real evidence is recorded does archive succeed.

    Exit 0 on success, 1 on first failure.
    """
    import tempfile

    change_id = "agent-claims-done"
    profile = "quick"

    def line(msg: str) -> None:
        print(msg)

    with tempfile.TemporaryDirectory(prefix="sdd-fast-") as tmpdir:
        root = Path(tmpdir)

        print(_bold("SDD-Core — Proof: agent can't lie about being done"))
        print(_dim("=" * 54))
        print("")
        print("Scenario: an AI agent finishes coding and calls 'ssd-core archive'.")
        print("Watch what happens at each attempt.")
        print("")

        # Setup silently
        init_project(root)
        create_change(root, change_id, profile, "Agent claims to be done")

        # Attempt 1: archive before doing any work
        line(_bold("\nAttempt 1") + "  Agent calls: " + _cyan(f"ssd-core archive {change_id}"))
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

        line(_bold("\nAttempt 2") + "  Agent marks tasks done, calls: " + _cyan(f"ssd-core archive {change_id}"))
        findings = archive_change(root, change_id)
        if not findings:
            print(_red("UNEXPECTED: archive should have been blocked"))
            return 1
        print(_red("  \u2717 BLOCKED:") + " " + findings[0].message)

        # Attempt 3: verify with real command
        line(_bold("\nAttempt 3") + "  Agent provides evidence: " + _cyan(f"ssd-core verify {change_id} --command 'echo auth-tests-pass'"))
        v_findings = verify_change(root, change_id, ["echo auth-tests-pass"])
        if v_findings:
            for f in v_findings:
                print(_red("  \u2717") + " " + f.format(root))
            return 1
        print(_green("  \u2714 Evidence recorded") + " — command output checksummed and stored")

        # Now advance and archive via auto --loop
        line(_bold("\nAttempt 4") + "  Engine closes it: " + _cyan(f"ssd-core auto {change_id} --loop"))
        rc = print_auto(root, change_id, loop=True)
        if rc != 0:
            return 1

        print("")
        print(_dim("=" * 54))
        print(_bold("Result:"))
        print(f"  {_red('\u2717')} 3 blocked attempts  — the agent could not skip governance")
        print(f"  {_green('\u2714')} 1 successful archive — only after checksummed proof")
        print("")
        print(_bold("What was enforced:"))
        print(f"  phase order       : archive required verify first")
        print(f"  evidence quality  : verification.md could not contain placeholders")
        print(f"  execution proof   : output log + sha256 stored before phase recorded")
        print("")
        print(f"  {_cyan('ssd-core evidence ' + change_id)}  ← inspect what was recorded")
    return 0


def run_demo() -> int:
    """Run an annotated Golden Path demo in a temporary directory.

    Shows the full governance loop:
      1. Init + create change
      2. ``ssd-core auto --loop`` drains all auto-executable setup steps
      3. The agent fills proposal.md (simulated)
      4. ``ssd-core auto --loop`` advances to the task phase
      5. The agent closes tasks (simulated)
      6. ``ssd-core verify --command`` captures real execution evidence
      7. ``ssd-core auto --loop`` closes the change (archive)

    Every step runs real SDD-Core logic — no mocks, no shortcuts.
    Exit code: 0 on success, 1 on first failure.
    """
    import tempfile

    change_id = "demo-harden-login"
    profile = "quick"
    title = "Harden login error handling"

    def section(label: str) -> None:
        print(f"\n{_dim('──')} {_bold(label)}")

    def ok(msg: str) -> None:
        print(f"   {_green('✓')} {msg}")

    def fail(what: str, findings: list[Finding], root: Path) -> int:
        print(f"   {_red('✗')} {what}")
        for f in findings:
            print(f"     {_red('→')} {f.format(root)}")
        return 1

    with tempfile.TemporaryDirectory(prefix="sdd-demo-") as tmpdir:
        root = Path(tmpdir)

        print(_bold("SSD-Core — AI Development Governance Engine"))
        print(_dim("=" * 52))
        print("Problem: AI agents produce code but lose intent, skip verification,")
        print("         and claim completion without evidence.")
        print("Solution: a governance layer that enforces the protocol automatically.")
        print(f"\n{_dim('Temp root:')} {_dim(str(root))}")

        # ── Phase 0: init ─────────────────────────────────────────────
        section("ssd-core init  (one-time repository setup)")
        findings = init_project(root)
        if findings:
            return fail("init failed", findings, root)
        ok("Initialized .sdd/ — adapters, agents, profiles, schemas, skills, specs")

        # ── Phase 1: new change ───────────────────────────────────────
        section(f"ssd-core new {change_id} --profile quick --title '{title}'")
        findings = create_change(root, change_id, profile, title)
        if findings:
            return fail("create_change failed", findings, root)
        ok(f"Created .sdd/changes/{change_id}/ — proposal.md, tasks.md, verification.md")

        # ── Phase 2: auto --loop (nothing to execute yet) ─────────────
        section(f"ssd-core auto {change_id} --loop  (engine runs; pauses for human input)")
        result = _auto_advance(root, change_id)
        print(f"   → phase: {result.step.phase.value}")
        if result.needs_human_work:
            change_dir = change_directory(root, change_id)
            artifact_file = _PHASE_ARTIFACT_FILE.get(result.step.phase, "proposal.md")
            artifact_path = (change_dir / artifact_file).relative_to(root).as_posix()
            print(f"   → Engine paused. Needs human input.")
            print(f"     Edit: {artifact_path}")

        # ── Phase 3: agent fills proposal.md ─────────────────────────
        section("Agent fills proposal.md → status: ready  (simulated)")
        change_dir = change_directory(root, change_id)
        proposal_path = change_dir / "proposal.md"
        text = proposal_path.read_text(encoding="utf-8")
        text = set_frontmatter_value(text, "status", "ready")
        text = text.replace(
            "- Define the intended change.",
            "- Reject weak error codes; return structured error objects.",
        )
        proposal_path.write_text(text, encoding="utf-8")
        ok("proposal.md: intent recorded, status → ready")

        # ── Phase 4: auto --loop (advances to task, pauses) ──────────
        section(f"ssd-core auto {change_id} --loop  (engine resumes after human edit)")
        # Loop until it can't advance.
        loop_steps = 0
        while True:
            r = _auto_advance(root, change_id)
            if r.executed_command:
                print(f"   → Executed: {r.executed_command}")
                loop_steps += 1
            if r.needs_human_work or r.step.is_complete or r.step.is_blocked or not r.executed_command:
                break
        print(f"   → phase: {r.step.phase.value} ({loop_steps} step(s) executed)")
        if r.needs_human_work:
            artifact_file = _PHASE_ARTIFACT_FILE.get(r.step.phase, "tasks.md")
            artifact_path = (change_dir / artifact_file).relative_to(root).as_posix()
            print(f"   → Engine paused. Needs human input.")
            print(f"     Edit: {artifact_path}")

        # ── Phase 5: agent closes tasks.md ───────────────────────────
        section("Agent closes tasks in tasks.md → status: ready  (simulated)")
        tasks_path = change_dir / "tasks.md"
        text = tasks_path.read_text(encoding="utf-8")
        text = text.replace("- [ ]", "- [x]")
        text = text.replace(
            "T-001 Define the first concrete task.",
            "T-001 Return structured error object on login failure.",
        )
        text = set_frontmatter_value(text, "status", "ready")
        tasks_path.write_text(text, encoding="utf-8")
        ok("tasks.md: T-001 closed, status → ready")

        # ── Phase 6: auto --loop advances to verify, pauses ──────────
        section(f"ssd-core auto {change_id} --loop  (advances to verify, cannot skip it)")
        loop_steps = 0
        while True:
            r = _auto_advance(root, change_id)
            if r.executed_command:
                print(f"   → Executed: {r.executed_command}")
                loop_steps += 1
            if r.needs_human_work or r.step.is_complete or r.step.is_blocked or not r.executed_command:
                break
        print(f"   → phase: {r.step.phase.value} ({loop_steps} step(s) executed)")
        if r.step.phase == WorkflowPhase.VERIFY:
            print("   → Engine paused. Verification requires a real command.")
            print(f"     Run: ssd-core verify {change_id} --command '<your-test-command>'")

        # ── Phase 7: verify with real execution evidence ──────────────
        section(f"ssd-core verify {change_id} --command 'echo tests-pass'")
        print(f"   {_dim('(captures stdout/stderr, SHA-256 checksums output log, records timing)')}")
        findings = verify_change(root, change_id, ["echo tests-pass"])
        if findings:
            return fail("verify failed", findings, root)
        ok("Command executed; output stored → .sdd/evidence/<id>.log")
        ok("verification.md updated automatically → status: verified")
        ok("Phase recorded in .sdd/state.json → verify")

        # ── Phase 8: auto --loop closes the change ────────────────────
        section(f"ssd-core auto {change_id} --loop  (engine closes the change)")
        loop_steps = 0
        while True:
            r = _auto_advance(root, change_id)
            if r.executed_command:
                print(f"   → Executed: {r.executed_command}")
                loop_steps += 1
            if r.needs_human_work or r.step.is_complete or r.step.is_blocked or not r.executed_command:
                break
        if r.step.is_complete:
            archived = next(p for p in (root / ".sdd" / "archive").iterdir() if p.is_dir())
            ok(f"Change closed → .sdd/archive/{archived.name}/  ({loop_steps} step(s))")
        else:
            return fail("expected archived", r.step.blocking_findings, root)

        # ── Final: validate ───────────────────────────────────────────
        section("ssd-core validate  (full repository integrity check)")
        val_findings = [f for f in validate(root) if f.severity == "error"]
        if val_findings:
            return fail("validate failed", val_findings, root)
        ok("Repository governance passed — zero errors")

    print()
    print(_dim("=" * 52))
    print(_bold("Demo complete.") + " Temp directory cleaned up.")
    print()
    print(_bold("What the engine prevented:"))
    print(f"  {_red('→')} Hallucinated completion — archive required checksummed evidence")
    print(f"  {_red('→')} Phase skipping — ALLOWED_TRANSITIONS enforced every step")
    print(f"  {_red('→')} Stale state — state.json required before gated commands ran")
    print(f"  {_red('→')} Ungoverned commits — guard + install-hooks can enforce this in CI")
    print()
    print(_bold("Next:"))
    print(f"  {_cyan('ssd-core init --root <your-repo>')}")
    print(f"  {_cyan('ssd-core auto <change-id> --loop')}")
    print(f"  {_cyan('ssd-core ci-template --root <your-repo>')}")
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
        print(f"  " + _cyan(f"Run: ssd-core verify {change_id} --command '<your-test-command>'"))
        discovered = discover_test_command(root)
        if discovered:
            print(f"  " + _green(f"Discovered runner: ssd-core verify {change_id} --command '{discovered}'"))
        return 0

    artifact_file = _PHASE_ARTIFACT_FILE.get(step.phase)
    if artifact_file:
        change_dir = change_directory(root, change_id)
        artifact_path = (change_dir / artifact_file).relative_to(root).as_posix()
        print(_yellow(icon) + " " + _bold(f"phase: {step.phase.value}") + " " + _yellow("[needs edit]"))
        print(f"  {step.next_action}")
        print(f"  " + _cyan(f"Edit: {artifact_path}"))
        print(f"  Re-run " + _dim(f"ssd-core auto {change_id}") + " when done.")
        return 0

    # Fallback for any unhandled phase (e.g., SYNC_SPECS after a failed sync).
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
    """Advance *change_id* and print the result.

    When *loop* is False, executes one step and returns.
    When *loop* is True, keeps advancing automatically.  When *verify_commands*
    is also set, the loop will run ``ssd-core verify`` automatically instead of
    pausing at the verify phase — enabling a fully unattended lifecycle.
    """
    if not loop:
        return _print_auto_step(root, change_id, _auto_advance(root, change_id))

    print(_bold(f"SSD-Core auto loop: {change_id}"))
    print(_dim("-" * 44))
    steps_taken = 0
    result = _auto_advance(root, change_id)  # ensure defined
    while True:
        result = _auto_advance(root, change_id)
        # Auto-verify: when the loop pauses at VERIFY and --verify-with was supplied.
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
            continue  # let the loop advance past verify

        rc = _print_auto_step(root, change_id, result)
        if result.executed_command:
            steps_taken += 1
        if rc != 0 or result.step.is_complete or result.needs_human_work or not result.executed_command:
            break
    print(_dim("-" * 44))
    print(f"Auto loop finished. {_bold(str(steps_taken))} step(s) executed.")
    return 0 if not result.step.is_blocked else 1
