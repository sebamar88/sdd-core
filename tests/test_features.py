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

_COMMAND_FILE_NAMES: list[str] = []


class TestFeatures(unittest.TestCase):
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
        commands_dir = tmp_home / ".runproof" / "commands"
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
        custom_file = root / ".runproof" / "commands" / "sdd-propose.md"
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
        ext_dir = root / ".runproof" / "extensions" / "my-ext"
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
        ext_dir = root / ".runproof" / "extensions" / "my-ext"
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
            "    from runproof._types import Finding\n"
            "    return findings + [Finding('error', None, 'hook-injected-error')]\n",
            encoding="utf-8",
        )
        with contextlib.redirect_stdout(io.StringIO()):
            sdd.install_extension(root, src)
        # Mark TRUSTED.
        (root / ".runproof" / "extensions" / "hook-ext" / "TRUSTED").write_text("", encoding="utf-8")
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
            "    from runproof._types import Finding\n"
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
        memory_dir = root / ".runproof" / "memory"
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
        self.assertTrue((root / ".runproof" / "changes" / change_id).is_dir())

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
        self.assertTrue((root / ".runproof" / "changes" / change_id).is_dir())
        # quick profile has proposal.md, tasks.md, verification.md
        artifacts = list((root / ".runproof" / "changes" / change_id).iterdir())
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
