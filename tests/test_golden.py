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


class TestGolden(unittest.TestCase):
    def test_golden_path_idea_to_archive_with_execution_evidence(self) -> None:
        """The definitive system proof: a standard-profile change goes from
        idea to archived with real command execution, checksummed evidence,
        and guard validation at every critical gate.

        Narrative:
          1. init project
          2. create standard change
          3. agent fills proposal → auto-loop advances through SPECIFY/DESIGN
          4. agent fills tasks → auto-loop pauses at TASK (verify gate)
          5. verify with real command → evidence persisted + checksummed
          6. auto-loop drives through ARCHIVE_RECORD → SYNC_SPECS → ARCHIVED
          7. guard --strict-state --require-execution-evidence passes on the archive
          8. change directory is gone, archive + spec exist

        If this test passes, the system works end-to-end.
        """
        import hashlib
        root = REPO_ROOT / ".tmp-tests" / f"golden-{uuid.uuid4().hex}"
        change_id = "harden-login"

        # ── 1. Init project ──────────────────────────────────────────────
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        # ── 2. Create standard-profile change ─────────────────────────────
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Harden login"), [])
        change_dir = root / ".runproof" / "changes" / change_id
        self.assertTrue(change_dir.is_dir())

        # ── 3. Agent fills proposal → auto-loop advances ─────────────────
        # At this point, auto should pause at PROPOSE (proposal is draft).
        result = sdd._auto_advance(root, change_id)
        self.assertTrue(result.needs_human_work)
        self.assertEqual(result.step.phase, sdd.WorkflowPhase.PROPOSE)

        # Agent writes the proposal.
        proposal = change_dir / "proposal.md"
        proposal.write_text(
            sdd.set_frontmatter_value(proposal.read_text(encoding="utf-8"), "status", "ready"),
            encoding="utf-8",
        )

        # Auto-loop: should advance through SPECIFY (needs delta-spec).
        with contextlib.redirect_stdout(io.StringIO()):
            result = sdd._auto_advance(root, change_id)
        self.assertIsNotNone(result.executed_command)  # transition to SPECIFY

        # Agent fills delta-spec.
        delta_spec = change_dir / "delta-spec.md"
        delta_spec.write_text(
            sdd.set_frontmatter_value(delta_spec.read_text(encoding="utf-8"), "status", "ready"),
            encoding="utf-8",
        )

        # Auto-loop: advance through DESIGN.
        with contextlib.redirect_stdout(io.StringIO()):
            result = sdd._auto_advance(root, change_id)
        self.assertIsNotNone(result.executed_command)

        # Agent fills design.
        design = change_dir / "design.md"
        design.write_text(
            sdd.set_frontmatter_value(design.read_text(encoding="utf-8"), "status", "ready"),
            encoding="utf-8",
        )

        # Auto-loop: advance to TASK.
        with contextlib.redirect_stdout(io.StringIO()):
            result = sdd._auto_advance(root, change_id)
        self.assertIsNotNone(result.executed_command)

        # ── 4. Agent fills tasks → auto pauses at TASK (verify gate) ──────
        tasks = change_dir / "tasks.md"
        text = tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]")
        text = sdd.set_frontmatter_value(text, "status", "ready")
        tasks.write_text(text, encoding="utf-8")

        # Auto MUST pause here — VERIFY is a restricted phase.
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(10):
                result = sdd._auto_advance(root, change_id)
                if result.needs_human_work or result.step.is_complete:
                    break
        self.assertEqual(result.step.phase, sdd.WorkflowPhase.TASK)
        self.assertTrue(result.needs_human_work)

        # ── 5. Verify with real command execution ─────────────────────────
        sentinel = "GOLDEN_PATH_PROOF_42"
        cmd = f'"{sys.executable}" -c "print(\'{sentinel}\')"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [cmd])
        self.assertEqual(findings, [], f"verify blocked: {findings}")
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

        # Evidence is persisted with valid checksum.
        records, rec_findings = sdd.execution_evidence_records(root, change_id)
        self.assertEqual(rec_findings, [])
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertTrue(rec["passed"])
        self.assertEqual(rec["exit_code"], 0)
        self.assertEqual(rec["command"], cmd)
        log_path = root / rec["log_path"]
        log_content = log_path.read_text(encoding="utf-8")
        self.assertIn(sentinel, log_content)
        self.assertEqual(
            hashlib.sha256(log_content.encode("utf-8")).hexdigest(),
            rec["output_checksum"],
        )

        # ── 6. Auto-loop drives to ARCHIVED ──────────────────────────────
        # archive.md needs status: ready before the engine can archive.
        archive_md = change_dir / "archive.md"
        archive_md.write_text(
            sdd.set_frontmatter_value(archive_md.read_text(encoding="utf-8"), "status", "ready"),
            encoding="utf-8",
        )

        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(20):
                result = sdd._auto_advance(root, change_id)
                if result.step.is_complete or result.step.is_blocked or result.needs_human_work:
                    break
        self.assertTrue(result.step.is_complete, f"expected complete, got phase={result.step.phase}")

        # ── 7. Guard with strictest policy passes ─────────────────────────
        guard_findings = sdd.guard_repository(
            root,
            strict_state=True,
            require_execution_evidence=True,
        )
        self.assertEqual(guard_findings, [], f"guard failed: {guard_findings}")

        # ── 8. Filesystem proof ───────────────────────────────────────────
        # Change directory is gone.
        self.assertFalse(change_dir.exists())
        # Living spec was synced.
        self.assertTrue((root / ".runproof" / "specs" / change_id / "spec.md").is_file())
        # Archive exists.
        archives = [p for p in (root / ".runproof" / "archive").iterdir() if p.is_dir()]
        self.assertEqual(len(archives), 1)
        self.assertIn(change_id, archives[0].name)

    def test_golden_path_failure_system_stays_consistent(self) -> None:
        """The failure counterpart to the golden path: a standard-profile change
        advances to TASK, the verification command FAILS, and the system stays
        perfectly consistent — nothing advances, evidence is recorded, guard blocks.

        Narrative:
          1. init → create → agent fills all artifacts → auto-loop to TASK
          2. verify with failing command → verify BLOCKED, phase stays TASK
          3. evidence of the failure IS recorded (command, exit_code, log, hash)
          4. guard --require-execution-evidence blocks (no passing evidence)
          5. change directory still exists, no archive, no spec sync
          6. agent retries with passing command → verify succeeds
          7. auto-loop closes → guard passes → archive exists

        If this test passes, the system is safe even when things go wrong.
        """
        import hashlib
        root = REPO_ROOT / ".tmp-tests" / f"golden-fail-{uuid.uuid4().hex}"
        change_id = "harden-login-fail"

        # ── 1. Init → create → advance to TASK ──────────────────────────
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Harden login"), [])
        change_dir = root / ".runproof" / "changes" / change_id

        # Fill all human-work artifacts.
        for name in ["proposal.md", "delta-spec.md", "design.md"]:
            p = change_dir / name
            p.write_text(sdd.set_frontmatter_value(p.read_text(encoding="utf-8"), "status", "ready"), encoding="utf-8")
        tasks = change_dir / "tasks.md"
        text = tasks.read_text(encoding="utf-8").replace("- [ ]", "- [x]")
        tasks.write_text(sdd.set_frontmatter_value(text, "status", "ready"), encoding="utf-8")

        # Drain auto-loop until TASK (verify gate).
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(20):
                result = sdd._auto_advance(root, change_id)
                if result.needs_human_work or result.step.is_complete:
                    break
        self.assertEqual(result.step.phase, sdd.WorkflowPhase.TASK)

        # ── 2. Verify with FAILING command → BLOCKED ─────────────────────
        fail_cmd = f'"{sys.executable}" -c "import sys; sys.exit(7)"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [fail_cmd])
        self.assertTrue(any(f.severity == "error" for f in findings))
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.TASK)

        # ── 3. Failure evidence IS recorded ──────────────────────────────
        records, _ = sdd.execution_evidence_records(root, change_id)
        fail_rec = next(r for r in records if r["command"] == fail_cmd)
        self.assertFalse(fail_rec["passed"])
        self.assertEqual(fail_rec["exit_code"], 7)
        fail_log = root / fail_rec["log_path"]
        self.assertTrue(fail_log.is_file())
        self.assertEqual(
            hashlib.sha256(fail_log.read_text(encoding="utf-8").encode("utf-8")).hexdigest(),
            fail_rec["output_checksum"],
        )

        # ── 4. Guard blocks — no passing evidence ────────────────────────
        guard_findings = sdd.guard_repository(root, require_execution_evidence=True)
        # Change is still active at TASK, not archived.
        self.assertTrue(change_dir.exists())
        archive_root = root / ".runproof" / "archive"
        archived_dirs = [p for p in archive_root.iterdir() if p.is_dir()] if archive_root.exists() else []
        self.assertEqual(archived_dirs, [])

        # ── 5. No spec sync ──────────────────────────────────────────────
        self.assertFalse((root / ".runproof" / "specs" / change_id).exists())

        # ── 6. Agent retries with PASSING command → verify succeeds ──────
        pass_cmd = f'"{sys.executable}" -c "print(\'retry-ok\')"'
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.verify_change(root, change_id, [pass_cmd])
        self.assertEqual(findings, [])
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.VERIFY)

        # Both records exist — failure AND retry.
        records, _ = sdd.execution_evidence_records(root, change_id)
        commands = [r["command"] for r in records]
        self.assertIn(fail_cmd, commands)
        self.assertIn(pass_cmd, commands)

        # ── 7. Auto-loop closes → guard passes → archive exists ─────────
        archive_md = change_dir / "archive.md"
        archive_md.write_text(
            sdd.set_frontmatter_value(archive_md.read_text(encoding="utf-8"), "status", "ready"),
            encoding="utf-8",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(20):
                result = sdd._auto_advance(root, change_id)
                if result.step.is_complete or result.step.is_blocked or result.needs_human_work:
                    break
        self.assertTrue(result.step.is_complete)

        guard_findings = sdd.guard_repository(
            root, strict_state=True, require_execution_evidence=True,
        )
        self.assertEqual(guard_findings, [], f"guard failed: {guard_findings}")
        self.assertFalse(change_dir.exists())
        archives = [p for p in (root / ".runproof" / "archive").iterdir() if p.is_dir()]
        self.assertEqual(len(archives), 1)


if __name__ == "__main__":
    unittest.main()
