"""One-shot script: insert pipeline + evidence + pr-check helpers into cli.py."""
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "ssd_core" / "cli.py"
content = CLI.read_text(encoding="utf-8")

ANCHOR = '    return 1 if has_error else 0\n\n\n# \u2500\u2500 CI template'
assert content.count(ANCHOR) == 1, f"anchor not found uniquely: {content.count(ANCHOR)}"

INSERT = r'''    return 1 if has_error else 0


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


# \u2500\u2500 CI template'''

content = content.replace(ANCHOR, INSERT, 1)
CLI.write_text(content, encoding="utf-8")
print("Done.")
