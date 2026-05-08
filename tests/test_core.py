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


class TestCore(unittest.TestCase):
    @staticmethod
    def finding_messages(findings: list[sdd.Finding]) -> list[str]:
        return [finding.message for finding in findings]

    def test_version_is_defined(self) -> None:
        self.assertEqual(sdd.VERSION, "0.27.0")

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

    def test_runproof_brand_constants(self) -> None:
        self.assertEqual(sdd.SDD_DIR, ".runproof")
        self.assertIn("constitution", sdd.MEMORY_KEYS)


if __name__ == "__main__":
    unittest.main()
