"""Workflow registry (state.json), phase gate, and transition logic.

Imports from _wf_changeops and _wf_inference are deferred inside
validate_workflow_registry and transition_workflow to break cycles.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from ._types import (
    Finding,
    WorkflowPhase,
    WorkflowState,
    WORKFLOW_STATE_SCHEMA,
    PHASE_ORDER,
    ALLOWED_TRANSITIONS,
    PHASE_NEXT_ACTIONS,
    trace,
)

# ── Registry constants ─────────────────────────────────────────────────────────

_MAX_HISTORY_ENTRIES = 25  # cap state.json per-change history to bound file size

# Phases that have a dedicated command and MUST NOT be reached via `transition`.
TRANSITION_RESTRICTED_PHASES = {
    WorkflowPhase.VERIFY,
    WorkflowPhase.ARCHIVED,
    WorkflowPhase.NOT_STARTED,
    WorkflowPhase.BLOCKED,
}

# Maps CLI command name to (required_recorded_phase, check_checksum_integrity).
COMMAND_GATES: dict[str, tuple[WorkflowPhase, bool]] = {
    "verify":     (WorkflowPhase.TASK,       False),
    "sync-specs": (WorkflowPhase.SYNC_SPECS, True),
    "archive":    (WorkflowPhase.ARCHIVE,    True),
}

# Maps human-work phases to the artifact file that needs editing.
_PHASE_ARTIFACT_FILE: dict[WorkflowPhase, str] = {
    WorkflowPhase.PROPOSE:        "proposal.md",
    WorkflowPhase.SPECIFY:        "delta-spec.md",
    WorkflowPhase.DESIGN:         "design.md",
    WorkflowPhase.TASK:           "tasks.md",
    WorkflowPhase.CRITIQUE:       "critique.md",
    WorkflowPhase.ARCHIVE_RECORD: "archive.md",
}


# ── Registry I/O ──────────────────────────────────────────────────────────────

def workflow_registry_path(root: Path) -> Path:
    return root / ".sdd" / "state.json"


def empty_workflow_registry() -> dict[str, object]:
    return {
        "schema": WORKFLOW_STATE_SCHEMA,
        "updated": date.today().isoformat(),
        "changes": {},
    }


def read_workflow_registry(root: Path) -> tuple[dict[str, object], list[Finding]]:
    path = workflow_registry_path(root)
    if not path.is_file():
        return empty_workflow_registry(), [Finding("error", path, "workflow state registry is missing")]

    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return empty_workflow_registry(), [Finding("error", path, f"invalid workflow state JSON: {exc.msg} at line {exc.lineno}")]

    if not isinstance(registry, dict):
        return empty_workflow_registry(), [Finding("error", path, "workflow state registry must be a JSON object")]
    if registry.get("schema") != WORKFLOW_STATE_SCHEMA:
        return registry, [Finding("error", path, f"workflow state schema must be {WORKFLOW_STATE_SCHEMA}")]
    if not isinstance(registry.get("changes"), dict):
        return registry, [Finding("error", path, "workflow state changes must be a JSON object")]
    return registry, []


def write_workflow_registry(root: Path, registry: dict[str, object]) -> None:
    path = workflow_registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["schema"] = WORKFLOW_STATE_SCHEMA
    registry["updated"] = date.today().isoformat()
    if not isinstance(registry.get("changes"), dict):
        registry["changes"] = {}
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def registry_changes(registry: dict[str, object]) -> dict[str, object]:
    changes = registry.get("changes")
    if isinstance(changes, dict):
        return changes
    registry["changes"] = {}
    return registry["changes"]  # type: ignore[return-value]


def state_entry(registry: dict[str, object], change_id: str) -> dict[str, object] | None:
    entry = registry_changes(registry).get(change_id)
    return entry if isinstance(entry, dict) else None


def artifact_checksum(change_dir: Path | None) -> str:
    digest = hashlib.sha256()
    if change_dir is None or not change_dir.is_dir():
        return ""
    for path in sorted(path for path in change_dir.rglob("*") if path.is_file()):
        relative = path.relative_to(change_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def record_workflow_state(root: Path, state: WorkflowState, action: str) -> None:
    if state.phase in {WorkflowPhase.NOT_STARTED, WorkflowPhase.BLOCKED}:
        return

    from ._wf_changeops import change_location

    registry, _ = read_workflow_registry(root)
    changes = registry_changes(registry)
    existing = state_entry(registry, state.change_id) or {}
    history = existing.get("history")
    if not isinstance(history, list):
        history = []

    today = date.today().isoformat()
    location = change_location(root, state.change_id)
    checksum = artifact_checksum(location)
    history.append(
        {
            "phase": state.phase.value,
            "action": action,
            "at": today,
            "checksum": checksum,
        }
    )
    changes[state.change_id] = {
        "phase": state.phase.value,
        "profile": state.profile,
        "updated": today,
        "checksum": checksum,
        "history": history[-_MAX_HISTORY_ENTRIES:],
    }
    write_workflow_registry(root, registry)


def declared_workflow_phase(root: Path, change_id: str) -> WorkflowPhase | None:
    registry, findings = read_workflow_registry(root)
    if findings:
        return None
    entry = state_entry(registry, change_id)
    if entry is None:
        return None
    phase = entry.get("phase")
    try:
        return WorkflowPhase(str(phase))
    except ValueError:
        return None


def phase_is_supported(target: WorkflowPhase, inferred: WorkflowPhase) -> bool:
    return PHASE_ORDER[target] <= PHASE_ORDER[inferred]


# ── Phase gate ────────────────────────────────────────────────────────────────

def require_recorded_phase(root: Path, change_id: str, expected: WorkflowPhase) -> list[Finding]:
    trace("REGISTRY", f"require_phase {change_id} expected={expected.value}")
    from ._wf_changeops import validate_change_id, change_location

    findings = validate_change_id(change_id)
    if findings:
        return findings

    registry, findings = read_workflow_registry(root)
    if findings:
        return findings

    entry = state_entry(registry, change_id)
    if entry is None:
        return [
            Finding(
                "error",
                change_location(root, change_id) or workflow_registry_path(root),
                f"workflow phase must be recorded before running this command; run `ssd-core transition {change_id} {expected.value}`",
            )
        ]

    try:
        declared = WorkflowPhase(str(entry.get("phase")))
    except ValueError:
        return [Finding("error", workflow_registry_path(root), f"workflow state phase is invalid for {change_id}: {entry.get('phase')}")]

    if declared != expected:
        return [
            Finding(
                "error",
                change_location(root, change_id) or workflow_registry_path(root),
                f"workflow phase must be {expected.value}; recorded phase is {declared.value}",
            )
        ]
    return []


def gate_command(
    root: Path,
    change_id: str,
    required_phase: WorkflowPhase,
    *,
    check_checksum: bool = False,
) -> list[Finding]:
    """Central command gate used by all destructive workflow commands."""
    trace("REGISTRY", f"gate_command {change_id} required={required_phase.value} checksum={check_checksum}")
    findings = require_recorded_phase(root, change_id, required_phase)
    if findings or not check_checksum:
        return findings

    from ._wf_changeops import change_location

    registry, reg_findings = read_workflow_registry(root)
    if reg_findings:
        return reg_findings

    entry = state_entry(registry, change_id)
    if entry is None:
        return []

    stored = str(entry.get("checksum", ""))
    if not stored:
        return []

    location = change_location(root, change_id)
    current = artifact_checksum(location)
    if current != stored:
        return [
            Finding(
                "error",
                location or workflow_registry_path(root),
                f"artifact checksum is stale since {required_phase.value} was recorded; "
                f"run `ssd-core transition {change_id} {required_phase.value}` to acknowledge changes before proceeding",
            )
        ]
    return []


def validate_workflow_registry(root: Path, *, strict_state: bool = False) -> list[Finding]:
    from ._wf_changeops import (
        active_change_directories,
        validate_change_id,
        change_location,
        archived_change_directory,
        archived_change_id,
        check_change_artifacts,
    )
    from ._wf_inference import _infer_workflow_state

    registry, findings = read_workflow_registry(root)
    if findings:
        return findings

    changes = registry_changes(registry)
    for change_id, raw_entry in changes.items():
        path = workflow_registry_path(root)
        if not isinstance(change_id, str) or validate_change_id(change_id):
            findings.append(Finding("error", path, f"workflow state change id is invalid: {change_id}"))
            continue
        if not isinstance(raw_entry, dict):
            findings.append(Finding("error", path, f"workflow state entry must be an object: {change_id}"))
            continue

        raw_phase = raw_entry.get("phase")
        try:
            declared = WorkflowPhase(str(raw_phase))
        except ValueError:
            findings.append(Finding("error", path, f"workflow state phase is invalid for {change_id}: {raw_phase}"))
            continue

        artifact_state = _infer_workflow_state(root, change_id)
        if artifact_state.phase == WorkflowPhase.NOT_STARTED:
            findings.append(Finding("error", path, f"workflow state references missing change: {change_id}"))
            continue
        if artifact_state.is_blocked:
            findings.extend(artifact_state.findings)
            continue
        if PHASE_ORDER[declared] > PHASE_ORDER[artifact_state.phase]:
            findings.append(
                Finding(
                    "error",
                    change_location(root, change_id),
                    f"declared phase {declared.value} is ahead of artifact phase {artifact_state.phase.value}",
                )
            )

        if strict_state:
            location = change_location(root, change_id)
            current_checksum = artifact_checksum(location)
            if raw_entry.get("checksum") != current_checksum:
                findings.append(
                    Finding(
                        "error",
                        location or path,
                        f"workflow state checksum is stale for {change_id}; run `ssd-core transition {change_id} <phase>` after intentional artifact changes",
                    )
                )

    if strict_state:
        tracked_changes = {str(change_id) for change_id in changes}
        for change_dir in active_change_directories(root):
            if change_dir.name not in tracked_changes:
                findings.append(
                    Finding(
                        "error",
                        change_dir,
                        f"active change is not recorded in .sdd/state.json: {change_dir.name}",
                    )
                )

    return findings


def transition_workflow(root: Path, change_id: str, target_phase: WorkflowPhase) -> WorkflowState:
    trace("REGISTRY", f"transition {change_id} → {target_phase.value}")
    from ._wf_changeops import validate_change_id, change_location
    from ._wf_inference import workflow_state, infer_phase_from_artifacts

    findings = validate_change_id(change_id)
    if findings:
        return WorkflowState(change_id, WorkflowPhase.BLOCKED, "unknown", "Use a kebab-case change id.", findings)
    if target_phase in TRANSITION_RESTRICTED_PHASES:
        if target_phase == WorkflowPhase.VERIFY:
            message = f"use `ssd-core verify {change_id}` to record the verify phase; it enforces evidence quality before recording"
        elif target_phase == WorkflowPhase.ARCHIVED:
            message = f"use `ssd-core archive {change_id}` to archive a change"
        else:
            message = f"cannot transition to {target_phase.value}"
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            "unknown",
            "Choose an active workflow phase.",
            [Finding("error", None, message)],
        )

    state = workflow_state(root, change_id)
    if state.is_blocked:
        return state

    current = state.phase
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target_phase not in allowed:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            state.profile,
            state.next_action,
            [
                Finding(
                    "error",
                    change_location(root, change_id),
                    f"invalid workflow transition: {current.value} -> {target_phase.value}",
                )
            ],
        )

    artifact_phase = infer_phase_from_artifacts(root, change_id)
    if not phase_is_supported(target_phase, artifact_phase):
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            state.profile,
            state.next_action,
            [
                Finding(
                    "error",
                    change_location(root, change_id),
                    f"artifacts do not support transition to {target_phase.value}; artifact phase is {artifact_phase.value}",
                )
            ],
        )

    transitioned = WorkflowState(change_id, target_phase, state.profile, state.next_action, [])
    record_workflow_state(root, transitioned, "transition")
    return transitioned
