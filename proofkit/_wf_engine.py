"""SDDWorkflow, WorkflowEngine, EngineStep, and AutoStep.

Top-level module that imports from all lower-level modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from ._types import (
    Finding,
    WorkflowPhase,
    WorkflowFailureKind,
    WorkflowFailure,
    WorkflowState,
    WorkflowResult,
    SDD_DIR,
    PHASE_ORDER,
    ALLOWED_TRANSITIONS,
    trace,
)
from ._wf_changeops import (
    change_directory,
    archive_change,
    sync_specs,
    validate_spec_sync,
    active_change_directories,
    archived_change_id,
    check_change_artifacts,
)
from ._wf_evidence import (
    verify_change,
    validate_execution_evidence,
)
from ._wf_inference import (
    workflow_state,
    infer_phase_from_artifacts,
    run_workflow,
)
from ._wf_registry import (
    COMMAND_GATES,
    TRANSITION_RESTRICTED_PHASES,
    gate_command,
    validate_workflow_registry,
)
from ._wf_validation import validate
from ._extensions import run_extension_hooks


def _suggested_command(phase: WorkflowPhase, change_id: str) -> str | None:
    """Return the canonical CLI command that advances *change_id* past *phase*."""
    mapping: dict[WorkflowPhase, str | None] = {
        WorkflowPhase.NOT_STARTED:    f"proofkit new {change_id} --profile <profile> --title '<intent>'",
        WorkflowPhase.PROPOSE:        f"proofkit transition {change_id} propose",
        WorkflowPhase.SPECIFY:        f"proofkit transition {change_id} specify",
        WorkflowPhase.DESIGN:         f"proofkit transition {change_id} design",
        WorkflowPhase.TASK:           f"proofkit transition {change_id} task",
        WorkflowPhase.VERIFY:         f"proofkit verify {change_id} --command '<test-command>'",
        WorkflowPhase.CRITIQUE:       f"proofkit transition {change_id} archive-record",
        WorkflowPhase.ARCHIVE_RECORD: f"proofkit transition {change_id} sync-specs",
        WorkflowPhase.SYNC_SPECS:     f"proofkit sync-specs {change_id}",
        WorkflowPhase.ARCHIVE:        f"proofkit archive {change_id}",
        WorkflowPhase.ARCHIVED:       None,
        WorkflowPhase.BLOCKED:        None,
    }
    return mapping.get(phase)


@dataclass(frozen=True)
class EngineStep:
    """Structured description of the current workflow position."""

    change_id: str
    phase: WorkflowPhase
    next_action: str
    suggested_command: str | None
    allowed_commands: list[str]
    blocking_findings: list[Finding]

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocking_findings)

    @property
    def is_complete(self) -> bool:
        return self.phase == WorkflowPhase.ARCHIVED


@dataclass(frozen=True)
class AutoStep:
    """Return type for ``WorkflowEngine.execute_next()`` and ``proofkit auto``."""

    executed_command: str | None
    step: EngineStep

    @property
    def is_blocked(self) -> bool:
        return self.step.is_blocked

    @property
    def is_complete(self) -> bool:
        return self.step.is_complete

    @property
    def needs_human_work(self) -> bool:
        return not self.is_blocked and not self.is_complete and self.executed_command is None


class WorkflowEngine:
    """Declarative workflow engine."""

    COMMAND_GATES: ClassVar[dict[str, tuple[WorkflowPhase, bool]]] = COMMAND_GATES

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def guard(self, change_id: str, command: str) -> list[Finding]:
        """Return block findings for *command* against *change_id*, or [] if the gate passes."""
        trace("ENGINE", f"engine.guard {change_id} command={command}")
        if command not in self.COMMAND_GATES:
            return [Finding("error", None, f"no gate registered for command: {command}")]
        required_phase, check_checksum = self.COMMAND_GATES[command]
        return gate_command(self.root, change_id, required_phase, check_checksum=check_checksum)

    def allowed_commands(self, change_id: str) -> list[str]:
        """Return the names of gated commands that would pass the gate right now."""
        return sorted(
            command
            for command, (phase, checksum) in self.COMMAND_GATES.items()
            if not gate_command(self.root, change_id, phase, check_checksum=checksum)
        )

    def next_step(self, change_id: str) -> "EngineStep":
        """Return a structured description of the current workflow position."""
        state = workflow_state(self.root, change_id)
        return EngineStep(
            change_id=change_id,
            phase=state.phase,
            next_action=state.next_action,
            suggested_command=_suggested_command(state.phase, change_id),
            allowed_commands=self.allowed_commands(change_id),
            blocking_findings=list(state.findings),
        )

    def execute(
        self,
        change_id: str,
        command: str,
        *,
        verification_commands: list[str] | None = None,
        require_command: bool = False,
        timeout_seconds: int = 120,
    ) -> list[Finding]:
        """Execute a gated workflow command after checking its declared phase."""
        trace("ENGINE", f"engine.execute {change_id} command={command}")
        findings = self.guard(change_id, command)
        if findings:
            return findings
        if command == "verify":
            return verify_change(
                self.root,
                change_id,
                verification_commands,
                require_command=require_command,
                timeout_seconds=timeout_seconds,
            )
        if command == "sync-specs":
            return sync_specs(self.root, change_id)
        if command == "archive":
            return archive_change(self.root, change_id)
        return [Finding("error", None, f"no executor registered for command: {command}")]

    def execute_next(self, change_id: str) -> "AutoStep":
        """Advance the workflow one step automatically."""
        return _auto_advance(self.root, change_id)


class SDDWorkflow:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def state(self, change_id: str) -> WorkflowState:
        return workflow_state(self.root, change_id)

    def run(
        self,
        change_id: str,
        *,
        profile: str = "standard",
        title: str | None = None,
        create: bool = True,
    ) -> WorkflowResult:
        state = run_workflow(self.root, change_id, profile, title, create=create)
        failures = [
            WorkflowFailure.from_finding(WorkflowFailureKind.VALIDATION, finding)
            for finding in state.findings
            if state.is_blocked
        ]
        return WorkflowResult(state, failures)

    def require_phase(self, change_id: str, expected: WorkflowPhase, *, check_checksum: bool = False) -> WorkflowResult:
        gate_findings = gate_command(self.root, change_id, expected, check_checksum=check_checksum)
        state = self.state(change_id)
        if gate_findings:
            failure = WorkflowFailure.from_finding(WorkflowFailureKind.PHASE_ORDER, gate_findings[0])
            blocked_state = WorkflowState(
                change_id,
                WorkflowPhase.BLOCKED,
                state.profile,
                state.next_action,
                gate_findings,
            )
            return WorkflowResult(blocked_state, [failure])

        if state.phase != expected:
            failure = WorkflowFailure(
                WorkflowFailureKind.PHASE_ORDER,
                f"workflow phase must be {expected.value}; current phase is {state.phase.value}",
                change_directory(self.root, change_id),
            )
            blocked_state = WorkflowState(
                change_id,
                WorkflowPhase.BLOCKED,
                state.profile,
                state.next_action,
                [failure.to_finding()],
            )
            return WorkflowResult(blocked_state, [failure])
        return WorkflowResult(state, [])

    def transition(self, change_id: str, target_phase: WorkflowPhase | str) -> WorkflowResult:
        from ._wf_registry import transition_workflow

        try:
            phase = target_phase if isinstance(target_phase, WorkflowPhase) else WorkflowPhase(str(target_phase))
        except ValueError:
            failure = WorkflowFailure(
                WorkflowFailureKind.PHASE_ORDER,
                f"unknown workflow phase: {target_phase}",
                change_directory(self.root, change_id),
            )
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    "unknown",
                    "Choose a valid workflow phase.",
                    [failure.to_finding()],
                ),
                [failure],
            )
        state = transition_workflow(self.root, change_id, phase)
        failures = [
            WorkflowFailure.from_finding(WorkflowFailureKind.PHASE_ORDER, finding)
            for finding in state.findings
            if state.is_blocked
        ]
        return WorkflowResult(state, failures)

    def sync_specs(self, change_id: str) -> WorkflowResult:
        required = self.require_phase(change_id, WorkflowPhase.SYNC_SPECS, check_checksum=True)
        if not required.ok:
            return required

        findings = sync_specs(self.root, change_id)
        if findings:
            failures = [WorkflowFailure.from_finding(WorkflowFailureKind.COMMAND, finding) for finding in findings]
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    required.state.profile,
                    "Resolve sync-specs findings before continuing.",
                    [failure.to_finding() for failure in failures],
                ),
                failures,
            )
        return WorkflowResult(self.state(change_id), [])

    def verify(
        self,
        change_id: str,
        commands: list[str] | None = None,
        *,
        require_command: bool = False,
        timeout_seconds: int = 120,
    ) -> WorkflowResult:
        required = self.require_phase(change_id, WorkflowPhase.TASK, check_checksum=False)
        if not required.ok:
            return required

        findings = verify_change(
            self.root,
            change_id,
            commands,
            require_command=require_command,
            timeout_seconds=timeout_seconds,
        )
        if findings:
            failures = [WorkflowFailure.from_finding(WorkflowFailureKind.COMMAND, finding) for finding in findings]
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    required.state.profile,
                    "Resolve verification findings before continuing.",
                    [failure.to_finding() for failure in failures],
                ),
                failures,
            )
        return WorkflowResult(self.state(change_id), [])

    def archive(self, change_id: str) -> WorkflowResult:
        required = self.require_phase(change_id, WorkflowPhase.ARCHIVE, check_checksum=True)
        if not required.ok:
            return required

        findings = archive_change(self.root, change_id)
        if findings:
            failures = [WorkflowFailure.from_finding(WorkflowFailureKind.COMMAND, finding) for finding in findings]
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    required.state.profile,
                    "Resolve archive findings before continuing.",
                    [failure.to_finding() for failure in failures],
                ),
                failures,
            )
        return WorkflowResult(self.state(change_id), [])


def guard_repository(
    root: Path,
    *,
    require_active_change: bool = False,
    strict_state: bool = False,
    require_execution_evidence: bool = False,
) -> list[Finding]:
    trace("ENGINE", f"guard_repository root={root.name} strict={strict_state} evidence={require_execution_evidence}")
    findings = [finding for finding in validate(root) if finding.severity == "error"]
    if findings:
        return findings

    findings.extend(validate_workflow_registry(root, strict_state=strict_state))

    active_changes = active_change_directories(root)
    if require_active_change and not active_changes:
        findings.append(
            Finding(
                "error",
                root / SDD_DIR / "changes",
                "active SDD change is required by guard policy",
            )
        )

    for change_dir in active_changes:
        state = workflow_state(root, change_dir.name)
        if state.is_blocked:
            findings.extend(state.findings)
        if require_execution_evidence and PHASE_ORDER[state.phase] >= PHASE_ORDER[WorkflowPhase.VERIFY]:
            findings.extend(validate_execution_evidence(root, change_dir.name))

    archive_root = root / SDD_DIR / "archive"
    if archive_root.is_dir():
        for archive_dir in sorted(path for path in archive_root.iterdir() if path.is_dir()):
            change_id = archived_change_id(archive_dir)
            findings.extend(check_change_artifacts(root, archive_dir, change_id))
            findings.extend(validate_spec_sync(root, archive_dir, change_id))
            if require_execution_evidence:
                findings.extend(validate_execution_evidence(root, change_id))

    findings.extend(run_extension_hooks(root, "on_guard", findings=list(findings)))
    return findings


def _auto_advance(root: Path, change_id: str) -> "AutoStep":
    """Advance the workflow one step automatically."""
    trace("ENGINE", f"auto_advance {change_id}")
    from ._wf_registry import transition_workflow

    engine = WorkflowEngine(root)

    def current_step() -> "EngineStep":
        return engine.next_step(change_id)

    state = workflow_state(root, change_id)

    if state.is_blocked or state.phase == WorkflowPhase.ARCHIVED or state.phase == WorkflowPhase.NOT_STARTED:
        return AutoStep(executed_command=None, step=current_step())

    if state.phase == WorkflowPhase.SYNC_SPECS:
        findings = sync_specs(root, change_id)
        cmd = f"sync-specs {change_id}"
        return AutoStep(executed_command=None if findings else cmd, step=current_step())

    if state.phase == WorkflowPhase.ARCHIVE:
        findings = archive_change(root, change_id)
        cmd = f"archive {change_id}"
        return AutoStep(executed_command=None if findings else cmd, step=current_step())

    artifact_phase = infer_phase_from_artifacts(root, change_id)
    if PHASE_ORDER.get(artifact_phase, 0) > PHASE_ORDER.get(state.phase, 0):
        eligible = ALLOWED_TRANSITIONS.get(state.phase, set()) - TRANSITION_RESTRICTED_PHASES
        target = max(
            (t for t in eligible if PHASE_ORDER.get(t, 0) <= PHASE_ORDER.get(artifact_phase, 0)),
            key=lambda t: PHASE_ORDER.get(t, 0),
            default=None,
        )
        if target is not None:
            new_state = transition_workflow(root, change_id, target)
            if new_state.is_blocked:
                return AutoStep(executed_command=None, step=current_step())
            return AutoStep(executed_command=f"transition {change_id} {target.value}", step=current_step())

    return AutoStep(executed_command=None, step=current_step())
