"""Repository discovery and profile suggestion.

Depends on _wf_changeops (for create_change in bootstrap_change).
No circular imports from the perspective of this module.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from ._types import (
    Finding,
    RepositoryInfo,
    SDD_DIR,
)


def _pyproject_has_pytest(root: Path) -> bool:
    """Return True when pyproject.toml declares a [tool.pytest.ini_options] section."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        content = pyproject.read_text(encoding="utf-8")
        return "[tool.pytest" in content
    except OSError:
        return False


def discover_test_command(root: Path) -> str | None:
    """Auto-discover the project's test runner from common signal files."""
    has_pytest_config = (
        (root / "pytest.ini").exists()
        or (root / "setup.cfg").exists()
        or _pyproject_has_pytest(root)
    )
    if has_pytest_config and shutil.which("pytest"):
        return "python -m pytest"
    if has_pytest_config and shutil.which("python"):
        return "python -m pytest"

    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {}) or {}
            if isinstance(scripts, dict) and "test" in scripts:
                return "npm test"
        except (json.JSONDecodeError, OSError):
            pass

    if (root / "Cargo.toml").exists() and shutil.which("cargo"):
        return "cargo test"

    if (root / "go.mod").exists() and shutil.which("go"):
        return "go test ./..."

    makefile = root / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
            if re.search(r"^test:", content, re.MULTILINE):
                return "make test"
        except OSError:
            pass

    return None


def discover_repository(root: Path) -> RepositoryInfo:
    """Detect languages, CI presence, and test command for an existing repository."""
    languages: list[str] = []

    py_signals = ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]
    if any((root / f).exists() for f in py_signals):
        languages.append("python")

    if (root / "package.json").exists():
        languages.append("node")

    if (root / "Cargo.toml").exists():
        languages.append("rust")

    if (root / "go.mod").exists():
        languages.append("go")

    if (root / "pom.xml").exists() or (root / "build.gradle").exists():
        languages.append("java")

    ci_signals = [
        ".github/workflows",
        ".gitlab-ci.yml",
        ".circleci/config.yml",
        "Jenkinsfile",
        ".travis.yml",
    ]
    has_ci = any((root / s).exists() for s in ci_signals)
    has_sdd = (root / SDD_DIR).is_dir()
    test_cmd = discover_test_command(root)

    return RepositoryInfo(
        languages=tuple(languages),
        test_command=test_cmd,
        has_ci=has_ci,
        has_sdd=has_sdd,
    )


# Keyword scoring table for suggest_profile.
_PROFILE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("hotfix", "urgent", "critical", "emergency", "patch"), "quick"),
    (("bug", "fix", "broken", "error", "crash", "regression", "issue", "defect"), "bugfix"),
    (("refactor", "cleanup", "restructure", "reorganize", "simplify", "extract", "rename"), "refactor"),
    (("research", "investigate", "explore", "evaluate", "spike", "poc", "proof of concept", "analysis"), "research"),
    (("feature", "add", "implement", "build", "create", "new", "enhance", "improve"), "standard"),
]


def suggest_profile(title: str) -> str:
    """Return the best-matching SDD profile name for a change *title*."""
    tokens: set[str] = set(re.findall(r"[a-z0-9]+", title.lower()))
    best_profile = "standard"
    best_score = 0
    for keywords, candidate in _PROFILE_KEYWORDS:
        score = sum(1 for kw in keywords if kw in tokens)
        if score > best_score:
            best_score = score
            best_profile = candidate
    return best_profile


def bootstrap_change(
    root: Path,
    title: str,
    *,
    profile: str = "standard",
) -> tuple[str, list[Finding]]:
    """Create a change scaffold for an existing (brownfield) project.

    Pass ``profile="auto"`` to let :func:`suggest_profile` pick the best
    profile based on the title keywords.

    Returns ``(change_id, findings)``; findings is empty on success.
    """
    from ._wf_changeops import create_change

    if not (root / SDD_DIR).is_dir():
        return (
            "",
            [Finding("error", root / SDD_DIR, f"{SDD_DIR} directory not found — run 'proofkit init' first")],
        )

    resolved_profile = suggest_profile(title) if profile == "auto" else profile

    slug_base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "change"
    slug_base = slug_base[:40]
    change_id = slug_base

    changes_dir = root / SDD_DIR / "changes"
    if (changes_dir / change_id).exists():
        suffix = uuid.uuid4().hex[:6]
        change_id = f"{slug_base}-{suffix}"

    findings = create_change(root, change_id, resolved_profile, title)
    return (change_id if not findings else "", findings)
