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

import ssd_core
from ssd_core import cli as sdd

REPO_ROOT = Path(__file__).resolve().parents[1]


class SddToolingTests(unittest.TestCase):
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

    def test_version_is_defined(self) -> None:
        self.assertEqual(sdd.VERSION, "0.5.0")

    def test_distribution_versions_match(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["version"], sdd.VERSION)
        self.assertEqual(package["version"], sdd.VERSION)

    def test_packaged_templates_are_present(self) -> None:
        template_root = files("ssd_core").joinpath("templates")

        self.assertTrue(template_root.joinpath("sdd", "constitution.md").is_file())
        self.assertTrue(template_root.joinpath("sdd", "state.json").is_file())
        self.assertTrue(template_root.joinpath("sdd", "evidence", ".gitkeep").is_file())
        self.assertTrue(template_root.joinpath("sdd", "adapters", "generic-markdown.json").is_file())
        self.assertTrue(template_root.joinpath("sdd", "adapters", "codex.json").is_file())
        self.assertTrue(template_root.joinpath("sdd", "adapters", "claude-code.json").is_file())
        self.assertTrue(template_root.joinpath("sdd", "adapters", "gemini-cli.json").is_file())
        self.assertTrue(template_root.joinpath("sdd", "adapters", "opencode.json").is_file())
        self.assertTrue(template_root.joinpath("sdd", "adapters", "qwen-code.json").is_file())
        self.assertTrue(template_root.joinpath("docs", "adapters-v0.1.md").is_file())
        self.assertTrue(template_root.joinpath("docs", "sdd-core-protocol-v0.1.md").is_file())

    def test_standard_profile_artifacts_are_defined(self) -> None:
        self.assertEqual(
            sdd.PROFILE_ARTIFACTS["standard"],
            ["proposal.md", "delta-spec.md", "design.md", "tasks.md", "verification.md", "archive.md"],
        )

    def test_agent_and_skill_catalogs_are_defined(self) -> None:
        self.assertIn("orchestrator", sdd.REQUIRED_AGENTS)
        self.assertIn("verifier", sdd.REQUIRED_AGENTS)
        self.assertIn("propose", sdd.REQUIRED_SKILLS)
        self.assertIn("archive", sdd.REQUIRED_SKILLS)

    def test_adapter_manifest_is_required(self) -> None:
        self.assertIn("generic-markdown.json", sdd.REQUIRED_ADAPTERS)
        self.assertIn("codex.json", sdd.REQUIRED_ADAPTERS)
        self.assertIn("claude-code.json", sdd.REQUIRED_ADAPTERS)
        self.assertIn("gemini-cli.json", sdd.REQUIRED_ADAPTERS)
        self.assertIn("opencode.json", sdd.REQUIRED_ADAPTERS)
        self.assertIn("qwen-code.json", sdd.REQUIRED_ADAPTERS)
        self.assertIn("adapter-capabilities.schema.json", sdd.REQUIRED_SCHEMAS)

    def test_artifact_body_includes_change_metadata(self) -> None:
        body = sdd.artifact_body(
            "proposal.md",
            change_id="add-search",
            title="Add search",
            profile="standard",
            today="2026-05-03",
        )

        self.assertIn("schema: sdd.artifact.v1", body)
        self.assertIn("artifact: proposal", body)
        self.assertIn("change_id: add-search", body)
        self.assertIn("profile: standard", body)
        self.assertIn("Add search", body)

    def test_create_change_rejects_invalid_change_id_before_filesystem_access(self) -> None:
        findings = sdd.create_change(
            root=REPO_ROOT,
            change_id="Add Search",
            profile="standard",
            title="Add search",
        )

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")
        self.assertIn("change-id is not valid", findings[0].message)

    def test_current_repository_validates(self) -> None:
        findings = sdd.validate(REPO_ROOT)

        self.assertEqual(findings, [])

    def test_current_repository_status_has_no_active_changes(self) -> None:
        findings, changes = sdd.status(REPO_ROOT)

        self.assertEqual(findings, [])
        self.assertEqual(changes, [])

    def test_init_project_creates_valid_foundation_in_new_root(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / "init-fixture"

        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.init_project(root)

        self.assertEqual(findings, [])
        self.assertTrue((root / ".sdd" / "constitution.md").is_file())
        self.assertTrue((root / ".sdd" / "state.json").is_file())
        self.assertTrue((root / ".sdd" / "evidence").is_dir())
        self.assertTrue((root / ".sdd" / "adapters" / "generic-markdown.json").is_file())
        self.assertEqual(sdd.validate(root), [])

    def test_validate_requires_change_id_to_match_change_directory(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"change-id-mismatch-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, "demo-change", "standard", "Demo"), [])

        proposal_path = root / ".sdd" / "changes" / "demo-change" / "proposal.md"
        proposal_text = proposal_path.read_text(encoding="utf-8")
        proposal_path.write_text(proposal_text.replace("change_id: demo-change", "change_id: wrong-id"), encoding="utf-8")

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertTrue(any("change_id does not match directory name" in message for message in messages))

    def test_validate_requires_profile_in_change_artifacts(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"missing-profile-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, "demo-change", "standard", "Demo"), [])

        proposal_path = root / ".sdd" / "changes" / "demo-change" / "proposal.md"
        proposal_text = proposal_path.read_text(encoding="utf-8")
        proposal_path.write_text(proposal_text.replace("profile: standard\n", ""), encoding="utf-8")

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertIn("frontmatter missing required key: profile", messages)

    def test_validate_rejects_artifact_name_mismatch(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"artifact-mismatch-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, "demo-change", "standard", "Demo"), [])

        proposal_path = root / ".sdd" / "changes" / "demo-change" / "proposal.md"
        proposal_text = proposal_path.read_text(encoding="utf-8")
        proposal_path.write_text(proposal_text.replace("artifact: proposal", "artifact: design"), encoding="utf-8")

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertTrue(any("artifact value must match filename stem" in message for message in messages))

    def test_validate_rejects_invalid_created_date(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"invalid-date-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        constitution_path = root / ".sdd" / "constitution.md"
        constitution_text = constitution_path.read_text(encoding="utf-8")
        constitution_path.write_text(constitution_text.replace("created: 2026-05-03", "created: 2026-13-40"), encoding="utf-8")

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertIn("created is not a valid calendar date", messages)

    def test_validate_requires_living_spec_change_id_match(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"spec-change-id-mismatch-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        spec_dir = root / ".sdd" / "specs" / "demo-change"
        spec_dir.mkdir(parents=True)
        spec_path = spec_dir / "spec.md"
        spec_path.write_text(
            "\n".join(
                [
                    "---",
                    "schema: sdd.living-spec.v1",
                    "artifact: spec",
                    "change_id: wrong-id",
                    "status: active",
                    "created: 2026-05-03",
                    "updated: 2026-05-03",
                    "---",
                    "",
                    "# Demo Spec",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertTrue(any("change_id does not match directory name" in message for message in messages))

    def test_check_change_rejects_missing_change(self) -> None:
        findings = sdd.check_change(REPO_ROOT, "missing-change")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")
        self.assertIn("change does not exist", findings[0].message)

    def test_archive_rejects_invalid_change_id_before_filesystem_access(self) -> None:
        findings = sdd.archive_change(REPO_ROOT, "Invalid Change")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")
        self.assertIn("change-id is not valid", findings[0].message)

    def test_sync_specs_rejects_missing_change(self) -> None:
        findings = sdd.sync_specs(REPO_ROOT, "missing-change")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")
        self.assertIn("workflow phase must be recorded", findings[0].message)

    def test_strip_frontmatter_text_removes_frontmatter(self) -> None:
        text = "---\nschema: sdd.artifact.v1\n---\n\n# Body\n"

        self.assertEqual(sdd.strip_frontmatter_text(text), "# Body\n")

    def test_end_to_end_standard_change_syncs_and_archives(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"e2e-{uuid.uuid4().hex}"
        change_id = "document-example"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Document example"), [])

        change_dir = root / ".sdd" / "changes" / change_id
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
        self.assertTrue((root / ".sdd" / "specs" / change_id / "spec.md").is_file())
        archives = list((root / ".sdd" / "archive").glob(f"*-{change_id}"))
        self.assertEqual(len(archives), 1)

    def test_archive_rejects_verified_change_before_spec_sync(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"archive-before-sync-{uuid.uuid4().hex}"
        change_id = "document-example"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Document example"), [])

        change_dir = root / ".sdd" / "changes" / change_id
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
        self.assertTrue((root / ".sdd" / "changes" / "guard-login" / "proposal.md").is_file())
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

        proposal_path = root / ".sdd" / "changes" / change_id / "proposal.md"
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

        proposal_path = root / ".sdd" / "changes" / change_id / "proposal.md"
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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
        self.assertFalse((root / ".sdd" / "changes" / "guard-login").exists())

    def test_public_workflow_orchestrator_is_exported(self) -> None:
        self.assertIs(ssd_core.SDDWorkflow, sdd.SDDWorkflow)
        self.assertIs(ssd_core.WorkflowPhase, sdd.WorkflowPhase)
        self.assertIs(ssd_core.WorkflowFailureKind, sdd.WorkflowFailureKind)
        self.assertIs(ssd_core.guard_repository, sdd.guard_repository)
        self.assertIs(ssd_core.install_hooks, sdd.install_hooks)
        self.assertIs(ssd_core.transition_workflow, sdd.transition_workflow)
        self.assertIs(ssd_core.declared_workflow_phase, sdd.declared_workflow_phase)

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
        self.assertTrue(any("ssd-core verify" in f.message for f in blocked.findings))
        # The dedicated verify command must also be unavailable before TASK is recorded
        findings = sdd.verify_change(root, change_id)
        self.assertEqual(len(findings), 1)
        self.assertIn("workflow phase must be task", findings[0].message)

    def test_transition_blocks_archived_phase(self) -> None:
        blocked = sdd.transition_workflow(REPO_ROOT, "any-change", sdd.WorkflowPhase.ARCHIVED)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("ssd-core archive" in f.message for f in blocked.findings))

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
        self.assertIn("SDD log", output)
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        archive_dir = root / ".sdd" / "archive" / f"2026-05-05-{change_id}"
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
        self.assertIn("ssd-core guard", commit_text)
        self.assertIn("--require-active-change", commit_text)
        self.assertIn("--strict-state", commit_text)

        pre_push = root / ".git" / "hooks" / "pre-push"
        self.assertTrue(pre_push.is_file())
        push_text = pre_push.read_text(encoding="utf-8")
        self.assertIn("ssd-core guard", push_text)
        self.assertIn("--strict-state", push_text)
        self.assertNotIn("--require-active-change", push_text)

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
        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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
        evidence_path = root / ".sdd" / "evidence" / change_id / "verification.jsonl"
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        verification_path = root / ".sdd" / "changes" / change_id / "verification.md"
        # Default template still has the placeholder Commands line
        findings = sdd.validate_verification_evidence(verification_path)
        messages = self.finding_messages(findings)
        self.assertTrue(any("placeholder" in m for m in messages))

    def test_public_verify_change_is_exported(self) -> None:
        self.assertIs(ssd_core.verify_change, sdd.verify_change)
        self.assertIs(ssd_core.validate_verification_evidence, sdd.validate_verification_evidence)
        self.assertIs(ssd_core.validate_execution_evidence, sdd.validate_execution_evidence)

    def test_gate_command_is_exported(self) -> None:
        self.assertIs(ssd_core.gate_command, sdd.gate_command)

    def test_archive_blocks_when_artifact_edited_after_archive_phase_recorded(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"gate-stale-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".sdd" / "changes" / change_id
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
        self.assertIn("ssd-core transition", findings[0].message)

    def test_verify_does_not_block_when_verification_md_edited_after_task(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-expects-edit-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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

        change_dir = root / ".sdd" / "changes" / change_id
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
        self.assertIs(ssd_core.WorkflowEngine, sdd.WorkflowEngine)
        self.assertIs(ssd_core.COMMAND_GATES, sdd.COMMAND_GATES)

    # --- validate_verification_matrix ---

    def test_validate_verification_matrix_blocks_when_no_passing_row(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"matrix-no-pass-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        verification_path = root / ".sdd" / "changes" / change_id / "verification.md"
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

        verification_path = root / ".sdd" / "changes" / change_id / "verification.md"
        text = verification_path.read_text(encoding="utf-8")
        text = text.replace("pending verification evidence", "unit test evidence")
        text = text.replace("not-run", "pass")
        text = text.replace("Record host-project verification actions.", "pytest -q")
        verification_path.write_text(text, encoding="utf-8")

        findings = sdd.validate_verification_matrix(verification_path)
        self.assertEqual(findings, [])

    def test_validate_verification_matrix_is_exported(self) -> None:
        self.assertIs(ssd_core.validate_verification_matrix, sdd.validate_verification_matrix)

    def test_check_change_blocks_when_matrix_has_no_passing_row(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"check-matrix-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".sdd" / "changes" / change_id
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
        change_dir = root / ".sdd" / "changes" / change_id
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
        change_dir = root / ".sdd" / "changes" / change_id
        proposal_path = change_dir / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        # state.json says PROPOSE; artifact inference says SPECIFY (proposal ready)
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.PROPOSE)
        self.assertEqual(sdd.infer_phase_from_artifacts(root, change_id), sdd.WorkflowPhase.SPECIFY)
        # workflow_state() returns PROPOSE (declared), not SPECIFY
        self.assertEqual(sdd.workflow_state(root, change_id).phase, sdd.WorkflowPhase.PROPOSE)

    def test_infer_phase_from_artifacts_is_exported(self) -> None:
        self.assertIs(ssd_core.infer_phase_from_artifacts, sdd.infer_phase_from_artifacts)

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
        proposal_path = root / ".sdd" / "changes" / change_id / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")
        self.record_transition(root, change_id, sdd.WorkflowPhase.SPECIFY)

        # state.json now says SPECIFY; delta-spec.md is still draft
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.SPECIFY)
        # SPECIFY allows DESIGN — but artifact phase is still SPECIFY (delta-spec.md is draft)
        # phase_is_supported(DESIGN, SPECIFY) → 30 <= 20 → False → blocked
        blocked = sdd.transition_workflow(root, change_id, sdd.WorkflowPhase.DESIGN)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("artifact phase" in finding.message for finding in blocked.findings))


if __name__ == "__main__":
    unittest.main()
