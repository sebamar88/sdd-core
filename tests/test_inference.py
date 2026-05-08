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


class TestInference(unittest.TestCase):
    @staticmethod
    def finding_messages(findings: list[sdd.Finding]) -> list[str]:
        return [finding.message for finding in findings]

    def record_transition(self, root: Path, change_id: str, phase: sdd.WorkflowPhase) -> None:
        state = sdd.transition_workflow(root, change_id, phase)
        self.assertFalse(state.is_blocked, self.finding_messages(state.findings))
        self.assertEqual(state.phase, phase)

    def test_workflow_state_prefers_declared_phase_over_artifact_inference(self) -> None:
        """workflow_state() returns the state.json declared phase even when artifacts
        could support a higher phase.  Only structural blockers (missing/blocked
        artifacts) override the recorded phase."""
        root = REPO_ROOT / ".tmp-tests" / f"state-primary-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            # run_workflow records PROPOSE in state.json
            self.assertEqual(sdd.run_workflow(root, change_id, "standard", "Guard login", create=True).phase, sdd.WorkflowPhase.PROPOSE)

        # Advance artifacts to "tasks ready" level so artifact inference would return VERIFY
        change_dir = root / ".runproof" / "changes" / change_id
        for filename in ["proposal.md", "delta-spec.md", "design.md", "tasks.md"]:
            path = change_dir / filename
            path.write_text(path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        tasks_path = change_dir / "tasks.md"
        tasks_path.write_text(tasks_path.read_text(encoding="utf-8").replace("- [ ]", "- [x]"), encoding="utf-8")

        # Artifact inference now points to VERIFY — but state.json still says PROPOSE
        self.assertEqual(sdd.infer_phase_from_artifacts(root, change_id), sdd.WorkflowPhase.VERIFY)
        # workflow_state() must return the declared phase, not the artifact-inferred one
        self.assertEqual(sdd.workflow_state(root, change_id).phase, sdd.WorkflowPhase.PROPOSE)

    def test_infer_phase_from_artifacts_ignores_state_json(self) -> None:
        """infer_phase_from_artifacts() always reflects artifact content regardless
        of what is recorded in state.json."""
        root = REPO_ROOT / ".tmp-tests" / f"infer-artifacts-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            # run_workflow records PROPOSE
            self.assertEqual(sdd.run_workflow(root, change_id, "standard", "Guard login", create=True).phase, sdd.WorkflowPhase.PROPOSE)

        # Artifact level: only proposal.md ready — inference should return SPECIFY
        change_dir = root / ".runproof" / "changes" / change_id
        proposal_path = change_dir / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        # state.json says PROPOSE; artifact inference says SPECIFY (proposal ready)
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.PROPOSE)
        self.assertEqual(sdd.infer_phase_from_artifacts(root, change_id), sdd.WorkflowPhase.SPECIFY)
        # workflow_state() returns PROPOSE (declared), not SPECIFY
        self.assertEqual(sdd.workflow_state(root, change_id).phase, sdd.WorkflowPhase.PROPOSE)

    def test_infer_phase_from_artifacts_is_exported(self) -> None:
        self.assertIs(runproof.infer_phase_from_artifacts, sdd.infer_phase_from_artifacts)

    def test_transition_blocks_when_artifacts_behind_target_despite_declared_phase(self) -> None:
        """Even when state.json declares a phase that allows the requested transition,
        the artifact readiness check must still block if artifacts don't support it."""
        root = REPO_ROOT / ".tmp-tests" / f"transition-artifact-gate-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.run_workflow(root, change_id, "standard", "Guard login", create=True).phase, sdd.WorkflowPhase.PROPOSE)

        # Record SPECIFY in state.json without the artifacts being ready
        # (do it by manually recording the transition after making proposal "ready")
        proposal_path = root / ".runproof" / "changes" / change_id / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        self.record_transition(root, change_id, sdd.WorkflowPhase.SPECIFY)

        # state.json now says SPECIFY; delta-spec.md is still draft
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.SPECIFY)
        # SPECIFY allows DESIGN — but artifact phase is still SPECIFY (delta-spec.md is draft)
        # phase_is_supported(DESIGN, SPECIFY) → 30 <= 20 → False → blocked
        blocked = sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("artifact phase" in finding.message for finding in blocked.findings))

    # ── auto loop tests ───────────────────────────────────────────────────────

    def _make_quick_change(self, root: Path, change_id: str) -> Path:
        """Init repo and create a *quick* profile change. Return the change dir."""
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "quick", "Test change"), [])
        return root / ".runproof" / "changes" / change_id

    def _fill_proposal(self, change_dir: Path) -> None:
        p = change_dir / "proposal.md"
        text = p.read_text(encoding="utf-8")
        text = sdd.set_frontmatter_value(text, "status", "ready")
        p.write_text(text, encoding="utf-8")

    def _fill_tasks(self, change_dir: Path) -> None:
        p = change_dir / "tasks.md"
        text = p.read_text(encoding="utf-8").replace("- [ ]", "- [x]")
        text = sdd.set_frontmatter_value(text, "status", "ready")
        p.write_text(text, encoding="utf-8")

    def _advance_to_task(self, root: Path, change_id: str, change_dir: Path) -> None:
        """Fill artifacts and drain auto loop until it pauses at TASK (verify gate)."""
        self._fill_proposal(change_dir)
        self._fill_tasks(change_dir)
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(20):
                result = sdd._auto_advance(root, change_id)
                if result.needs_human_work or result.step.is_complete or not result.executed_command:
                    break
        self.assertEqual(result.step.phase, sdd.WorkflowPhase.TASK)

    def test_auto_advance_pauses_at_propose_when_artifacts_not_ready(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"auto-pause-{uuid.uuid4().hex}"
        change_id = "auto-pause-test"
        self._make_quick_change(root, change_id)

        result = sdd._auto_advance(root, change_id)

        self.assertTrue(result.needs_human_work)
        self.assertEqual(result.step.phase, sdd.WorkflowPhase.PROPOSE)
        self.assertIsNone(result.executed_command)

    def test_auto_advance_records_transition_when_proposal_ready(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"auto-transition-{uuid.uuid4().hex}"
        change_id = "auto-trans-test"
        change_dir = self._make_quick_change(root, change_id)
        self._fill_proposal(change_dir)

        result = sdd._auto_advance(root, change_id)

        self.assertIsNotNone(result.executed_command)
        self.assertIn("transition", result.executed_command)
        self.assertFalse(result.needs_human_work)

    def test_auto_loop_pauses_at_task_when_verify_required(self) -> None:
        """After tasks are done the loop must stop at TASK — VERIFY requires verify_change."""
        root = REPO_ROOT / ".tmp-tests" / f"auto-loop-task-{uuid.uuid4().hex}"
        change_id = "auto-loop-task"
        change_dir = self._make_quick_change(root, change_id)
        self._fill_proposal(change_dir)
        self._fill_tasks(change_dir)

        steps = 0
        with contextlib.redirect_stdout(io.StringIO()):
            while True:
                result = sdd._auto_advance(root, change_id)
                if result.executed_command:
                    steps += 1
                if result.needs_human_work or result.step.is_complete or not result.executed_command:
                    break

        # Loop stops at TASK; VERIFY is a restricted phase requiring verify_change.
        self.assertTrue(result.needs_human_work)
        self.assertEqual(result.step.phase, sdd.WorkflowPhase.TASK)
        self.assertGreater(steps, 0, "at least one transition should have executed")

    def test_auto_loop_archives_after_verify(self) -> None:
        """Full lifecycle: init → fill → verify → auto closes."""
        root = REPO_ROOT / ".tmp-tests" / f"auto-full-{uuid.uuid4().hex}"
        change_id = "auto-full-lifecycle"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)

        # Record verification with real evidence.
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, ["echo loop-verified"])
        self.assertEqual(findings, [])

        # Loop should now close the change (archive).
        steps = 0
        with contextlib.redirect_stdout(io.StringIO()):
            while True:
                result = sdd._auto_advance(root, change_id)
                if result.executed_command:
                    steps += 1
                if result.needs_human_work or result.step.is_complete or result.step.is_blocked or not result.executed_command:
                    break

        self.assertTrue(result.step.is_complete)
        self.assertGreater(steps, 0)
        archive_root = root / ".runproof" / "archive"
        archived = [p for p in archive_root.iterdir() if p.is_dir()]
        self.assertEqual(len(archived), 1)

    def test_auto_advance_cannot_skip_verify_phase(self) -> None:
        """Tasks done → loop stops at TASK. ARCHIVE must never appear without VERIFY."""
        root = REPO_ROOT / ".tmp-tests" / f"auto-no-skip-verify-{uuid.uuid4().hex}"
        change_id = "auto-no-skip"
        change_dir = self._make_quick_change(root, change_id)
        self._fill_proposal(change_dir)
        self._fill_tasks(change_dir)

        phases_seen: list[sdd.WorkflowPhase] = []
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(20):
                result = sdd._auto_advance(root, change_id)
                phases_seen.append(result.step.phase)
                if result.needs_human_work or result.step.is_complete or not result.executed_command:
                    break

        # Loop stops at TASK; ARCHIVE/ARCHIVED must never be reached without verify_change.
        self.assertEqual(phases_seen[-1], sdd.WorkflowPhase.TASK)
        self.assertNotIn(sdd.WorkflowPhase.ARCHIVE, phases_seen)
        self.assertNotIn(sdd.WorkflowPhase.ARCHIVED, phases_seen)


if __name__ == "__main__":
    unittest.main()
