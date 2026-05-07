"""Template resolution helpers, memory API, and install-commands.

Depends only on _types.  No circular imports.
"""
from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ._types import (
    Finding,
    TemplateResource,
    SDD_DIR,
    MEMORY_KEYS,
    _green,
    _dim,
)

# ── install-commands integration directories ───────────────────────────────────
_INTEGRATION_COMMAND_DIRS: dict[str, dict[str, str]] = {
    "claude-code": {"repo": ".claude/commands",              "user": ".claude/commands",              "local": ".claude/commands"},
    "copilot":     {"repo": ".github/copilot-prompts/sdd",   "user": ".github/copilot-prompts/sdd",   "local": ".github/copilot-prompts/sdd"},
    "opencode":    {"repo": ".opencode/commands/sdd",        "user": ".config/opencode/commands/sdd", "local": ".opencode/commands/sdd"},
    "codex":       {"repo": ".codex/commands/sdd",           "user": ".codex/commands/sdd",           "local": ".codex/commands/sdd"},
    "gemini-cli":  {"repo": ".gemini/commands/sdd",          "user": ".gemini/commands/sdd",          "local": ".gemini/commands/sdd"},
    "generic":     {"repo": f"{SDD_DIR}/commands",                 "user": f"{SDD_DIR}/commands",                 "local": f"{SDD_DIR}/commands"},
}

COMMAND_SCOPES: list[str] = ["repo", "user", "local"]

_COMMAND_FILES: list[str] = [
    "sdd-propose.md",
    "sdd-specify.md",
    "sdd-design.md",
    "sdd-tasks.md",
    "sdd-verify.md",
    "sdd-status.md",
]


def logical_path(root: Path, value: str) -> Path:
    return root.joinpath(*value.split("/"))


def template_sdd_root() -> TemplateResource:
    source_checkout_template = Path(__file__).resolve().parents[1] / SDD_DIR
    if source_checkout_template.is_dir():
        return source_checkout_template
    return files("proofkit").joinpath("templates", "sdd")  # type: ignore[return-value]


def template_docs_root() -> TemplateResource:
    source_checkout_docs = Path(__file__).resolve().parents[1] / "docs"
    if source_checkout_docs.is_dir():
        return source_checkout_docs
    return files("proofkit").joinpath("templates", "docs")


def template_commands_root() -> TemplateResource:
    source_checkout = Path(__file__).resolve().parent / "templates" / "commands"
    if source_checkout.is_dir():
        return source_checkout
    return files("proofkit").joinpath("templates", "commands")  # type: ignore[return-value]


def template_memory_root() -> TemplateResource:
    source_checkout = Path(__file__).resolve().parent / "templates" / "sdd" / "memory"
    if source_checkout.is_dir():
        return source_checkout
    return files("proofkit").joinpath("templates", "sdd", "memory")  # type: ignore[return-value]


def list_available_integrations() -> list[str]:
    """Return the sorted list of integration names supported by install_commands."""
    return sorted(_INTEGRATION_COMMAND_DIRS)


def memory_path(root: Path, key: str) -> Path:
    return root / SDD_DIR / "memory" / f"{key}.md"


def read_memory_entry(root: Path, key: str) -> str | None:
    """Return the content of ``key.md`` in the project memory, or None if missing."""
    path = memory_path(root, key)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def append_memory(root: Path, key: str, content: str) -> list[Finding]:
    """Append *content* to the memory file identified by *key*."""
    if key not in MEMORY_KEYS:
        known = ", ".join(MEMORY_KEYS)
        return [Finding("error", None, f"unknown memory key '{key}'; must be one of: {known}")]
    path = memory_path(root, key)
    if not path.is_file():
        return [Finding("error", path, f"memory file not found: {path.name} — run `proofkit init` first")]
    existing = path.read_text(encoding="utf-8")
    separator = "\n\n" if not existing.endswith("\n\n") else ""
    path.write_text(existing + separator + content + "\n", encoding="utf-8")
    print(_green("\u2714") + f" Memory updated: {path.relative_to(root).as_posix()}")
    return []


def _memory_word_count(root: Path) -> int:
    """Return total word count across all memory files."""
    total = 0
    for key in MEMORY_KEYS:
        content = read_memory_entry(root, key)
        if content:
            total += len(content.split())
    return total


def _ensure_gitignore_entry(root: Path, entry: str) -> None:
    """Append *entry* to ``.gitignore`` inside *root* if not already present."""
    gitignore = root / ".gitignore"
    if gitignore.is_file():
        existing = gitignore.read_text(encoding="utf-8")
        if any(line.strip() == entry for line in existing.splitlines()):
            return
        separator = "" if existing.endswith("\n") else "\n"
        gitignore.write_text(existing + separator + entry + "\n", encoding="utf-8")
    else:
        gitignore.write_text(entry + "\n", encoding="utf-8")


def install_commands(
    root: Path,
    integration: str,
    scope: str = "repo",
    *,
    _home: Path | None = None,
) -> list[Finding]:
    """Install ProofKit AI command scaffold files for *integration* at the given *scope*."""
    if integration not in _INTEGRATION_COMMAND_DIRS:
        known = ", ".join(sorted(_INTEGRATION_COMMAND_DIRS))
        return [Finding("error", None, f"unknown integration '{integration}'; known: {known}")]
    if scope not in COMMAND_SCOPES:
        return [Finding("error", None, f"unknown scope '{scope}'; must be one of: {', '.join(COMMAND_SCOPES)}")]

    dirs = _INTEGRATION_COMMAND_DIRS[integration]
    rel_dir = dirs[scope]
    target_dir = ((_home or Path.home()) / rel_dir) if scope == "user" else (root / rel_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    tmpl = template_commands_root()
    installed: list[str] = []
    skipped: list[str] = []
    for filename in _COMMAND_FILES:
        src = tmpl / filename
        dst = target_dir / filename
        if dst.exists():
            skipped.append(filename)
            continue
        copy_template_file(src, dst)
        installed.append(filename)

    if scope == "local":
        _ensure_gitignore_entry(root, rel_dir)

    scope_label = "user (~)" if scope == "user" else scope
    print(_green("\u2714") + f" [{integration}] commands installed ({scope_label}): {target_dir.as_posix()}")
    for f in installed:
        print("  " + _dim("-") + f" {f}")
    if skipped:
        print(_dim(f"  (skipped {len(skipped)} file(s) that already exist)"))
    return []


def copy_template_file(source: TemplateResource, destination: Path) -> None:
    destination.write_bytes(source.read_bytes())


def copy_template_directory_files(source: TemplateResource, destination: Path) -> None:
    destination.mkdir(exist_ok=True)
    for source_path in sorted(source.iterdir(), key=lambda item: item.name):
        if not source_path.is_file():
            continue
        target_path = destination / source_path.name
        if not target_path.exists():
            copy_template_file(source_path, target_path)
