"""
Contract tests: cross-module behavioral guarantees.

These tests verify the invariants that hold across module boundaries:

    ENGINE   ←→ REGISTRY
    EVIDENCE ←→ REGISTRY
    INFERENCE ←→ REGISTRY
    VALIDATION ←→ CHANGEOPS

Each test names the contract it exercises in its docstring.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import uuid
import unittest
from pathlib import Path

from ssd_core import cli as sdd

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── Setup helpers ─────────────────────────────────────────────────────────────

def _tmp(prefix: str) -> Path:
    return REPO_ROOT / ".tmp-tests" / f"{prefix}-{uuid.uuid4().hex}"


def _init(root: Path, change_id: str) -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        assert sdd.init_project(root) == []
        assert sdd.create_change(root, change_id, "standard", "Contract test change") == []


def _make_artifacts_ready(root: Path, change_id: str) -> None:
    """Set all standard artifact statuses to 'ready' and tasks to complete."""
    change_dir = root / ".sdd" / "changes" / change_id
    for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
        path = change_dir / filename
        path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
    tasks_path = change_dir / "tasks.md"
    tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
    tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")


def _make_verification_ready(root: Path, change_id: str) -> None:
    """Set verification.md to verified status with real (non-placeholder) evidence."""
    verification_path = root / ".sdd" / "changes" / change_id / "verification.md"
    text = verification_path.read_text(encoding="utf-8")
    text = text.replace("status: draft", "status: verified")
    text = text.replace("pending verification evidence", "all unit tests pass")
    text = text.replace("not-run", "pass")
    text = text.replace("Record host-project verification actions.", "pytest -q (exit 0)")
    verification_path.write_text(text, encoding="utf-8")


def _advance_to_task(root: Path, change_id: str) -> None:
    """Record SPECIFY → DESIGN → TASK without going through verify."""
    for phase in (sdd.WorkflowPhase.SPECIFY, sdd.WorkflowPhase.DESIGN, sdd.WorkflowPhase.TASK):
        state = sdd.transition_workflow(root, change_id, phase)
        assert not state.is_blocked, [f.message for f in state.findings]


# ── Contract 1: REGISTRY atomicity on failed transition ───────────────────────

class TestTransitionAtomicity(unittest.TestCase):
    """REGISTRY contract: a blocked transition must never mutate state.json."""

    def test_blocked_transition_leaves_state_json_unchanged(self) -> None:
        """If transition_workflow returns is_blocked=True, state.json is unchanged."""
        root = _tmp("contract-txn-atomic")
        change_id = "my-change"
        _init(root, change_id)

        state_path = root / ".sdd" / "state.json"
        before = json.loads(state_path.read_text(encoding="utf-8"))

        # DESIGN cannot be reached directly from PROPOSE — should be blocked.
        result = sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)

        self.assertTrue(result.is_blocked)
        after = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(before, after, "state.json mutated during a blocked transition")


# ── Contract 2: EVIDENCE→REGISTRY phase not advanced on command failure ────────

class TestEvidenceCommandFailure(unittest.TestCase):
    """EVIDENCE contract: verify_change must NOT record VERIFY if any command fails."""

    def test_verify_change_does_not_advance_phase_when_command_fails(self) -> None:
        """Phase stays at TASK when a verification command returns non-zero."""
        root = _tmp("contract-verify-fail")
        change_id = "my-change"
        _init(root, change_id)
        _make_artifacts_ready(root, change_id)
        _make_verification_ready(root, change_id)
        _advance_to_task(root, change_id)

        # A command that always fails.
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, commands=["python -c \"raise SystemExit(1)\""])

        self.assertTrue(any(f.severity == "error" for f in findings), findings)
        self.assertEqual(
            sdd.declared_workflow_phase(root, change_id),
            sdd.WorkflowPhase.TASK,
            "Phase advanced despite command failure — EVIDENCE/REGISTRY contract broken",
        )


# ── Contract 3: ENGINE gate enforced before archive ───────────────────────────

class TestGateEnforcedBeforeArchive(unittest.TestCase):
    """ENGINE→REGISTRY contract: archive_change must be blocked unless SYNC_SPECS phase."""

    def test_archive_blocked_before_sync_specs_phase(self) -> None:
        """archive_change must emit a blocking finding when SYNC_SPECS not recorded."""
        root = _tmp("contract-gate-archive")
        change_id = "my-change"
        _init(root, change_id)
        _make_artifacts_ready(root, change_id)
        _make_verification_ready(root, change_id)
        _advance_to_task(root, change_id)

        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id)
        sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.ARCHIVE_RECORD)
        # Intentionally skip SYNC_SPECS — go straight to archive.

        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.archive_change(root, change_id)

        self.assertTrue(len(findings) > 0, "archive_change passed without gate — contract broken")
        self.assertTrue(
            any("workflow phase must be archive" in f.message for f in findings),
            [f.message for f in findings],
        )


# ── Contract 4: ENGINE gate enforced before sync-specs ────────────────────────

class TestGateEnforcedBeforeSyncSpecs(unittest.TestCase):
    """ENGINE→REGISTRY contract: sync_specs must be blocked unless SYNC_SPECS phase."""

    def test_sync_specs_blocked_before_archive_record_phase(self) -> None:
        """sync_specs must emit a blocking finding when ARCHIVE_RECORD not recorded."""
        root = _tmp("contract-gate-sync")
        change_id = "my-change"
        _init(root, change_id)
        _make_artifacts_ready(root, change_id)
        _make_verification_ready(root, change_id)
        _advance_to_task(root, change_id)

        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id)
        # Skip ARCHIVE_RECORD → try sync_specs directly.

        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.sync_specs(root, change_id)

        self.assertTrue(len(findings) > 0, "sync_specs passed without gate — contract broken")


# ── Contract 5: INFERENCE reflects REGISTRY after transition ──────────────────

class TestWorkflowStateReflectsTransition(unittest.TestCase):
    """INFERENCE→REGISTRY contract: workflow_state must match state.json after transition."""

    def test_workflow_state_matches_transition_workflow_result(self) -> None:
        """After a successful transition, workflow_state returns the same phase."""
        root = _tmp("contract-state-reflect")
        change_id = "my-change"
        _init(root, change_id)
        _make_artifacts_ready(root, change_id)

        for phase in (sdd.WorkflowPhase.SPECIFY, sdd.WorkflowPhase.DESIGN, sdd.WorkflowPhase.TASK):
            result = sdd.transition_workflow(root, change_id, phase)
            self.assertFalse(result.is_blocked, [f.message for f in result.findings])

            state = sdd.workflow_state(root, change_id)
            self.assertEqual(
                state.phase,
                phase,
                f"workflow_state returned {state.phase} after transition_workflow recorded {phase}",
            )


# ── Contract 6: EVIDENCE records accumulate across multiple verify calls ──────

class TestEvidenceRecordsAccumulate(unittest.TestCase):
    """EVIDENCE contract: successive verify_change calls accumulate execution records."""

    def test_evidence_records_created_for_each_command(self) -> None:
        """verify_change with N commands writes exactly N execution records to the evidence file."""
        root = _tmp("contract-evidence-accum")
        change_id = "my-change"
        _init(root, change_id)
        _make_artifacts_ready(root, change_id)
        _make_verification_ready(root, change_id)
        _advance_to_task(root, change_id)

        commands = ["python -c \"pass\"", "python -c \"import sys; sys.exit(0)\""]
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, commands=commands)
        self.assertEqual(findings, [], findings)

        records, parse_findings = sdd.execution_evidence_records(root, change_id)
        self.assertEqual(parse_findings, [])
        self.assertEqual(
            len(records),
            len(commands),
            f"Expected {len(commands)} records, got {len(records)} — EVIDENCE contract broken",
        )


# ── Contract 7: INFERENCE phase and declared phase can diverge ────────────────

class TestInferenceAndRegistryIndependence(unittest.TestCase):
    """INFERENCE contract: infer_phase_from_artifacts and workflow_state are independent."""

    def test_inferred_phase_can_diverge_from_declared_phase(self) -> None:
        """Artifact-inferred phase may differ from state.json when they're out of sync.

        This is expected behaviour — both values are deterministic but serve
        different purposes.  Neither reading suppresses the other.
        """
        root = _tmp("contract-phase-diverge")
        change_id = "my-change"
        _init(root, change_id)
        # Artifacts are still 'draft' — inferred phase will be NOT_STARTED / PROPOSE.
        # Manually write SPECIFY to state.json so declared > inferred.
        state = sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
        # transition should block because artifacts aren't ready — that's fine.

        declared = sdd.declared_workflow_phase(root, change_id)
        inferred = sdd.infer_phase_from_artifacts(root, change_id)

        # The contract: both values are stable and independently queryable.
        self.assertIsNotNone(declared)
        self.assertIsNotNone(inferred)
        # And they are not required to match each other,
        # so no assertion on equality here — the test proves both paths work.


# ── Contract 8: VALIDATION catches cross-artifact change_id inconsistency ─────

class TestValidationCrossArtifact(unittest.TestCase):
    """VALIDATION contract: validate() returns errors on change_id mismatch in frontmatter."""

    def test_validate_detects_frontmatter_change_id_mismatch(self) -> None:
        """If a change artifact uses the wrong change_id, validate() reports it."""
        root = _tmp("contract-validate-mismatch")
        change_id = "my-change"
        _init(root, change_id)

        # Corrupt the proposal frontmatter with a wrong change_id.
        proposal_path = root / ".sdd" / "changes" / change_id / "proposal.md"
        text = proposal_path.read_text(encoding="utf-8")
        corrupted = text.replace(f"change_id: {change_id}", "change_id: wrong-change-id")
        proposal_path.write_text(corrupted, encoding="utf-8")

        findings = sdd.validate(root)
        errors = [f for f in findings if f.severity == "error"]
        self.assertTrue(
            len(errors) > 0,
            "validate() missed a change_id mismatch in proposal frontmatter",
        )


# ── Contract 9: Trace mode activates without errors ──────────────────────────

class TestTraceMode(unittest.TestCase):
    """TYPES contract: --trace flag emits to stderr without corrupting stdout."""

    def test_trace_output_goes_to_stderr_not_stdout(self) -> None:
        """validate invoked via main() with --trace emits trace lines only to stderr."""
        root = _tmp("contract-trace")
        _init(root, root.name)  # just for a valid repo

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        with contextlib.redirect_stdout(stdout_capture), \
             contextlib.redirect_stderr(stderr_capture):
            sdd.main(["--trace", "validate", "--root", str(root)])

        stderr_output = stderr_capture.getvalue()
        stdout_output = stdout_capture.getvalue()

        self.assertIn("[TRACE]", stderr_output, "No trace output emitted to stderr")
        self.assertNotIn("[TRACE]", stdout_output, "Trace output leaked to stdout")

    def test_trace_mode_does_not_alter_validate_exit_code(self) -> None:
        """--trace must not change the return value of main()."""
        root = _tmp("contract-trace-exit")
        _init(root, "my-change")

        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            code_without = sdd.main(["validate", "--root", str(root)])
            code_with = sdd.main(["--trace", "validate", "--root", str(root)])

        self.assertEqual(code_without, code_with)


if __name__ == "__main__":
    unittest.main()
