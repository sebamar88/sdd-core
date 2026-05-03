from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sdd  # noqa: E402


class SddToolingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
