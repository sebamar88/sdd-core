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
    "sdd-specify.md",
    "sdd-design.md",
    "sdd-tasks.md",
    "sdd-verify.md",
    "sdd-status.md",
]


class TestWorkflow(unittest.TestCase):
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

    def test_end_to_end_standard_change_syncs_and_archives(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"e2e-{uuid.uuid4().hex}"
        change_id = "document-example"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Document example"), [])

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

        self.assertEqual(sdd.check_change(root, change_id), [])
        self.record_standard_ready_transitions(root, change_id)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.sync_specs(root, change_id), [])
            self.assertEqual(sdd.archive_change(root, change_id), [])

        self.assertFalse(change_dir.exists())
        self.assertTrue((root / ".runproof" / "specs" / change_id / "spec.md").is_file())
        archives = list((root / ".runproof" / "archive").glob(f"*-{change_id}"))
        self.assertEqual(len(archives), 1)

    def test_archive_rejects_verified_change_before_spec_sync(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"archive-before-sync-{uuid.uuid4().hex}"
        change_id = "document-example"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Document example"), [])

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
        findings = sdd.archive_change(root, change_id)
        self.assertEqual(len(findings), 1)
        self.assertIn("workflow phase must be archive", findings[0].message)

    def test_run_workflow_creates_missing_change_and_reports_propose_phase(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"workflow-create-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            state = sdd.run_workflow(root, "guard-login", "standard", "Guard login", create=True)

        self.assertEqual(state.phase, sdd.WorkflowPhase.PROPOSE)
        self.assertEqual(state.profile, "standard")
        self.assertEqual(state.findings, [])
        self.assertTrue((root / ".runproof" / "changes" / "guard-login" / "proposal.md").is_file())
        self.assertEqual(sdd.declared_workflow_phase(root, "guard-login"), sdd.WorkflowPhase.PROPOSE)

    def test_transition_blocks_phase_when_artifacts_do_not_support_it(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"transition-block-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            state = sdd.run_workflow(root, "guard-login", "standard", "Guard login", create=True)

        self.assertEqual(state.phase, sdd.WorkflowPhase.PROPOSE)
        blocked = sdd.transition_workflow(root, "guard-login", sdd.WorkflowPhase.DESIGN)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("invalid workflow transition" in finding.message for finding in blocked.findings))

    def test_transition_records_next_phase_after_artifact_readiness(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"transition-ready-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.run_workflow(root, change_id, "standard", "Guard login", create=True).phase, sdd.WorkflowPhase.PROPOSE)

        proposal_path = root / ".runproof" / "changes" / change_id / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        transitioned = sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.SPECIFY)
        self.assertFalse(transitioned.is_blocked, self.finding_messages(transitioned.findings))
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.SPECIFY)

    def test_guard_strict_state_detects_unrecorded_artifact_mutation(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"strict-state-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.run_workflow(root, change_id, "standard", "Guard login", create=True).phase, sdd.WorkflowPhase.PROPOSE)

        proposal_path = root / ".runproof" / "changes" / change_id / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        findings = sdd.guard_repository(root, require_active_change=True, strict_state=True)
        self.assertTrue(any("workflow state checksum is stale" in finding.message for finding in findings))

        self.record_transition(root, change_id, sdd.WorkflowPhase.SPECIFY)
        self.assertEqual(sdd.guard_repository(root, require_active_change=True, strict_state=True), [])

    def test_workflow_state_enforces_phase_order_before_spec_sync(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"workflow-order-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        self.assertEqual(sdd.infer_phase_from_artifacts(root, change_id), sdd.WorkflowPhase.PROPOSE)

        for filename in ["proposal.md", "delta-spec.md", "design.md", "tasks.md", "archive.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")

        state = sdd.infer_state_from_artifacts(root, change_id)
        self.assertEqual(state.phase, sdd.WorkflowPhase.VERIFY)
        self.assertIn("verification.md", state.next_action)

        verification_path = change_dir / "verification.md"
        verification_text = verification_path.read_text(encoding="utf-8")
        verification_text = verification_text.replace("status: draft", "status: verified")
        verification_text = verification_text.replace("pending verification evidence", "unit test evidence")
        verification_text = verification_text.replace("not-run", "pass")
        verification_text = verification_text.replace("Record host-project verification actions.", "pytest -q (exit 0)")
        verification_path.write_text(verification_text, encoding="utf-8")

        self.assertEqual(sdd.infer_phase_from_artifacts(root, change_id), sdd.WorkflowPhase.SYNC_SPECS)
        self.record_standard_ready_transitions(root, change_id)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.sync_specs(root, change_id), [])

        self.assertEqual(sdd.workflow_state(root, change_id).phase, sdd.WorkflowPhase.ARCHIVE)

    def test_workflow_state_requires_archive_record_before_spec_sync(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"workflow-archive-record-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "tasks.md"]:
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

        state = sdd.infer_state_from_artifacts(root, change_id)
        self.assertEqual(state.phase, sdd.WorkflowPhase.ARCHIVE_RECORD)
        self.assertIn("archive.md", state.next_action)

    def test_run_workflow_no_create_reports_not_started(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"workflow-no-create-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            state = sdd.run_workflow(root, "guard-login", "standard", "Guard login", create=False)

        self.assertEqual(state.phase, sdd.WorkflowPhase.NOT_STARTED)
        self.assertFalse((root / ".runproof" / "changes" / "guard-login").exists())

    def test_public_workflow_orchestrator_is_exported(self) -> None:
        self.assertIs(runproof.SDDWorkflow, sdd.SDDWorkflow)
        self.assertIs(runproof.WorkflowPhase, sdd.WorkflowPhase)
        self.assertIs(runproof.WorkflowFailureKind, sdd.WorkflowFailureKind)
        self.assertIs(runproof.guard_repository, sdd.guard_repository)
        self.assertIs(runproof.install_hooks, sdd.install_hooks)
        self.assertIs(runproof.transition_workflow, sdd.transition_workflow)
        self.assertIs(runproof.declared_workflow_phase, sdd.declared_workflow_phase)

    def test_sdd_workflow_blocks_sync_before_required_phase(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"workflow-api-block-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        workflow = sdd.SDDWorkflow(root)
        with contextlib.redirect_stdout(io.StringIO()):
            result = workflow.run("guard-login", profile="standard", title="Guard login")
        self.assertTrue(result.ok)
        self.assertEqual(result.state.phase, sdd.WorkflowPhase.PROPOSE)

        blocked = workflow.sync_specs("guard-login")
        self.assertFalse(blocked.ok)
        self.assertEqual(blocked.state.phase, sdd.WorkflowPhase.BLOCKED)
        self.assertEqual(blocked.failures[0].kind, sdd.WorkflowFailureKind.PHASE_ORDER)
        self.assertIn("workflow phase must be sync-specs", blocked.failures[0].message)

    def test_sdd_workflow_transition_rejects_unknown_phase(self) -> None:
        workflow = sdd.SDDWorkflow(REPO_ROOT)

        result = workflow.transition("guard-login", "made-up")

        self.assertFalse(result.ok)
        self.assertEqual(result.state.phase, sdd.WorkflowPhase.BLOCKED)
        self.assertIn("unknown workflow phase", result.failures[0].message)

    def test_transition_blocks_verify_phase_and_demands_verify_command(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"transition-no-verify-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        blocked = sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.VERIFY)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("runproof verify" in f.message for f in blocked.findings))
        # The dedicated verify command must also be unavailable before TASK is recorded
        findings = sdd.verify_change(root, change_id)
        self.assertEqual(len(findings), 1)
        self.assertIn("workflow phase must be task", findings[0].message)

    def test_transition_blocks_archived_phase(self) -> None:
        blocked = sdd.transition_workflow(REPO_ROOT, "any-change", sdd.WorkflowPhase.ARCHIVED)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("runproof archive" in f.message for f in blocked.findings))

    def test_log_shows_history_after_transitions(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"log-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.run_workflow(root, change_id, "standard", "Guard login", create=True).phase,
                             sdd.WorkflowPhase.PROPOSE)

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = sdd.main(["log", change_id, "--root", str(root)])

        self.assertEqual(result, 0)
        output = out.getvalue()
        self.assertIn("RunProof log", output)
        self.assertIn(change_id, output)
        self.assertIn("propose", output)

    def test_log_returns_nonzero_for_unrecorded_change(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = sdd.main(["log", "not-recorded", "--root", str(REPO_ROOT)])
        self.assertEqual(result, 1)

    def test_sdd_workflow_orchestrates_sync_and_archive_when_ready(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"workflow-api-e2e-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        workflow = sdd.SDDWorkflow(root)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(workflow.run(change_id, profile="standard", title="Guard login").ok)

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

        for phase in [
            sdd.WorkflowPhase.SPECIFY,
            sdd.WorkflowPhase.DESIGN,
            sdd.WorkflowPhase.TASK,
        ]:
            transition = workflow.transition(change_id, phase)
            self.assertTrue(transition.ok, [failure.message for failure in transition.failures])

        # VERIFY must go through verify_change, not transition
        with contextlib.redirect_stdout(io.StringIO()):
            verify_findings = sdd.verify_change(workflow.root, change_id)
        self.assertEqual(verify_findings, [])

        for phase in [
            sdd.WorkflowPhase.ARCHIVE_RECORD,
            sdd.WorkflowPhase.SYNC_SPECS,
        ]:
            transition = workflow.transition(change_id, phase)
            self.assertTrue(transition.ok, [failure.message for failure in transition.failures])

        with contextlib.redirect_stdout(io.StringIO()):
            synced = workflow.sync_specs(change_id)

        self.assertTrue(synced.ok)
        self.assertEqual(synced.state.phase, sdd.WorkflowPhase.ARCHIVE)

        with contextlib.redirect_stdout(io.StringIO()):
            archived = workflow.archive(change_id)

        self.assertTrue(archived.ok)
        self.assertEqual(archived.state.phase, sdd.WorkflowPhase.ARCHIVED)
        self.assertFalse(change_dir.exists())

    def test_guard_requires_active_change_when_policy_enabled(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"guard-require-active-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        findings = sdd.guard_repository(root, require_active_change=True)
        self.assertEqual(len(findings), 1)
        self.assertIn("active SDD change is required", findings[0].message)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.create_change(root, "guard-login", "standard", "Guard login"), [])

        self.assertEqual(sdd.guard_repository(root, require_active_change=True), [])

    def test_guard_detects_manually_archived_change_without_spec_sync(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"guard-archive-sync-{uuid.uuid4().hex}"
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
        verification_path.write_text(verification_text, encoding="utf-8")

        archive_dir = root / ".runproof" / "archive" / f"2026-05-05-{change_id}"
        shutil.copytree(change_dir, archive_dir)
        shutil.rmtree(change_dir)

        findings = sdd.guard_repository(root)
        self.assertTrue(any("living spec must be synced before archive" in finding.message for finding in findings))

    def test_install_hooks_writes_pre_commit_guard(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"hooks-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        (root / ".git").mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.install_hooks(root), [])

        pre_commit = root / ".git" / "hooks" / "pre-commit"
        self.assertTrue(pre_commit.is_file())
        commit_text = pre_commit.read_text(encoding="utf-8")
        self.assertIn("runproof guard", commit_text)
        self.assertIn("--require-active-change", commit_text)
        self.assertIn("--strict-state", commit_text)

        pre_push = root / ".git" / "hooks" / "pre-push"
        self.assertTrue(pre_push.is_file())
        push_text = pre_push.read_text(encoding="utf-8")
        self.assertIn("runproof guard", push_text)
        self.assertIn("--strict-state", push_text)
        self.assertNotIn("--require-active-change", push_text)

    def test_resolve_active_change_id_returns_single_active(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"resolve-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            sdd.create_change(root, "my-change", "quick", "My change")
        result = sdd.resolve_active_change_id(root)
        self.assertEqual(result, "my-change")
        shutil.rmtree(root, ignore_errors=True)

    def test_resolve_active_change_id_returns_none_when_no_changes(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"resolve-empty-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        result = sdd.resolve_active_change_id(root)
        self.assertIsNone(result)
        shutil.rmtree(root, ignore_errors=True)

    def test_runproof_next_advances_auto_phases(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"next-{uuid.uuid4().hex}"
        change_id = "test-next"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            sdd.create_change(root, change_id, "quick", "Test next")

        # Mark proposal ready
        change_dir = root / ".runproof" / "changes" / change_id
        proposal = change_dir / "proposal.md"
        proposal.write_text(
            proposal.read_text(encoding="utf-8").replace("status: draft", "status: ready"),
            encoding="utf-8",
        )

        with contextlib.redirect_stdout(io.StringIO()):
            rc = sdd.main(["next", "--root", str(root)])

        self.assertEqual(rc, 0)
        shutil.rmtree(root, ignore_errors=True)

    def test_status_json_returns_valid_json(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"status-json-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            sdd.create_change(root, "test-change", "quick", "Test change")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sdd.main(["status", "--json", "--root", str(root)])

        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("change_id", data)
        self.assertIn("phase", data)
        self.assertIn("next_action", data)
        self.assertIn("can_auto_advance", data)
        self.assertIn("missing_artifacts", data)
        self.assertEqual(data["change_id"], "test-change")
        shutil.rmtree(root, ignore_errors=True)


class TestMarkArtifactReady(unittest.TestCase):
    """Tests for the runproof ready UX command."""

    def _init_and_create(self, root: Path, change_id: str) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Test change"), [])

    def test_ready_marks_proposal_as_ready(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ready-{uuid.uuid4().hex}"
        change_id = "add-feature"
        self._init_and_create(root, change_id)

        proposal = root / ".runproof" / "changes" / change_id / "proposal.md"
        self.assertIn("status: draft", proposal.read_text(encoding="utf-8"))

        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.mark_artifact_ready(root, change_id)

        self.assertEqual(findings, [], [f.message for f in findings])
        self.assertIn("status: ready", proposal.read_text(encoding="utf-8"))

    def test_ready_rejects_missing_change(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ready-missing-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)

        findings = sdd.mark_artifact_ready(root, "no-such-change")
        self.assertTrue(any(f.severity == "error" for f in findings))

    def test_ready_rejects_invalid_change_id(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ready-invalid-{uuid.uuid4().hex}"
        findings = sdd.mark_artifact_ready(root, "INVALID ID!")
        self.assertTrue(any(f.severity == "error" for f in findings))

    def test_ready_exported_from_package(self) -> None:
        self.assertTrue(callable(runproof.mark_artifact_ready))


if __name__ == "__main__":
    unittest.main()
