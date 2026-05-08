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
    SDD_DIR,
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
    _display_text,
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
    install_commands,
    list_available_integrations,
    load_extensions,
    install_extension,
    remove_extension,
    read_memory_entry,
    append_memory,
    _memory_word_count,
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
    mark_artifact_ready,
    WorkflowEngine,
    AutoStep,
    EngineStep,
)


def print_extension_list(root: Path) -> int:
    """Print all installed extensions and return 0."""
    exts = load_extensions(root)
    if not exts:
        print(_dim("No extensions installed."))
        print(_dim("  Install one: runproof extension install <path>"))
        return 0
    print(_bold(f"Installed extensions ({len(exts)}):"))
    for ext in exts:
        trust_tag = _green("[trusted]") if ext.is_trusted else _yellow("[not trusted]")
        hooks_tag = _dim(" hooks") if ext.has_hooks else ""
        print(f"  {_bold(ext.name)}  {_dim(ext.version)}  {trust_tag}{hooks_tag}")
        print(f"    {ext.description}")
    return 0


def print_memory(root: Path, key: str | None = None) -> int:
    """Print the content of one or all memory files."""
    from ._types import MEMORY_KEYS
    keys = [key] if key else MEMORY_KEYS
    for k in keys:
        content = read_memory_entry(root, k)
        if content is None:
            print(_yellow(f"Memory file '{k}.md' not found — run `runproof init` first."))
            return 1
        print(_bold(f"── memory/{k}.md ──"))
        print(content)
    return 0


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
        print(_green("\u2714") + " " + _bold("RunProof guard passed."))
        return 0

    print(_red("\u2717") + " " + _bold("RunProof guard blocked."))
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

    print(_bold(f"RunProof log: {change_id}"))
    print(f"  profile : {entry.get('profile', 'unknown')}")
    print(f"  phase   : {_cyan(str(entry.get('phase', 'unknown')))}")
    print("")
    print(_bold("History:"))
    for record in history:
        phase = record.get("phase", "?")
        action = record.get("action", "?")
        at = record.get("at", "?")
        checksum = str(record.get("checksum", ""))[:8] or "(none)"
        icon = _display_text(_PHASE_ICON.get(str(phase), " "))
        print(f"  {_dim(at)} {icon} {_cyan(f'{phase:<20}')} via {_dim(action):<14} sha256:{_dim(checksum)}")
    return 0


def print_phase(root: Path, change_id: str) -> int:
    findings = validate_change_id(change_id)
    if findings:
        return print_findings(root, findings)

    declared = declared_workflow_phase(root, change_id)
    artifact_phase = infer_phase_from_artifacts(root, change_id)
    state = workflow_state(root, change_id)

    print(_bold(f"RunProof phase: {change_id}"))
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
    from ._wf_registry import _PHASE_ARTIFACT_FILE
    icon = _PHASE_ICON.get(state.phase.value, " ")
    phase_str = _red(icon + " " + state.phase.value) if state.is_blocked else _cyan(icon + " " + state.phase.value)
    print(_bold("RunProof workflow"))
    print(f"  root    : {_dim(str(root))}")
    print(f"  change  : {state.change_id}")
    print(f"  profile : {state.profile}")
    print(f"  phase   : {phase_str}")

    artifact_filename = _PHASE_ARTIFACT_FILE.get(state.phase)
    if artifact_filename and not state.is_blocked:
        artifact_path = root / ".runproof" / "changes" / state.change_id / artifact_filename
        try:
            rel = artifact_path.relative_to(root).as_posix()
        except ValueError:
            rel = str(artifact_path)
        print(f"  file    : {_dim(rel)}")
        print(f"  next    : {state.next_action}")
        print(f"  hint    : {_cyan(f'runproof ready {state.change_id}')}  {_dim('(marks artifact as ready)')}")
    else:
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
        print(_red("\u2717") + " " + _bold("RunProof transition blocked."))
        for finding in state.findings:
            pre = _red("  \u2717") if finding.severity == "error" else _yellow("  \u26a0")
            print(pre + " " + finding.format(root))
        # Actionable hint when blocked because the artifact isn't ready yet
        has_artifact_block = any(
            "artifacts do not support transition" in (f.message or "") or
            "artifact phase is" in (f.message or "")
            for f in state.findings
        )
        if has_artifact_block:
            print(_dim(f"  → Run: runproof ready {state.change_id}"))
        return 1

    icon = _PHASE_ICON.get(state.phase.value, " ")
    print(_green("\u2714") + " " + _bold("RunProof transition recorded."))
    print(f"  change   : {state.change_id}")
    print(f"  phase    : {_cyan(icon + ' ' + state.phase.value)}")
    print(f"  registry : {workflow_registry_path(root).relative_to(root).as_posix()}")
    return 0


def print_status(root: Path) -> int:
    findings, changes = status(root)
    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]

    val_str = _red("fail") if errors else _green("pass")
    print(_bold("RunProof status"))
    print(f"  root            : {_dim(str(root))}")
    print(f"  validation      : {val_str}")
    print(f"  active changes  : {len(changes)}")
    mem_words = _memory_word_count(root)
    print(f"  memory          : {mem_words} word(s)")

    if changes:
        print("")
        print(_bold("Changes:"))
        for change in changes:
            icon = _display_text(_PHASE_ICON.get("archived" if change.is_complete else "propose", " "))
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
        print(_green("\u2714") + " RunProof validation passed.")
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
    return _display_text(" \u2192 ".join(parts))


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

    print(_bold(f"RunProof evidence: {change_id}"))
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

    print(_bold(f"RunProof governance report: {change_id}"))
    print("")

    completed_phases = [
        p.value for p in _PIPELINE_PHASES
        if PHASE_ORDER.get(p, 0) <= PHASE_ORDER.get(state.phase, 0)
    ]
    md_lines = [
        "```",
        "## RunProof Governance Report",
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
        f"> Generated by RunProof v{VERSION}",
        "> Artifact checksum in `.runproof/state.json`",
        "```",
    ]

    for line in md_lines:
        print(line)

    print("")
    print(f"  phase     : {phase_colored}")
    print(f"  pipeline  : {_phase_pipeline_str(state.phase, state.profile)}")

    if state.is_blocked:
        print("  " + _red(f"{chr(0x2717)} BLOCKED - resolve findings before merging"))
        for f in state.findings:
            print(f"    {_red(chr(0x2717))} {f.format(root)}")
        return 1
    if state.phase not in {WorkflowPhase.VERIFY, WorkflowPhase.ARCHIVED}:
        print("  " + _yellow(f"{chr(0x26a0)}  change is not yet verified - do not merge"))
        return 1
    if not records:
        print("  " + _yellow(f"{chr(0x26a0)}  no execution evidence - run: runproof verify --command or --discover"))
        return 1
    if not all(r.get("passed") for r in records):
        print("  " + _red(f"{chr(0x2717)}  execution evidence contains failures - resolve before merging"))
        return 1
    print("  " + _green(f"{chr(0x2714)}  governance check passed - safe to merge"))
    return 0

# ── Auto-advance, demo, print_auto (split to keep file under 500 lines) ──────
from ._render_auto import *  # noqa: F401, F403

