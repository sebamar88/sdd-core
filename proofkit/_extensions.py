"""proofkit._extensions — Extension system for ProofKit.

Third-party extensions can add profiles, agents, skills, and command scaffolds
without forking the core package.  They may also ship a ``hooks.py`` that
participates in the verify and guard lifecycle.

Trust model
-----------
Hooks are Python code and are therefore not auto-loaded.  A human must create a
``TRUSTED`` marker file inside the installed extension directory:

    .sdd/extensions/<name>/TRUSTED

Without that file, the extension's hooks.py is silently skipped (a warning is
printed so the operator knows why hooks are not running).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from ._types import Finding, SDD_DIR

# ── Data model ────────────────────────────────────────────────────────────────

_MANIFEST_SCHEMA = "sdd.extension.v1"
_REQUIRED_MANIFEST_KEYS = {"schema", "name", "version", "description", "author"}


@dataclass(frozen=True)
class Extension:
    name: str
    version: str
    description: str
    author: str
    has_templates: bool
    has_hooks: bool
    root_dir: Path

    @property
    def is_trusted(self) -> bool:
        return (self.root_dir / "TRUSTED").is_file()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extensions_dir(root: Path) -> Path:
    return root / SDD_DIR / "extensions"


def _read_manifest(manifest_path: Path) -> tuple[dict | None, str | None]:
    """Return (manifest_dict, error_message).  error_message is None on success."""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"manifest.json is not valid JSON: {exc}"

    if not isinstance(data, dict):
        return None, "manifest.json must be a JSON object"

    missing = _REQUIRED_MANIFEST_KEYS - data.keys()
    if missing:
        return None, f"manifest.json missing required fields: {', '.join(sorted(missing))}"

    if data.get("schema") != _MANIFEST_SCHEMA:
        return None, f"manifest schema must be '{_MANIFEST_SCHEMA}', got: {data.get('schema')!r}"

    return data, None


# ── Public API ────────────────────────────────────────────────────────────────

def load_extensions(root: Path) -> list[Extension]:
    """Return all installed extensions.  Returns [] when none are installed."""
    ext_base = _extensions_dir(root)
    if not ext_base.is_dir():
        return []

    result: list[Extension] = []
    for entry in sorted(ext_base.iterdir()):
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.is_file():
            continue
        data, error = _read_manifest(manifest_path)
        if error is not None or data is None:
            continue
        result.append(
            Extension(
                name=data["name"],
                version=data["version"],
                description=data["description"],
                author=data["author"],
                has_templates=bool(data.get("templates", False)),
                has_hooks=bool(data.get("hooks", False)),
                root_dir=entry,
            )
        )
    return result


def install_extension(root: Path, source_path: Path) -> list[Finding]:
    """Install an extension from *source_path* into ``.sdd/extensions/<name>/``.

    *source_path* must be a directory containing a valid ``manifest.json``.
    Existing installations are replaced (allows upgrades).
    """
    manifest_path = source_path / "manifest.json"
    if not manifest_path.is_file():
        return [Finding("error", source_path, "manifest.json not found in extension source directory")]

    data, error = _read_manifest(manifest_path)
    if error is not None or data is None:
        return [Finding("error", manifest_path, error or "invalid manifest")]

    name = data["name"]
    ext_base = _extensions_dir(root)
    ext_base.mkdir(parents=True, exist_ok=True)

    target = ext_base / name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source_path, target)

    print(f"\u2714 Extension installed: {name} {data['version']}")
    if data.get("hooks"):
        print("  \u26a0  This extension ships hooks.py.  To enable hooks, create:")
        print(f"        {(target / 'TRUSTED').as_posix()}")
    return []


def remove_extension(root: Path, name: str) -> list[Finding]:
    """Remove (uninstall) the extension named *name*."""
    target = _extensions_dir(root) / name
    if not target.is_dir():
        return [Finding("error", target, f"extension '{name}' is not installed")]

    shutil.rmtree(target)
    print(f"\u2714 Extension removed: {name}")
    return []


def run_extension_hooks(
    root: Path,
    hook_name: str,
    **kwargs,
) -> list[Finding]:
    """Call *hook_name* on every trusted installed extension and aggregate results.

    The hook signature is:
        def <hook_name>(root: Path, findings: list[Finding], **kwargs) -> list[Finding]

    Extensions without a TRUSTED marker are silently skipped (a warning is
    printed to stdout so operators know why hooks are inactive).

    Returns the accumulated list of additional findings.
    """
    extensions = load_extensions(root)
    extra: list[Finding] = []
    findings_arg: list[Finding] = list(kwargs.pop("findings", []))

    for ext in extensions:
        if not ext.has_hooks:
            continue

        if not ext.is_trusted:
            print(
                f"\u26a0  Extension '{ext.name}' has hooks but is not trusted — "
                "create a TRUSTED file to enable"
            )
            continue

        hooks_path = ext.root_dir / "hooks.py"
        if not hooks_path.is_file():
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f"sdd_ext_{ext.name}_hooks", hooks_path
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            # Register in sys.modules so relative imports within hooks.py work.
            sys.modules[f"sdd_ext_{ext.name}_hooks"] = module
            spec.loader.exec_module(module)  # type: ignore[attr-defined]

            hook_fn = getattr(module, hook_name, None)
            if hook_fn is None:
                continue

            result = hook_fn(root=root, findings=list(findings_arg), **kwargs)
            if isinstance(result, list):
                # Collect any new findings the hook injected.
                for item in result:
                    if item not in findings_arg and isinstance(item, Finding):
                        extra.append(item)
        except Exception as exc:
            extra.append(
                Finding(
                    "error",
                    ext.root_dir,
                    f"extension hook '{hook_name}' in '{ext.name}' raised: {exc}",
                )
            )

    return extra
