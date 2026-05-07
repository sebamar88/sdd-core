"""Structural validation and project initialisation.

Depends on _types, _wf_templates (for path helpers and copy ops),
and _wf_artifacts (for read_frontmatter).  No circular imports.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ._types import (
    Finding,
    REQUIRED_DIRECTORIES,
    SDD_DIR,
    REQUIRED_ADAPTERS,
    REQUIRED_AGENTS,
    REQUIRED_PROFILES,
    REQUIRED_SCHEMAS,
    REQUIRED_SKILLS,
    PROFILE_ARTIFACTS,
    ARTIFACT_STATUSES,
    SCHEMA_PATTERN,
    TOKEN_PATTERN,
    DATE_PATTERN,
    FOUNDATION_COPY_DIRECTORIES,
    FOUNDATION_COPY_FILES,
    FOUNDATION_DOC_FILES,
    EMPTY_STATE_DIRECTORIES,
    MEMORY_COPY_FILES,
    trace,
)
from ._wf_artifacts import read_frontmatter
from ._wf_templates import (
    logical_path,
    template_sdd_root,
    template_docs_root,
    template_memory_root,
    copy_template_file,
    copy_template_directory_files,
)


def validate_required_directories(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for directory in REQUIRED_DIRECTORIES:
        path = logical_path(root, directory)
        if not path.is_dir():
            findings.append(Finding("error", path, "required directory is missing"))
    return findings


def validate_required_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for required_file in [f"{SDD_DIR}/protocol.md", f"{SDD_DIR}/constitution.md", f"{SDD_DIR}/state.json"]:
        path = logical_path(root, required_file)
        if not path.is_file():
            findings.append(Finding("error", path, "required file is missing"))

    for adapter in REQUIRED_ADAPTERS:
        path = logical_path(root, f"{SDD_DIR}/adapters/{adapter}")
        if not path.is_file():
            findings.append(Finding("error", path, "required adapter manifest is missing"))

    for agent in REQUIRED_AGENTS:
        path = logical_path(root, f"{SDD_DIR}/agents/{agent}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required agent is missing"))

    for profile in REQUIRED_PROFILES:
        path = logical_path(root, f"{SDD_DIR}/profiles/{profile}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required profile is missing"))

    for skill in REQUIRED_SKILLS:
        path = logical_path(root, f"{SDD_DIR}/skills/{skill}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required skill is missing"))

    for schema_name in REQUIRED_SCHEMAS:
        path = logical_path(root, f"{SDD_DIR}/schemas/{schema_name}")
        if not path.is_file():
            findings.append(Finding("error", path, "required schema is missing"))

    return findings


def validate_markdown_frontmatter(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    sdd_root = root / SDD_DIR
    if not sdd_root.exists():
        return findings

    for path in sorted(sdd_root.rglob("*.md")):
        try:
            relative_parts = path.relative_to(sdd_root).parts
        except ValueError:
            relative_parts = ()
        if relative_parts and relative_parts[0] == "memory":
            continue

        metadata, error = read_frontmatter(path)
        if error is not None:
            findings.append(Finding("error", path, error))
            continue

        try:
            relative = path.relative_to(sdd_root)
        except ValueError:
            relative = path

        is_change_artifact = len(relative.parts) >= 3 and relative.parts[0] == "changes"
        is_example_artifact = len(relative.parts) >= 3 and relative.parts[0] == "examples"
        is_living_spec = len(relative.parts) >= 3 and relative.parts[0] == "specs"

        for key in ["schema", "artifact", "status", "created", "updated"]:
            if key not in metadata:
                findings.append(Finding("error", path, f"frontmatter missing required key: {key}"))

        schema = metadata.get("schema")
        if schema and not SCHEMA_PATTERN.match(schema):
            findings.append(Finding("error", path, f"schema value is not valid: {schema}"))

        artifact = metadata.get("artifact")
        if artifact and not TOKEN_PATTERN.match(artifact):
            findings.append(Finding("error", path, f"artifact value is not valid: {artifact}"))

        status = metadata.get("status")
        if status and status not in ARTIFACT_STATUSES:
            findings.append(Finding("error", path, f"status value is not valid: {status}"))

        for date_key in ["created", "updated"]:
            date_value = metadata.get(date_key)
            if not date_value:
                continue
            if not DATE_PATTERN.match(date_value):
                findings.append(Finding("error", path, f"{date_key} must use YYYY-MM-DD format"))
                continue
            try:
                date.fromisoformat(date_value)
            except ValueError:
                findings.append(Finding("error", path, f"{date_key} is not a valid calendar date"))

        profile = metadata.get("profile")
        if profile and profile not in REQUIRED_PROFILES:
            findings.append(Finding("error", path, f"profile value is not recognized: {profile}"))

        if is_change_artifact or is_example_artifact:
            change_id = metadata.get("change_id")
            expected_change_id = relative.parts[1]
            if not change_id:
                findings.append(Finding("error", path, "frontmatter missing required key: change_id"))
            elif change_id != expected_change_id:
                findings.append(Finding("error", path, f"change_id does not match directory name: expected {expected_change_id}"))

            if not profile:
                findings.append(Finding("error", path, "frontmatter missing required key: profile"))

            expected_artifact = path.stem
            if artifact and artifact != expected_artifact:
                findings.append(Finding("error", path, f"artifact value must match filename stem: expected {expected_artifact}"))

        if is_living_spec:
            change_id = metadata.get("change_id")
            expected_change_id = relative.parts[1]
            if not change_id:
                findings.append(Finding("error", path, "frontmatter missing required key: change_id"))
            elif change_id != expected_change_id:
                findings.append(Finding("error", path, f"change_id does not match directory name: expected {expected_change_id}"))

            expected_artifact = path.stem
            if path.name == "spec.md":
                expected_artifact = "spec"
            if artifact and artifact != expected_artifact:
                findings.append(Finding("error", path, f"artifact value must match filename stem: expected {expected_artifact}"))

    return findings


def validate_json_schemas(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    schema_dir = root / SDD_DIR / "schemas"
    if not schema_dir.exists():
        return findings

    for path in sorted(schema_dir.glob("*.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("error", path, f"invalid JSON: {exc.msg} at line {exc.lineno}"))
            continue

        for key in ["$schema", "$id", "title", "type"]:
            if key not in schema:
                findings.append(Finding("error", path, f"schema missing required key: {key}"))

        if schema.get("type") != "object":
            findings.append(Finding("error", path, "schema top-level type must be object"))

    return findings


def validate_protocol_pointer(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    protocol_path = root / SDD_DIR / "protocol.md"
    if not protocol_path.exists():
        return findings

    text = protocol_path.read_text(encoding="utf-8")
    canonical = root / "docs" / "proofkit-protocol-v0.1.md"
    if "docs/proofkit-protocol-v0.1.md" not in text and "docs\\proofkit-protocol-v0.1.md" not in text:
        findings.append(Finding("warning", protocol_path, "protocol pointer does not name the canonical v0.1 spec"))
    if not canonical.is_file():
        findings.append(Finding("error", canonical, "canonical protocol spec is missing"))

    return findings


def validate(root: Path) -> list[Finding]:
    trace("VALIDATION", f"validate root={root.name}")
    checks = [
        validate_required_directories,
        validate_required_files,
        validate_markdown_frontmatter,
        validate_json_schemas,
        validate_protocol_pointer,
    ]
    findings: list[Finding] = []
    for check in checks:
        findings.extend(check(root))
    return findings


def init_project(root: Path) -> list[Finding]:
    source = template_sdd_root()
    if not source.is_dir():
        return [Finding("error", None, f"template {SDD_DIR} directory is missing")]

    root.mkdir(parents=True, exist_ok=True)
    target = root / SDD_DIR
    target.mkdir(exist_ok=True)

    for directory in FOUNDATION_COPY_DIRECTORIES:
        source_dir = source.joinpath(directory)
        target_dir = target / directory
        if not source_dir.is_dir():
            return [Finding("error", None, f"template directory is missing: {directory}")]
        copy_template_directory_files(source_dir, target_dir)

    for filename in FOUNDATION_COPY_FILES:
        source_file = source.joinpath(filename)
        destination = target / filename
        if not source_file.is_file():
            return [Finding("error", None, f"template file is missing: {filename}")]
        if not destination.exists():
            copy_template_file(source_file, destination)

    source_docs = template_docs_root()
    target_docs = root / "docs"
    target_docs.mkdir(exist_ok=True)
    for filename in FOUNDATION_DOC_FILES:
        source_file = source_docs.joinpath(filename)
        destination = target_docs / filename
        if not source_file.is_file():
            return [Finding("error", None, f"template doc is missing: {filename}")]
        if not destination.exists():
            copy_template_file(source_file, destination)

    for directory in EMPTY_STATE_DIRECTORIES:
        state_dir = target / directory
        state_dir.mkdir(exist_ok=True)
        keep = state_dir / ".gitkeep"
        if not keep.exists():
            keep.write_text("\n", encoding="utf-8")

    memory_dir = target / "memory"
    memory_dir.mkdir(exist_ok=True)
    tmpl_memory = template_memory_root()
    for filename in MEMORY_COPY_FILES:
        src = tmpl_memory.joinpath(filename)
        dst = memory_dir / filename
        if src.is_file() and not dst.exists():
            copy_template_file(src, dst)

    print(f"Initialized ProofKit at: {target.as_posix()}")
    return []
