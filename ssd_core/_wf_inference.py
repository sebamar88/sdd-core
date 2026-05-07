"""Workflow state inference: artifact-based phase detection and state.json synthesis.

Both _wf_changeops and _wf_registry are imported at the top level here because
_wf_inference is the highest-level consumer of those two modules in the acyclic
direction.  Any remaining cycles (changeops → inference, registry → inference)
are broken by the lazy imports in _wf_changeops (sync_specs, create_change)
and _wf_registry (validate_workflow_registry, transition_workflow).
"""
from __future__ import annotations

from pathlib import Path

from ._types import (
    Finding,
    WorkflowPhase,
    WorkflowState,
    OPEN_TASK_PATTERN,
    PHASE_ORDER,
    PHASE_NEXT_ACTIONS,
    trace,
)
from ._wf_changeops import (
    validate_change_id,
    archived_change_directory,
    change_directory,
    summarize_change,
    artifact_status,
    validate_spec_sync,
    check_change,
)
from ._wf_registry import (
    declared_workflow_phase,
    record_workflow_state,
)


def _infer_workflow_state(root: Path, change_id: str) -> WorkflowState:
    """Return workflow state inferred purely from artifact content, ignoring state.json."""
    findings = validate_change_id(change_id)
    if findings:
        return WorkflowState(change_id, WorkflowPhase.BLOCKED, "unknown", "Use a kebab-case change id.", findings)

    archived_dir = archived_change_directory(root, change_id)
    if archived_dir is not None:
        return WorkflowState(
            change_id,
            WorkflowPhase.ARCHIVED,
            "archived",
            f"Review archived evidence at {archived_dir.relative_to(root).as_posix()}.",
            [],
        )

    change_dir = change_directory(root, change_id)
    if not change_dir.is_dir():
        return WorkflowState(
            change_id,
            WorkflowPhase.NOT_STARTED,
            "unknown",
            "Create the governed change artifacts.",
            [],
        )

    summary = summarize_change(change_dir)
    if summary.profile == "unknown":
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Fix change artifact frontmatter so the profile can be detected.",
            [Finding("error", change_dir, "could not detect profile")],
        )

    structural_findings: list[Finding] = []
    for filename in summary.missing:
        structural_findings.append(Finding("error", change_dir / filename, "required profile artifact is missing"))
    for filename in summary.present:
        status_value, status_finding = artifact_status(change_dir, filename)
        if status_finding is not None:
            structural_findings.append(status_finding)
        elif status_value == "blocked":
            structural_findings.append(Finding("error", change_dir / filename, "artifact status is blocked"))
    if structural_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Resolve blocking artifact findings before continuing.",
            structural_findings,
        )

    phase_artifacts = [
        ("proposal.md", WorkflowPhase.PROPOSE, "Complete proposal.md and set status to ready."),
        ("delta-spec.md", WorkflowPhase.SPECIFY, "Complete delta-spec.md and set status to ready."),
        ("design.md", WorkflowPhase.DESIGN, "Complete design.md and set status to ready."),
        ("tasks.md", WorkflowPhase.TASK, "Complete tasks.md, close all task checkboxes, and set status to ready."),
        ("verification.md", WorkflowPhase.VERIFY, "Record passing evidence in verification.md and set status to verified."),
        ("critique.md", WorkflowPhase.CRITIQUE, "Resolve critique.md and set status to ready or verified."),
        ("archive.md", WorkflowPhase.ARCHIVE_RECORD, "Complete archive.md and set status to ready."),
    ]

    for filename, phase, next_action in phase_artifacts:
        if filename not in summary.present:
            continue
        path = change_dir / filename
        status_value, _ = artifact_status(change_dir, filename)
        if filename == "tasks.md" and OPEN_TASK_PATTERN.search(path.read_text(encoding="utf-8")):
            return WorkflowState(change_id, phase, summary.profile, next_action, [])
        if filename == "verification.md":
            verification_text = path.read_text(encoding="utf-8").lower()
            if status_value != "verified" or "not-run" in verification_text or "pending verification evidence" in verification_text:
                return WorkflowState(change_id, phase, summary.profile, next_action, [])
            continue
        if filename == "critique.md":
            if status_value not in {"ready", "verified"}:
                return WorkflowState(change_id, phase, summary.profile, next_action, [])
            continue
        if status_value != "ready":
            return WorkflowState(change_id, phase, summary.profile, next_action, [])

    readiness_findings = check_change(root, change_id)
    if readiness_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Resolve readiness findings before syncing specs or archiving.",
            readiness_findings,
        )

    spec_path = root / ".sdd" / "specs" / change_id / "spec.md"
    if "delta-spec.md" in summary.present and not spec_path.is_file():
        return WorkflowState(
            change_id,
            WorkflowPhase.SYNC_SPECS,
            summary.profile,
            f"Run `ssd-core sync-specs {change_id} --root <repo>`.",
            [],
        )

    return WorkflowState(
        change_id,
        WorkflowPhase.ARCHIVE,
        summary.profile,
        f"Run `ssd-core archive {change_id} --root <repo>`.",
        [],
    )


def workflow_state(root: Path, change_id: str) -> WorkflowState:
    """Return the current workflow state (state.json-authoritative with artifact fallback)."""
    trace("INFERENCE", f"workflow_state {change_id}")
    findings = validate_change_id(change_id)
    if findings:
        return WorkflowState(change_id, WorkflowPhase.BLOCKED, "unknown", "Use a kebab-case change id.", findings)

    archived_dir = archived_change_directory(root, change_id)
    if archived_dir is not None:
        return WorkflowState(
            change_id,
            WorkflowPhase.ARCHIVED,
            "archived",
            f"Review archived evidence at {archived_dir.relative_to(root).as_posix()}.",
            [],
        )

    change_dir = change_directory(root, change_id)
    if not change_dir.is_dir():
        return WorkflowState(
            change_id, WorkflowPhase.NOT_STARTED, "unknown", "Create the governed change artifacts.", []
        )

    summary = summarize_change(change_dir)
    if summary.profile == "unknown":
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Fix change artifact frontmatter so the profile can be detected.",
            [Finding("error", change_dir, "could not detect profile")],
        )

    structural_findings: list[Finding] = []
    for filename in summary.missing:
        structural_findings.append(Finding("error", change_dir / filename, "required profile artifact is missing"))
    for filename in summary.present:
        status_value, status_finding = artifact_status(change_dir, filename)
        if status_finding is not None:
            structural_findings.append(status_finding)
        elif status_value == "blocked":
            structural_findings.append(Finding("error", change_dir / filename, "artifact status is blocked"))
    if structural_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Resolve blocking artifact findings before continuing.",
            structural_findings,
        )

    # state.json is authoritative when a phase has been recorded.
    declared = declared_workflow_phase(root, change_id)
    if declared is not None:
        next_action = PHASE_NEXT_ACTIONS.get(declared, f"Continue {declared.value} phase.")
        return WorkflowState(change_id, declared, summary.profile, next_action, [])

    # No recorded phase — fall back to artifact inference.
    return _infer_workflow_state(root, change_id)


def infer_phase_from_artifacts(root: Path, change_id: str) -> WorkflowPhase:
    """Return the phase implied by artifact state alone, ignoring state.json."""
    return _infer_workflow_state(root, change_id).phase


def infer_state_from_artifacts(root: Path, change_id: str) -> WorkflowState:
    """Return the full WorkflowState inferred from artifact content, ignoring state.json."""
    return _infer_workflow_state(root, change_id)


def run_workflow(
    root: Path,
    change_id: str,
    profile: str,
    title: str | None,
    *,
    create: bool = True,
) -> WorkflowState:
    trace("INFERENCE", f"run_workflow {change_id} profile={profile} create={create}")
    from ._wf_validation import validate
    from ._wf_changeops import create_change

    foundation_findings = validate(root)
    foundation_errors = [finding for finding in foundation_findings if finding.severity == "error"]
    if foundation_errors:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            profile,
            "Initialize or repair the SSD-Core foundation before running a workflow.",
            foundation_errors,
        )

    state = workflow_state(root, change_id)
    if state.phase != WorkflowPhase.NOT_STARTED or not create:
        record_workflow_state(root, state, "run")
        return state

    create_findings = create_change(root, change_id, profile, title)
    if create_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            profile,
            "Fix change creation findings before continuing.",
            create_findings,
        )
    state = workflow_state(root, change_id)
    record_workflow_state(root, state, "run")
    return state
