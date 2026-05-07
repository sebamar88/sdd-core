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

import proofkit
from proofkit import cli as sdd

REPO_ROOT = Path(__file__).resolve().parents[1]

_COMMAND_FILE_NAMES = [
    "sdd-propose.md",
    "sdd-specify.md",
    "sdd-design.md",
    "sdd-tasks.md",
    "sdd-verify.md",
    "sdd-status.md",
]


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
        self.assertEqual(sdd.VERSION, "0.25.0")

    def test_distribution_versions_match(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["version"], sdd.VERSION)
        self.assertEqual(package["version"], sdd.VERSION)

    def test_packaged_templates_are_present(self) -> None:
        template_root = files("proofkit").joinpath("templates")

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
        self.assertTrue(template_root.joinpath("docs", "proofkit-protocol-v0.1.md").is_file())

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
        root = REPO_ROOT / ".tmp-tests" / f"init-fixture-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.init_project(root)

        self.assertEqual(findings, [])
        self.assertTrue((root / ".proofkit" / "constitution.md").is_file())
        self.assertTrue((root / ".proofkit" / "state.json").is_file())
        self.assertTrue((root / ".proofkit" / "evidence").is_dir())
        self.assertTrue((root / ".proofkit" / "adapters" / "generic-markdown.json").is_file())
        self.assertEqual(sdd.validate(root), [])

    def test_validate_requires_change_id_to_match_change_directory(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"change-id-mismatch-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, "demo-change", "standard", "Demo"), [])

        proposal_path = root / ".proofkit" / "changes" / "demo-change" / "proposal.md"
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

        proposal_path = root / ".proofkit" / "changes" / "demo-change" / "proposal.md"
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

        proposal_path = root / ".proofkit" / "changes" / "demo-change" / "proposal.md"
        proposal_text = proposal_path.read_text(encoding="utf-8")
        proposal_path.write_text(proposal_text.replace("artifact: proposal", "artifact: design"), encoding="utf-8")

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertTrue(any("artifact value must match filename stem" in message for message in messages))

    def test_validate_rejects_invalid_created_date(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"invalid-date-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        constitution_path = root / ".proofkit" / "constitution.md"
        constitution_text = constitution_path.read_text(encoding="utf-8")
        constitution_path.write_text(constitution_text.replace("created: 2026-05-03", "created: 2026-13-40"), encoding="utf-8")

        findings = sdd.validate(root)
        messages = self.finding_messages(findings)
        self.assertIn("created is not a valid calendar date", messages)

    def test_validate_requires_living_spec_change_id_match(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"spec-change-id-mismatch-{uuid.uuid4().hex}"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])

        spec_dir = root / ".proofkit" / "specs" / "demo-change"
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

        change_dir = root / ".proofkit" / "changes" / change_id
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
        self.assertTrue((root / ".proofkit" / "specs" / change_id / "spec.md").is_file())
        archives = list((root / ".proofkit" / "archive").glob(f"*-{change_id}"))
        self.assertEqual(len(archives), 1)

    def test_archive_rejects_verified_change_before_spec_sync(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"archive-before-sync-{uuid.uuid4().hex}"
        change_id = "document-example"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Document example"), [])

        change_dir = root / ".proofkit" / "changes" / change_id
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
        self.assertTrue((root / ".proofkit" / "changes" / "guard-login" / "proposal.md").is_file())
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

        proposal_path = root / ".proofkit" / "changes" / change_id / "proposal.md"
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

        proposal_path = root / ".proofkit" / "changes" / change_id / "proposal.md"
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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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
        self.assertFalse((root / ".proofkit" / "changes" / "guard-login").exists())

    def test_public_workflow_orchestrator_is_exported(self) -> None:
        self.assertIs(proofkit.SDDWorkflow, sdd.SDDWorkflow)
        self.assertIs(proofkit.WorkflowPhase, sdd.WorkflowPhase)
        self.assertIs(proofkit.WorkflowFailureKind, sdd.WorkflowFailureKind)
        self.assertIs(proofkit.guard_repository, sdd.guard_repository)
        self.assertIs(proofkit.install_hooks, sdd.install_hooks)
        self.assertIs(proofkit.transition_workflow, sdd.transition_workflow)
        self.assertIs(proofkit.declared_workflow_phase, sdd.declared_workflow_phase)

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
        self.assertTrue(any("proofkit verify" in f.message for f in blocked.findings))
        # The dedicated verify command must also be unavailable before TASK is recorded
        findings = sdd.verify_change(root, change_id)
        self.assertEqual(len(findings), 1)
        self.assertIn("workflow phase must be task", findings[0].message)

    def test_transition_blocks_archived_phase(self) -> None:
        blocked = sdd.transition_workflow(REPO_ROOT, "any-change", sdd.WorkflowPhase.ARCHIVED)
        self.assertTrue(blocked.is_blocked)
        self.assertTrue(any("proofkit archive" in f.message for f in blocked.findings))

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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        archive_dir = root / ".proofkit" / "archive" / f"2026-05-05-{change_id}"
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
        self.assertIn("proofkit guard", commit_text)
        self.assertIn("--require-active-change", commit_text)
        self.assertIn("--strict-state", commit_text)

        pre_push = root / ".git" / "hooks" / "pre-push"
        self.assertTrue(pre_push.is_file())
        push_text = pre_push.read_text(encoding="utf-8")
        self.assertIn("proofkit guard", push_text)
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
        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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
        evidence_path = root / ".proofkit" / "evidence" / change_id / "verification.jsonl"
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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        verification_path = root / ".proofkit" / "changes" / change_id / "verification.md"
        # Default template still has the placeholder Commands line
        findings = sdd.validate_verification_evidence(verification_path)
        messages = self.finding_messages(findings)
        self.assertTrue(any("placeholder" in m for m in messages))

    def test_public_verify_change_is_exported(self) -> None:
        self.assertIs(proofkit.verify_change, sdd.verify_change)
        self.assertIs(proofkit.validate_verification_evidence, sdd.validate_verification_evidence)
        self.assertIs(proofkit.validate_execution_evidence, sdd.validate_execution_evidence)

    def test_gate_command_is_exported(self) -> None:
        self.assertIs(proofkit.gate_command, sdd.gate_command)

    def test_archive_blocks_when_artifact_edited_after_archive_phase_recorded(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"gate-stale-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".proofkit" / "changes" / change_id
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
        self.assertIn("proofkit transition", findings[0].message)

    def test_verify_does_not_block_when_verification_md_edited_after_task(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"verify-expects-edit-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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

        change_dir = root / ".proofkit" / "changes" / change_id
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
        self.assertIs(proofkit.WorkflowEngine, sdd.WorkflowEngine)
        self.assertIs(proofkit.COMMAND_GATES, sdd.COMMAND_GATES)

    # --- validate_verification_matrix ---

    def test_validate_verification_matrix_blocks_when_no_passing_row(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"matrix-no-pass-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        verification_path = root / ".proofkit" / "changes" / change_id / "verification.md"
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

        verification_path = root / ".proofkit" / "changes" / change_id / "verification.md"
        text = verification_path.read_text(encoding="utf-8")
        text = text.replace("pending verification evidence", "unit test evidence")
        text = text.replace("not-run", "pass")
        text = text.replace("Record host-project verification actions.", "pytest -q")
        verification_path.write_text(text, encoding="utf-8")

        findings = sdd.validate_verification_matrix(verification_path)
        self.assertEqual(findings, [])

    def test_validate_verification_matrix_is_exported(self) -> None:
        self.assertIs(proofkit.validate_verification_matrix, sdd.validate_verification_matrix)

    def test_check_change_blocks_when_matrix_has_no_passing_row(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"check-matrix-{uuid.uuid4().hex}"
        change_id = "guard-login"

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.init_project(root), [])
            self.assertEqual(sdd.create_change(root, change_id, "standard", "Guard login"), [])

        change_dir = root / ".proofkit" / "changes" / change_id
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
        change_dir = root / ".proofkit" / "changes" / change_id
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
        change_dir = root / ".proofkit" / "changes" / change_id
        proposal_path = change_dir / "proposal.md"
        proposal_path.write_text(proposal_path.read_text(encoding="utf-8").replace("status: draft", "status: ready"), encoding="utf-8")

        # state.json says PROPOSE; artifact inference says SPECIFY (proposal ready)
        self.assertEqual(sdd.declared_workflow_phase(root, change_id), sdd.WorkflowPhase.PROPOSE)
        self.assertEqual(sdd.infer_phase_from_artifacts(root, change_id), sdd.WorkflowPhase.SPECIFY)
        # workflow_state() returns PROPOSE (declared), not SPECIFY
        self.assertEqual(sdd.workflow_state(root, change_id).phase, sdd.WorkflowPhase.PROPOSE)

    def test_infer_phase_from_artifacts_is_exported(self) -> None:
        self.assertIs(proofkit.infer_phase_from_artifacts, sdd.infer_phase_from_artifacts)

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
        proposal_path = root / ".proofkit" / "changes" / change_id / "proposal.md"
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
        return root / ".proofkit" / "changes" / change_id

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
        archive_root = root / ".proofkit" / "archive"
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

        This is the enforcement path of `proofkit verify --require-command`:
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

    # ── Golden narrative: full lifecycle with execution evidence ───────────

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
        change_dir = root / ".proofkit" / "changes" / change_id
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
        self.assertTrue((root / ".proofkit" / "specs" / change_id / "spec.md").is_file())
        # Archive exists.
        archives = [p for p in (root / ".proofkit" / "archive").iterdir() if p.is_dir()]
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
        change_dir = root / ".proofkit" / "changes" / change_id

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
        archive_root = root / ".proofkit" / "archive"
        archived_dirs = [p for p in archive_root.iterdir() if p.is_dir()] if archive_root.exists() else []
        self.assertEqual(archived_dirs, [])

        # ── 5. No spec sync ──────────────────────────────────────────────
        self.assertFalse((root / ".proofkit" / "specs" / change_id).exists())

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
        archives = [p for p in (root / ".proofkit" / "archive").iterdir() if p.is_dir()]
        self.assertEqual(len(archives), 1)


    # ── install-commands ─────────────────────────────────────────────────────

    def test_install_commands_repo_scope_creates_files_in_integration_dir(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"cmd-repo-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            findings = sdd.install_commands(root, "claude-code", "repo")
        self.assertEqual(findings, [])
        commands_dir = root / ".claude" / "commands"
        for name in _COMMAND_FILE_NAMES:
            self.assertTrue((commands_dir / name).is_file(), f"missing {name}")

    def test_install_commands_user_scope_creates_files_in_home_subdir(self) -> None:
        tmp_home = REPO_ROOT / ".tmp-tests" / f"cmd-home-{uuid.uuid4().hex}"
        root = REPO_ROOT / ".tmp-tests" / f"cmd-user-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            findings = sdd.install_commands(root, "generic", "user", _home=tmp_home)
        self.assertEqual(findings, [])
        commands_dir = tmp_home / ".proofkit" / "commands"
        for name in _COMMAND_FILE_NAMES:
            self.assertTrue((commands_dir / name).is_file(), f"missing {name}")

    def test_install_commands_local_scope_writes_files_and_adds_gitignore(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"cmd-local-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            findings = sdd.install_commands(root, "claude-code", "local")
        self.assertEqual(findings, [])
        commands_dir = root / ".claude" / "commands"
        for name in _COMMAND_FILE_NAMES:
            self.assertTrue((commands_dir / name).is_file(), f"missing {name}")
        gitignore = root / ".gitignore"
        self.assertTrue(gitignore.is_file())
        self.assertIn(".claude/commands", gitignore.read_text(encoding="utf-8"))

    def test_install_commands_local_scope_is_idempotent_on_gitignore(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"cmd-local-idem-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            sdd.install_commands(root, "claude-code", "local")
            # Second call: should not duplicate the gitignore entry.
            sdd.install_commands(root, "claude-code", "local")
        gitignore = root / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        self.assertEqual(content.count(".claude/commands"), 1)

    def test_install_commands_unknown_integration_returns_error(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"cmd-bad-int-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            findings = sdd.install_commands(root, "not-a-real-tool", "repo")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_install_commands_unknown_scope_returns_error(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"cmd-bad-scope-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            findings = sdd.install_commands(root, "claude-code", "workspace")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_install_commands_is_idempotent_skips_existing_files(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"cmd-idem-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
            sdd.install_commands(root, "generic", "repo")
        # Overwrite one file with a custom local scaffold.
        custom_file = root / ".proofkit" / "commands" / "sdd-propose.md"
        custom_file.write_text("# my custom scaffold", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.install_commands(root, "generic", "repo")
        self.assertEqual(findings, [])
        # Custom content must be preserved — not overwritten on second install.
        self.assertEqual(custom_file.read_text(encoding="utf-8"), "# my custom scaffold")

    def test_list_available_integrations_returns_all_known(self) -> None:
        integrations = sdd.list_available_integrations()
        self.assertIsInstance(integrations, list)
        expected = {"claude-code", "copilot", "opencode", "codex", "gemini-cli", "generic"}
        self.assertEqual(set(integrations), expected)
        self.assertEqual(integrations, sorted(integrations))

    def test_packaged_commands_templates_are_present(self) -> None:
        for name in _COMMAND_FILE_NAMES:
            tmpl = sdd.template_commands_root() / name
            self.assertTrue(tmpl.is_file(), f"command template missing: {name}")

    # ── extension system ────────────────────────────────────────────────────────

    def _make_extension_source(self, tmp: Path, name: str = "my-ext") -> Path:
        """Create a minimal valid extension source directory."""
        src = tmp / "ext-src" / name
        src.mkdir(parents=True)
        manifest = {
            "schema": "sdd.extension.v1",
            "name": name,
            "version": "1.0.0",
            "description": "Test extension",
            "author": "tester",
            "templates": False,
            "hooks": False,
        }
        (src / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return src

    def test_load_extensions_returns_empty_when_no_extensions_installed(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-empty-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        exts = sdd.load_extensions(root)
        self.assertEqual(exts, [])

    def test_install_extension_copies_manifest_and_creates_extension_dir(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-install-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        src = self._make_extension_source(root, "my-ext")
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.install_extension(root, src)
        self.assertEqual(findings, [])
        ext_dir = root / ".proofkit" / "extensions" / "my-ext"
        self.assertTrue(ext_dir.is_dir())
        self.assertTrue((ext_dir / "manifest.json").is_file())

    def test_list_extensions_shows_installed_name_and_version(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-list-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        src = self._make_extension_source(root, "my-ext")
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.install_extension(root, src)
        exts = sdd.load_extensions(root)
        self.assertEqual(len(exts), 1)
        self.assertEqual(exts[0].name, "my-ext")
        self.assertEqual(exts[0].version, "1.0.0")
        self.assertEqual(exts[0].description, "Test extension")

    def test_remove_extension_deletes_extension_directory(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-remove-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        src = self._make_extension_source(root, "my-ext")
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.install_extension(root, src)
        ext_dir = root / ".proofkit" / "extensions" / "my-ext"
        self.assertTrue(ext_dir.is_dir())
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.remove_extension(root, "my-ext")
        self.assertEqual(findings, [])
        self.assertFalse(ext_dir.exists())

    def test_extension_hook_on_verify_appends_findings_when_trusted(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-hook-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        # Build extension with a hooks.py that adds one error finding.
        src = self._make_extension_source(root, "hook-ext")
        manifst = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
        manifst["hooks"] = True
        (src / "manifest.json").write_text(json.dumps(manifst), encoding="utf-8")
        (src / "hooks.py").write_text(
            "def on_verify(root, change_id, findings):\n"
            "    from proofkit._types import Finding\n"
            "    return findings + [Finding('error', None, 'hook-injected-error')]\n",
            encoding="utf-8",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.install_extension(root, src)
        # Mark TRUSTED.
        (root / ".proofkit" / "extensions" / "hook-ext" / "TRUSTED").write_text("", encoding="utf-8")
        findings = sdd.run_extension_hooks(root, "on_verify", change_id="any", findings=[])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].message, "hook-injected-error")

    def test_extension_hook_skipped_without_trusted_marker(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-notrust-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        src = self._make_extension_source(root, "untrusted-ext")
        manifst = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
        manifst["hooks"] = True
        (src / "manifest.json").write_text(json.dumps(manifst), encoding="utf-8")
        (src / "hooks.py").write_text(
            "def on_verify(root, change_id, findings):\n"
            "    from proofkit._types import Finding\n"
            "    return findings + [Finding('error', None, 'should-not-appear')]\n",
            encoding="utf-8",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.install_extension(root, src)
        # No TRUSTED marker — hooks must be skipped (output may warn).
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.run_extension_hooks(root, "on_verify", change_id="any", findings=[])
        self.assertEqual(findings, [], "untrusted hooks must not inject findings")

    def test_install_extension_invalid_manifest_returns_finding(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-badmf-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        src = root / "ext-src" / "bad-ext"
        src.mkdir(parents=True)
        (src / "manifest.json").write_text("{not valid json", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            findings = sdd.install_extension(root, src)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_remove_extension_unknown_name_returns_finding(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"ext-rm-miss-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        findings = sdd.remove_extension(root, "nonexistent-ext")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    # ── project memory ──────────────────────────────────────────────────────────

    def test_init_project_creates_memory_directory_with_template_files(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-init-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        memory_dir = root / ".proofkit" / "memory"
        self.assertTrue(memory_dir.is_dir())
        self.assertTrue((memory_dir / "project.md").is_file())
        self.assertTrue((memory_dir / "decisions.md").is_file())

    def test_read_memory_entry_returns_content_after_init(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-read-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        content = sdd.read_memory_entry(root, "project")
        self.assertIsNotNone(content)
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)

    def test_append_memory_adds_content_to_project_md(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-append-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        findings = sdd.append_memory(root, "project", "## New Section\n\nSome content.")
        self.assertEqual(findings, [])
        content = sdd.read_memory_entry(root, "project")
        self.assertIn("New Section", content)

    def test_append_memory_supports_cp1252_stdout(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-append-cp1252-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)

        raw = io.BytesIO()
        cp1252_stdout = io.TextIOWrapper(raw, encoding="cp1252")
        with contextlib.redirect_stdout(cp1252_stdout):
            findings = sdd.append_memory(root, "project", "## New Section\n\nSome content.")
        cp1252_stdout.flush()

        self.assertEqual(findings, [])
        output = raw.getvalue().decode("cp1252")
        self.assertIn("Memory updated:", output)
        self.assertNotIn("\u2714", output)

    def test_append_memory_unknown_key_returns_error_finding(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-badkey-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        findings = sdd.append_memory(root, "nonexistent", "content")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_memory_show_returns_0_with_content(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-show-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = sdd.print_memory(root, "project")
        self.assertEqual(rc, 0)
        self.assertGreater(len(buf.getvalue()), 0)

    def test_status_output_includes_memory_word_count(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"mem-status-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            sdd.print_status(root)
        self.assertIn("memory", buf.getvalue().lower())

    # ── v0.19.0: Brownfield Bootstrap ─────────────────────────────────────

    def test_discover_repository_detects_python(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"disc-py-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
        info = sdd.discover_repository(root)
        self.assertIn("python", info.languages)

    def test_discover_repository_detects_node(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"disc-node-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        (root / "package.json").write_text('{"name":"x","scripts":{"test":"jest"}}\n', encoding="utf-8")
        info = sdd.discover_repository(root)
        self.assertIn("node", info.languages)

    def test_discover_repository_detects_rust(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"disc-rust-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        (root / "Cargo.toml").write_text("[package]\nname = \"x\"\n", encoding="utf-8")
        info = sdd.discover_repository(root)
        self.assertIn("rust", info.languages)

    def test_discover_repository_empty_project_has_no_languages(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"disc-empty-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        info = sdd.discover_repository(root)
        self.assertEqual(list(info.languages), [])

    def test_bootstrap_change_creates_scaffold(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"boot-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        with contextlib.redirect_stdout(io.StringIO()):
            change_id, findings = sdd.bootstrap_change(root, "Add brownfield support")
        self.assertEqual(findings, [])
        self.assertTrue((root / ".proofkit" / "changes" / change_id).is_dir())

    def test_bootstrap_change_requires_initialized_root(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"boot-uninit-{uuid.uuid4().hex}"
        root.mkdir(parents=True)
        with contextlib.redirect_stdout(io.StringIO()):
            _change_id, findings = sdd.bootstrap_change(root, "Should fail")
        self.assertTrue(any(f.severity == "error" for f in findings))

    # ── v0.20.0: Scale Adaptivity ─────────────────────────────────────────

    def test_suggest_profile_returns_quick_for_hotfix_title(self) -> None:
        profile = sdd.suggest_profile("hotfix: crash on startup")
        self.assertEqual(profile, "quick")

    def test_suggest_profile_returns_bugfix_for_bug_keywords(self) -> None:
        profile = sdd.suggest_profile("fix broken auth validation")
        self.assertEqual(profile, "bugfix")

    def test_suggest_profile_returns_refactor_for_refactor_keywords(self) -> None:
        profile = sdd.suggest_profile("refactor payment module")
        self.assertEqual(profile, "refactor")

    def test_suggest_profile_returns_standard_for_feature_title(self) -> None:
        profile = sdd.suggest_profile("add user notification preferences")
        self.assertEqual(profile, "standard")

    def test_suggest_profile_returns_research_for_research_title(self) -> None:
        profile = sdd.suggest_profile("research caching strategies for read-heavy endpoints")
        self.assertEqual(profile, "research")

    def test_bootstrap_change_auto_profile_uses_suggest_profile(self) -> None:
        root = REPO_ROOT / ".tmp-tests" / f"autoprof-{uuid.uuid4().hex}"
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.init_project(root)
        with contextlib.redirect_stdout(io.StringIO()):
            change_id, findings = sdd.bootstrap_change(root, "hotfix: crash on startup", profile="auto")
        self.assertEqual(findings, [])
        # change dir should exist
        self.assertTrue((root / ".proofkit" / "changes" / change_id).is_dir())
        # quick profile has proposal.md, tasks.md, verification.md
        artifacts = list((root / ".proofkit" / "changes" / change_id).iterdir())
        self.assertGreater(len(artifacts), 0)

    # ── v0.21.0: Multi-agent Runner ───────────────────────────────────────

    def test_dispatch_request_holds_fields(self) -> None:
        req = sdd.DispatchRequest(
            agent="shell",
            prompt="echo hello",
            working_dir=REPO_ROOT,
            timeout_seconds=10,
        )
        self.assertEqual(req.agent, "shell")
        self.assertEqual(req.prompt, "echo hello")
        self.assertEqual(req.timeout_seconds, 10)

    def test_dispatch_result_is_success_when_exit_zero(self) -> None:
        result = sdd.DispatchResult(exit_code=0, stdout="ok", stderr="", elapsed_seconds=0.1)
        self.assertTrue(result.success)

    def test_dispatch_result_is_failure_when_exit_nonzero(self) -> None:
        result = sdd.DispatchResult(exit_code=1, stdout="", stderr="err", elapsed_seconds=0.1)
        self.assertFalse(result.success)

    def test_shell_dispatcher_runs_echo(self) -> None:
        dispatcher = sdd.ShellAgentDispatcher()
        req = sdd.DispatchRequest(
            agent="shell",
            prompt="echo sdd-test-marker",
            working_dir=REPO_ROOT,
            timeout_seconds=10,
        )
        result = dispatcher.dispatch(req)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("sdd-test-marker", result.stdout)

    def test_shell_dispatcher_captures_failure(self) -> None:
        dispatcher = sdd.ShellAgentDispatcher()
        req = sdd.DispatchRequest(
            agent="shell",
            prompt="exit 42",
            working_dir=REPO_ROOT,
            timeout_seconds=10,
        )
        result = dispatcher.dispatch(req)
        self.assertFalse(result.success)

    def test_claude_code_dispatcher_returns_error_when_not_installed(self) -> None:
        import shutil as _shutil
        if _shutil.which("claude"):
            self.skipTest("claude CLI is installed; skipping unavailable-claude test")
        dispatcher = sdd.ClaudeCodeDispatcher()
        req = sdd.DispatchRequest(
            agent="claude-code",
            prompt="print hello",
            working_dir=REPO_ROOT,
            timeout_seconds=5,
        )
        result = dispatcher.dispatch(req)
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
