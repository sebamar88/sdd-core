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


class TestExecutionEvidence(unittest.TestCase):
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

    def test_execution_evidence_record_has_required_fields(self) -> None:
        """Verify the evidence JSON contains all required fields."""
        root = REPO_ROOT / ".tmp-tests" / f"evidence-schema-{uuid.uuid4().hex}"
        change_id = "evidence-schema"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, ["echo evidence-fields"])
        self.assertEqual(findings, [])

        records, findings = sdd.execution_evidence_records(root, change_id)
        self.assertEqual(findings, [])
        self.assertGreater(len(records), 0)

        rec = records[0]
        for field in ("schema", "id", "change_id", "phase", "command", "exit_code",
                      "passed", "recorded_at", "log_path", "output_checksum", "duration_seconds"):
            self.assertIn(field, rec, f"missing field: {field}")
        self.assertEqual(rec["schema"], "sdd.execution-evidence.v1")
        self.assertEqual(rec["command"], "echo evidence-fields")
        self.assertEqual(rec["exit_code"], 0)
        self.assertTrue(rec["passed"])
        self.assertIsInstance(rec["duration_seconds"], float)

    def test_execution_evidence_log_file_is_checksummed(self) -> None:
        """The output log exists and its SHA-256 matches output_checksum."""
        import hashlib
        root = REPO_ROOT / ".tmp-tests" / f"evidence-checksum-{uuid.uuid4().hex}"
        change_id = "evidence-checksum"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id, ["echo checksum-target"])

        records, _ = sdd.execution_evidence_records(root, change_id)
        self.assertGreater(len(records), 0)
        rec = records[0]
        log_path = root / rec["log_path"]
        self.assertTrue(log_path.is_file())
        actual = hashlib.sha256(log_path.read_text(encoding="utf-8").encode()).hexdigest()
        self.assertEqual(actual, rec["output_checksum"])

    def test_tampered_evidence_log_fails_validation(self) -> None:
        """Modifying the log after recording must fail validate_execution_evidence."""
        root = REPO_ROOT / ".tmp-tests" / f"evidence-tamper-{uuid.uuid4().hex}"
        change_id = "evidence-tamper"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id, ["echo tamper-me"])

        records, _ = sdd.execution_evidence_records(root, change_id)
        log_path = root / records[0]["log_path"]
        log_path.write_text("tampered content", encoding="utf-8")

        findings = sdd.validate_execution_evidence(root, change_id)
        self.assertTrue(any("checksum" in f.message for f in findings))

    def test_failed_command_records_evidence_and_blocks_verify(self) -> None:
        """A non-zero exit code must record evidence AND return a blocking finding."""
        root = REPO_ROOT / ".tmp-tests" / f"evidence-fail-{uuid.uuid4().hex}"
        change_id = "evidence-fail"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        fail_cmd = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [fail_cmd])

        self.assertTrue(any(f.severity == "error" for f in findings))
        # Evidence must still have been recorded despite failure.
        records, _ = sdd.execution_evidence_records(root, change_id)
        self.assertTrue(any(r["command"] == fail_cmd and not r["passed"] for r in records))

    # ── Execution truth: black-box output capture ──────────────────────────

    def test_execution_evidence_records_exact_exit_code(self) -> None:
        """The persisted exit_code must equal the real process exit code, not just pass/fail."""
        root = REPO_ROOT / ".tmp-tests" / f"evidence-exitcode-{uuid.uuid4().hex}"
        change_id = "evidence-exitcode"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        cmd = f'"{sys.executable}" -c "import sys; sys.exit(42)"'
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id, [cmd])

        records, _ = sdd.execution_evidence_records(root, change_id)
        rec = next(r for r in records if r["command"] == cmd)
        self.assertEqual(rec["exit_code"], 42)
        self.assertFalse(rec["passed"])

    def test_execution_evidence_log_captures_stdout(self) -> None:
        """The log file must contain the actual stdout produced by the command."""
        import hashlib
        root = REPO_ROOT / ".tmp-tests" / f"evidence-stdout-{uuid.uuid4().hex}"
        change_id = "evidence-stdout"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        sentinel = "SENTINEL_STDOUT_XYZ_87654"
        cmd = f'"{sys.executable}" -c "print(\'{sentinel}\')"'
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id, [cmd])

        records, _ = sdd.execution_evidence_records(root, change_id)
        rec = next(r for r in records if r["command"] == cmd)
        log_path = root / rec["log_path"]
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn(sentinel, log_content)
        # Checksum must still be valid after reading.
        actual_checksum = hashlib.sha256(log_content.encode("utf-8")).hexdigest()
        self.assertEqual(actual_checksum, rec["output_checksum"])

    def test_execution_evidence_log_captures_stderr(self) -> None:
        """The log file must contain the actual stderr produced by the command."""
        root = REPO_ROOT / ".tmp-tests" / f"evidence-stderr-{uuid.uuid4().hex}"
        change_id = "evidence-stderr"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)
        sentinel = "SENTINEL_STDERR_XYZ_13579"
        cmd = f'"{sys.executable}" -c "import sys; sys.stderr.write(\'{sentinel}\\n\')"'
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.verify_change(root, change_id, [cmd])

        records, _ = sdd.execution_evidence_records(root, change_id)
        rec = next(r for r in records if r["command"] == cmd)
        log_path = root / rec["log_path"]
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn(sentinel, log_content)

    # ── Anti-hallucination: lie detection tests ───────────────────────────────

    def test_require_command_flag_blocks_verify_when_no_commands_given(self) -> None:
        """When CI policy sets require_command=True, passing zero commands must block.

        This is the enforcement path of `runproof verify --require-command`:
        an agent cannot skip execution evidence simply by omitting --command.
        """
        root = REPO_ROOT / ".tmp-tests" / f"lie-nocommand-{uuid.uuid4().hex}"
        change_id = "lie-nocommand"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)

        findings = sdd.verify_change(root, change_id, [], require_command=True)

        self.assertTrue(any(f.severity == "error" for f in findings))
        self.assertTrue(any("--command" in f.message or "command" in f.message.lower() for f in findings))
        # Phase must NOT advance — still at TASK.
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.TASK)

    def test_guard_require_evidence_catches_verify_without_command(self) -> None:
        """Core anti-hallucination guarantee: guard catches an agent that claims
        'I ran the tests' by manually writing a perfect verification.md but never
        executing any command.

        Scenario:
          1. Agent advances to TASK.
          2. Agent manually writes verification.md (status: verified, passing matrix,
             no placeholder text) — looks legitimate.
          3. verify_change() with no commands succeeds (manual evidence is allowed).
          4. BUT: guard --require-execution-evidence BLOCKS.
             This is the governance catch: the claim has no cryptographic proof.
        """
        root = REPO_ROOT / ".tmp-tests" / f"lie-noevidence-{uuid.uuid4().hex}"
        change_id = "lie-noevidence"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)

        # Manually write a verification.md that looks legitimate.
        verification_path = change_dir / "verification.md"
        text = verification_path.read_text(encoding="utf-8")
        text = sdd.set_frontmatter_value(text, "status", "verified")
        text = text.replace("pending verification evidence", "all tests passed manually")
        text = text.replace("not-run", "pass")
        text = text.replace("Record host-project verification actions.", "pytest -q exit 0")
        verification_path.write_text(text, encoding="utf-8")

        # verify_change without commands succeeds — manual evidence is accepted.
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id)
        self.assertEqual(findings, [], "verify_change without commands should accept manual evidence")
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

        # guard --require-execution-evidence CATCHES IT.
        guard_findings = sdd.guard_repository(root, require_execution_evidence=True)
        self.assertTrue(
            any(f.severity == "error" for f in guard_findings),
            "guard must block when no execution evidence exists",
        )
        self.assertTrue(
            any("evidence" in f.message.lower() for f in guard_findings),
            f"expected evidence-related error, got: {[f.message for f in guard_findings]}",
        )

    def test_partial_command_failure_blocks_verify_but_records_all_evidence(self) -> None:
        """When multiple commands are given, ALL are run and ALL are recorded.
        A single failure blocks verify — governance does not stop at the first pass.

        This prevents the lie: 'the first test passed so the change is verified'
        while a later, critical test was silently failing.
        """
        root = REPO_ROOT / ".tmp-tests" / f"lie-partial-{uuid.uuid4().hex}"
        change_id = "lie-partial"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)

        pass_cmd = f'"{sys.executable}" -c "print(\'ok\')"'
        fail_cmd = f'"{sys.executable}" -c "import sys; sys.exit(3)"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [pass_cmd, fail_cmd])

        # Verify is blocked.
        self.assertTrue(any(f.severity == "error" for f in findings))
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.TASK)

        # BOTH commands were recorded — governance saw both.
        records, _ = sdd.execution_evidence_records(root, change_id)
        commands_recorded = {r["command"] for r in records}
        self.assertIn(pass_cmd, commands_recorded, "passing command must still be recorded")
        self.assertIn(fail_cmd, commands_recorded, "failing command must be recorded")

        # The pass record is marked passed; the fail record is marked failed.
        pass_rec = next(r for r in records if r["command"] == pass_cmd)
        fail_rec = next(r for r in records if r["command"] == fail_cmd)
        self.assertTrue(pass_rec["passed"])
        self.assertFalse(fail_rec["passed"])
        self.assertEqual(fail_rec["exit_code"], 3)

    def test_execution_allows_empty_stdout_for_successful_command(self) -> None:
        """Commands that produce no stdout (e.g. `true`, `test -f`) are valid.

        Evidence strength comes from exit_code + log + SHA-256, not from
        output volume.  Empty stdout must NOT block verify.
        """
        import hashlib
        root = REPO_ROOT / ".tmp-tests" / f"empty-stdout-{uuid.uuid4().hex}"
        change_id = "empty-stdout"
        change_dir = self._make_quick_change(root, change_id)
        self._advance_to_task(root, change_id, change_dir)

        # Command that succeeds with zero stdout and zero stderr.
        cmd = f'"{sys.executable}" -c "pass"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [cmd])

        # Verify succeeds — empty output is not an error.
        self.assertEqual(findings, [])
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

        # Evidence is fully recorded even with empty output.
        records, rec_findings = sdd.execution_evidence_records(root, change_id)
        self.assertEqual(rec_findings, [])
        rec = next(r for r in records if r["command"] == cmd)
        self.assertTrue(rec["passed"])
        self.assertEqual(rec["exit_code"], 0)

        # Log file exists and checksum is valid (of the metadata-only content).
        log_path = root / rec["log_path"]
        self.assertTrue(log_path.is_file())
        log_content = log_path.read_text(encoding="utf-8")
        actual_checksum = hashlib.sha256(log_content.encode("utf-8")).hexdigest()
        self.assertEqual(actual_checksum, rec["output_checksum"])

        # validate_execution_evidence also passes.
        self.assertEqual(sdd.validate_execution_evidence(root, change_id), [])


if __name__ == "__main__":
    unittest.main()
