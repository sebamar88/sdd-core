from __future__ import annotations

import contextlib
import io
import uuid
import unittest
from importlib.resources import files
from pathlib import Path

from ssd_core import cli as sdd

REPO_ROOT = Path(__file__).resolve().parents[1]


class SddToolingTests(unittest.TestCase):
    def test_version_is_defined(self) -> None:
        self.assertEqual(sdd.VERSION, "0.1.0")

    def test_packaged_templates_are_present(self) -> None:
        template_root = files("ssd_core").joinpath("templates")

        self.assertTrue(template_root.joinpath("sdd", "constitution.md").is_file())
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
        self.assertTrue((root / ".sdd" / "adapters" / "generic-markdown.json").is_file())
        self.assertEqual(sdd.validate(root), [])

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
        self.assertIn("change does not exist", findings[0].message)

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
        verification_path.write_text(verification_text, encoding="utf-8")

        self.assertEqual(sdd.check_change(root, change_id), [])

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sdd.sync_specs(root, change_id), [])
            self.assertEqual(sdd.archive_change(root, change_id), [])

        self.assertFalse(change_dir.exists())
        self.assertTrue((root / ".sdd" / "specs" / change_id / "spec.md").is_file())
        archives = list((root / ".sdd" / "archive").glob(f"*-{change_id}"))
        self.assertEqual(len(archives), 1)


if __name__ == "__main__":
    unittest.main()
