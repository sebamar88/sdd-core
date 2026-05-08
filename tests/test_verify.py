from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tomllib
import uuid
import unittest
from importlib.resources import files
from pathlib import Path

import runproof
from runproof import cli as sdd

REPO_ROOT = Path(__file__).resolve().parents[1]

_COMMAND_FILE_NAMES = [
    "sdd-propose.md",
    "ssd-specify.md",
    "sdd-design.md",
    "sdd-tasks.md",
    "sdd-verify.md",
    "sdd-status.md",
]


class TestVerify(unittest.TestCase):
    @staticmethod
    def finding_messages(findings: list[sdd.Finding]) -> list[str]:
        return [finding.message for finding in findings]

    def record_transition(self, root: Path, change_id: str, phase: sdd.WorkflowPhase) -> None:
        state = sdd.transition_workflow(root, change_id, phase)
        self.assertFalse(state.is_blocked, self.finding_messages(state.findings))
        self.assertEqual(state.phase, phase)

    def record_verify_step(self, root: Path, change_id: str) -> None:
        """Run verify_change as the single authoritative path to recording VERIFY."""
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id)
        self.assertEqual(findings, [], findings)

    def record_standard_ready_transitions(self, root: Path, change_id: str) -> None:
        for phase in [
            sdd.WorkflowPhase.SPECIFY,
            sdd.WorkflowPhase.DESIGN,
            sdd.WorkflowPhase.TASK,
        ]:
            self.record_transition(root, change_id, phase)
        # VERIFY must go through verify_change, not transition
        self.record_verify_step(root, change_id)
        for phase in [
            sdd.WorkflowPhase.ARCHIVE_RECORD,
            sdd.WorkflowPhase.SYNC_SPECS,
        ]:
            self.record_transition(root, change_id, phase)

    def test_verify_change_blocks_when_task_phase_not_recorded(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-no-task-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        findings = sdd.verify_change(root, change_id)
        self.assertEqual(len(findings), 1)
        self.assertIn("workflow phase must be task", findings[0].message)

    def test_verify_change_blocks_placeholder_evidence(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-placeholder-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        # Record TASK phase without real evidence so verify_change can be called
        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        # verification.md still has placeholder evidence but status: verified
        verification_path = change_dir / "verification.md"
        verification_text = verification_path.read_text(encoding="utf-8")
        verification_text = verification_text.replace("status: draft", "status: verified")
        verification_path.write_text(verification_text, encoding="utf-8")

        findings = sdd.verify_change(root, change_id)
        messages = self.finding_messages(findings)
        self.assertTrue(any("placeholder" in m for m in messages))

    def test_verify_change_records_verify_phase_when_evidence_is_present(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-ok-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        verification_path = change_dir / "verification.md"
        verification_text = verification_path.read_text(encoding="utf-8")
        verification_text = verification_text.replace("status: draft", "status: verified")
        verification_text = verification_text.replace("pending verification evidence", "all unit tests pass")
        verification_text = verification_text.replace("not-run", "pass")
        verification_text = verification_text.replace("Record host-project verification actions.", "pytest -q (exit 0)")
        verification_path.write_text(verification_text, encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id)

        self.assertEqual(findings, [])
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

    def test_verify_change_executes_command_and_records_evidence(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-exec-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        command = f'"{sys.executable}" -c "print(123)"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [command], require_command=True)

        self.assertEqual(findings, [])
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)
        self.assertEqual(sdd.validate_execution_evidence(root, change_id), [])
        evidence_path = root / ".runproof" / "evidence" / change_id / "verification.jsonl"
        self.assertTrue(evidence_path.is_file())
        records = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(records[0]["passed"])
        verification_text = (change_dir / "verification.md").read_text(encoding="utf-8")
        self.assertIn("status: verified", verification_text)
        self.assertIn("Execution Evidence", verification_text)

    def test_workflow_engine_execute_runs_verify_command(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"engine-exec-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        engine = sdd.WorkflowEngine(root)
        command = f'"{sys.executable}" -c "print(456)"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = engine.execute(change_id, "verify", verification_commands=[command], require_command=True)

        self.assertEqual(findings, [])
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

    def test_verify_change_blocks_failed_execution_command(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-exec-fail-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        command = f'"{sys.executable}" -c "import sys; sys.exit(7)"'
        findings = sdd.verify_change(root, change_id, [command], require_command=True)

        self.assertEqual(len(findings), 1)
        self.assertIn("verification command failed", findings[0].message)
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.TASK)

    def test_validate_verification_evidence_blocks_placeholder_commands_section(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"evidence-placeholder-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        verification_path = root / ".runproof" / "changes" / change_id / "verification.md"
        # Default template still has the placeholder Commands line
        findings = sdd.validate_verification_evidence(verification_path)
        messages = self.finding_messages(findings)
        self.assertTrue(any("placeholder" in m for m in messages))

    def test_public_verify_change_is_exported(self) -> None:
        self.assertIs(runproof.verify_change, sdd.verify_change)
        self.assertIs(runproof.validate_verification_evidence, sdd.validate_verification_evidence)
        self.assertIs(runproof.validate_execution_evidence, sdd.validate_execution_evidence)

    def test_gate_command_is_exported(self) -> None:
        self.assertIs(runproof.gate_command, sdd.gate_command)

    def test_archive_blocks_when_artifact_edited_after_archive_phase_recorded(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"gate-stale-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "tasks.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        verification_path = change_dir / "verification.md"
        verification_text = verification_path.read_text(encoding="utf-8")
        verification_text = verification_text.replace("status: draft", "status: verified")
        verification_text = verification_text.replace("pending verification evidence", "unit test evidence")
        verification_text = verification_text.replace("not-run", "pass")
        verification_text = verification_text.replace("Record host-project verification actions.", "pytest -q (exit 0)")
        verification_path.write_text(verification_text, encoding="utf-8")

        self.record_standard_ready_transitions(root, change_id)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.sync_specs(root, change_id), [])

        # ARCHIVE is now recorded. Silently edit an artifact.
        proposal_path = change_dir / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8") + "\n<!-- silent edit -->", encoding="utf-8")

        findings = sdd.archive_change(root, change_id)
        self.assertEqual(len(findings), 1)
        self.assertIn("artifact checksum is stale", findings[0].message)
        self.assertIn("runproof transition", findings[0].message)

    def test_verify_does_not_block_when_verification_md_edited_after_task(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-expects-edit-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        # TASK recorded with checksum A. Now edit verification.md (expected workflow).
        verification_path = change_dir / "verification.md"
        verification_text = verification_path.read_text(encoding="utf-8")
        verification_text = verification_text.replace("status: draft", "status: verified")
        verification_text = verification_text.replace("pending verification evidence", "unit test evidence")
        verification_text = verification_text.replace("not-run", "pass")
        verification_text = verification_text.replace("Record host-project verification actions.", "pytest -q (exit 0)")
        verification_path.write_text(verification_text, encoding="utf-8")

        # Checksum is stale (B != A), but verify must NOT block — editing verification.md is the point.
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id)

        self.assertEqual(findings, [])
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

    def test_gate_command_check_checksum_false_ignores_stale_artifacts(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"gate-no-checksum-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        # stale checksum
        (change_dir / "proposal.md").write_text(
            (change_dir / "proposal.md").read_text(encoding="utf-8") + "\n<!-- silent -->", encoding="utf-8"
        )

        # gate_command with check_checksum=False must pass despite stale checksum
        findings = sdd.gate_command(root, change_id, sdd.WorkflowPhase.TASK, check_checksum=False)
        self.assertEqual(findings, [])

        # gate_command with check_checksum=True must block
        findings = sdd.gate_command(root, change_id, sdd.WorkflowPhase.TASK, check_checksum=True)
        self.assertEqual(len(findings), 1)
        self.assertIn("artifact checksum is stale", findings[0].message)

    # --- WorkflowEngine and COMMAND_GATES ---

    def test_command_gates_contains_all_gated_commands(self) -> None:
        self.assertIn("verify", sdd.COMMAND_GATES)
        self.assertIn("sync-specs", sdd.COMMAND_GATES)
        self.assertIn("archive", sdd.COMMAND_GATES)
        # verify must NOT check checksum; sync-specs and archive MUST
        self.assertFalse(sdd.COMMAND_GATES["verify"][1])
        self.assertTrue(sdd.COMMAND_GATES["sync-specs"][1])
        self.assertTrue(sdd.COMMAND_GATES["archive"][1])

    def test_workflow_engine_guard_blocks_before_required_phase(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"engine-guard-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        engine = sdd.WorkflowEngine(root)
        # no phase recorded yet — all gated commands must block
        for command in sdd.COMMAND_GATES:
            findings = engine.guard(change_id, command)
            self.assertTrue(len(findings) > 0, f"expected block for command '{command}'")

    def test_workflow_engine_guard_rejects_unknown_command(self) -> None:
        engine = sdd.WorkflowEngine(REPO_ROOT)
        findings = engine.guard("any-change", "made-up-command")
        self.assertEqual(len(findings), 1)
        self.assertIn("no gate registered", findings[0].message)

    def test_workflow_engine_allowed_commands_reflects_state(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"engine-allowed-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        engine = sdd.WorkflowEngine(root)
        # no phase recorded — no commands allowed
        self.assertEqual(engine.allowed_commands(change_id), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
            sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.TASK)

        # TASK recorded — only "verify" should be allowed (no checksum, correct phase)
        allowed = engine.allowed_commands(change_id)
        self.assertIn("verify", allowed)
        self.assertNotIn("archive", allowed)
        self.assertNotIn("sync-specs", allowed)

    def test_workflow_engine_is_exported(self) -> None:
        self.assertIs(runproof.WorkflowEngine, sdd.WorkflowEngine)
        self.assertIs(runproof.COMMAND_GATES, sdd.COMMAND_GATES)

    # --- validate_verification_matrix ---

    def test_validate_verification_matrix_blocks_when_no_passing_row(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"matrix-no-pass-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        verification_path = root / ".runproof" / "changes" / change_id / "verification.md"
        # Replace placeholder text but leave status as a non-passing value
        text = verification_path.read_text(encoding="utf-8")
        text = text.replace("pending verification evidence", "unit test evidence")
        text = text.replace("not-run", "fail")  # 'fail' is not a passing status
        text = text.replace("Record host-project verification actions.", "pytest -q")
        verification_path.write_text(text, encoding="utf-8")

        findings = sdd.validate_verification_matrix(verification_path)
        self.assertEqual(len(findings), 1)
        self.assertIn("no passing rows", findings[0].message)

    def test_validate_verification_matrix_passes_with_recognized_status(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"matrix-pass-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        verification_path = root / ".runproof" / "changes" / change_id / "verification.md"
        text = verification_path.read_text(encoding="utf-8")
        text = text.replace("pending verification evidence", "unit test evidence")
        text = text.replace("not-run", "pass")
        text = text.replace("Record host-project verification actions.", "pytest -q")
        verification_path.write_text(text, encoding="utf-8")

        findings = sdd.validate_verification_matrix(verification_path)
        self.assertEqual(findings, [])

    def test_validate_verification_matrix_is_exported(self) -> None:
        self.assertIs(runproof.validate_verification_matrix, sdd.validate_verification_matrix)

    def test_check_change_blocks_when_matrix_has_no_passing_row(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"check-matrix-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "tasks.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")

        # verification.md has status:verified but matrix status is 'fail' (not a passing value)
        verification_path = change_dir / "verification.md"
        text = verification_path.read_text(encoding="utf-8")
        text = text.replace("status: draft", "status: verified")
        text = text.replace("pending verification evidence", "unit test evidence")
        text = text.replace("not-run", "fail")
        text = text.replace("Record host-project verification actions.", "pytest -q")
        verification_path.write_text(text, encoding="utf-8")

        findings = sdd.check_change(root, change_id)
        messages = self.finding_messages(findings)
        self.assertTrue(any("no passing rows" in m for m in messages))


if __name__ == "__main__":
    unittest.main()
