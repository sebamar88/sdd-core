from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Iterable, Protocol


VERSION = "0.1.0"

REQUIRED_DIRECTORIES = [
    ".sdd",
    ".sdd/adapters",
    ".sdd/agents",
    ".sdd/profiles",
    ".sdd/schemas",
    ".sdd/skills",
    ".sdd/specs",
    ".sdd/changes",
    ".sdd/archive",
]

REQUIRED_ADAPTERS = [
    "claude-code.json",
    "codex.json",
    "generic-markdown.json",
    "gemini-cli.json",
    "opencode.json",
    "qwen-code.json",
]

REQUIRED_AGENTS = [
    "orchestrator",
    "explorer",
    "specifier",
    "architect",
    "planner",
    "implementer",
    "verifier",
    "critic",
    "archivist",
]

REQUIRED_PROFILES = [
    "quick",
    "standard",
    "bugfix",
    "refactor",
    "enterprise",
    "research",
]

REQUIRED_SCHEMAS = [
    "agent.schema.json",
    "adapter-capabilities.schema.json",
    "artifact.schema.json",
    "phase-result.schema.json",
    "skill.schema.json",
    "verification.schema.json",
]

REQUIRED_SKILLS = [
    "propose",
    "specify",
    "design",
    "task",
    "implement",
    "verify",
    "critique",
    "sync-specs",
    "archive",
]

PROFILE_ARTIFACTS = {
    "quick": ["proposal.md", "tasks.md", "verification.md"],
    "standard": ["proposal.md", "delta-spec.md", "design.md", "tasks.md", "verification.md", "archive.md"],
    "bugfix": ["proposal.md", "tasks.md", "verification.md"],
    "refactor": ["proposal.md", "tasks.md", "verification.md"],
    "enterprise": [
        "proposal.md",
        "delta-spec.md",
        "design.md",
        "tasks.md",
        "verification.md",
        "critique.md",
        "archive.md",
    ],
    "research": ["proposal.md", "findings.md", "decision.md"],
}

FOUNDATION_COPY_DIRECTORIES = [
    "adapters",
    "agents",
    "profiles",
    "schemas",
    "skills",
]

FOUNDATION_COPY_FILES = [
    "constitution.md",
    "protocol.md",
]

FOUNDATION_DOC_FILES = [
    "adapter-contract-v0.1.md",
    "adapter-authoring-v0.1.md",
    "adapters-v0.1.md",
    "production-readiness-v0.1.md",
    "sdd-core-protocol-v0.1.md",
    "sdd-validator-v0.1.md",
]

EMPTY_STATE_DIRECTORIES = [
    "archive",
    "changes",
    "specs",
]

ARTIFACT_STATUSES = {
    "draft",
    "ready",
    "active",
    "in_progress",
    "blocked",
    "verified",
    "archived",
}

SCHEMA_PATTERN = re.compile(r"^sdd\.[a-z0-9-]+\.v[0-9]+$")
TOKEN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
OPEN_TASK_PATTERN = re.compile(r"^\s*-\s+\[\s\]", re.MULTILINE)


class TemplateResource(Protocol):
    name: str

    def is_dir(self) -> bool: ...

    def is_file(self) -> bool: ...

    def iterdir(self) -> Iterable["TemplateResource"]: ...

    def joinpath(self, *descendants: str) -> "TemplateResource": ...

    def read_bytes(self) -> bytes: ...


@dataclass(frozen=True)
class Finding:
    severity: str
    path: Path | None
    message: str

    def format(self, root: Path) -> str:
        location = ""
        if self.path is not None:
            try:
                location = f"{self.path.relative_to(root).as_posix()}: "
            except ValueError:
                location = f"{self.path}: "
        return f"{self.severity.upper()}: {location}{self.message}"


@dataclass(frozen=True)
class ChangeSummary:
    change_id: str
    profile: str
    present: list[str]
    missing: list[str]
    statuses: dict[str, str]

    @property
    def is_complete(self) -> bool:
        return not self.missing


def logical_path(root: Path, value: str) -> Path:
    return root.joinpath(*value.split("/"))


def template_sdd_root() -> TemplateResource:
    source_checkout_template = Path(__file__).resolve().parents[1] / ".sdd"
    if source_checkout_template.is_dir():
        return source_checkout_template
    return files("ssd_core").joinpath("templates", "sdd")  # type: ignore[return-value]


def template_docs_root() -> TemplateResource:
    source_checkout_docs = Path(__file__).resolve().parents[1] / "docs"
    if source_checkout_docs.is_dir():
        return source_checkout_docs
    return files("ssd_core").joinpath("templates", "docs")


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


def artifact_name(filename: str) -> str:
    return filename.removesuffix(".md")


def frontmatter(schema: str, artifact: str, change_id: str, profile: str, today: str) -> str:
    return "\n".join(
        [
            "---",
            f"schema: {schema}",
            f"artifact: {artifact}",
            f"change_id: {change_id}",
            f"profile: {profile}",
            "status: draft",
            f"created: {today}",
            f"updated: {today}",
            "---",
            "",
        ]
    )


def living_spec_frontmatter(change_id: str, today: str) -> str:
    return "\n".join(
        [
            "---",
            "schema: sdd.living-spec.v1",
            "artifact: spec",
            f"change_id: {change_id}",
            "status: active",
            f"created: {today}",
            f"updated: {today}",
            "---",
            "",
        ]
    )


def artifact_title(filename: str) -> str:
    words = artifact_name(filename).replace("-", " ").split()
    return " ".join(word.capitalize() for word in words)


def artifact_body(filename: str, change_id: str, title: str, profile: str, today: str) -> str:
    artifact = artifact_name(filename)
    header = frontmatter("sdd.artifact.v1", artifact, change_id, profile, today)
    heading = f"# {artifact_title(filename)}"

    if filename == "proposal.md":
        return (
            header
            + f"{heading}\n\n"
            + f"## Intent\n\n{title}\n\n"
            + "## Scope\n\n- Define the intended change.\n\n"
            + "## Non-Scope\n\n- Record what this change will not address.\n\n"
            + "## Risks\n\n- Record known risks or write `None`.\n"
        )

    if filename == "delta-spec.md":
        return (
            header
            + f"{heading}\n\n"
            + "## ADDED\n\n- List new observable behavior.\n\n"
            + "## MODIFIED\n\n- List changed observable behavior.\n\n"
            + "## REMOVED\n\n- List removed observable behavior.\n"
        )

    if filename == "design.md":
        return (
            header
            + f"{heading}\n\n"
            + "## Approach\n\n- Describe the technical approach.\n\n"
            + "## Decisions\n\n- Record important decisions and rationale.\n\n"
            + "## Alternatives Rejected\n\n- Record alternatives and why they were rejected.\n"
        )

    if filename == "tasks.md":
        return (
            header
            + f"{heading}\n\n"
            + "- [ ] T-001 Define the first concrete task.\n"
            + "  - Requirement: proposal\n"
            + "  - Evidence: verification.md\n"
        )

    if filename == "verification.md":
        return (
            frontmatter("sdd.verification.v1", artifact, change_id, profile, today)
            + f"{heading}\n\n"
            + "## Matrix\n\n"
            + "| Requirement | Scenario | Tasks | Evidence | Status |\n"
            + "| --- | --- | --- | --- | --- |\n"
            + "| proposal | initial scenario | T-001 | pending verification evidence | not-run |\n\n"
            + "## Commands\n\n- Record host-project verification actions.\n\n"
            + "## Manual Checks\n\n- Record manual evidence when relevant.\n\n"
            + "## Gaps\n\n- Record known gaps or write `None`.\n"
        )

    if filename == "critique.md":
        return (
            header
            + f"{heading}\n\n"
            + "## Verdict\n\n- draft\n\n"
            + "## Findings\n\n- Record blocking and non-blocking findings.\n\n"
            + "## Required Fixes\n\n- Record required fixes or write `None`.\n"
        )

    if filename == "archive.md":
        return (
            header
            + f"{heading}\n\n"
            + "## Archive Status\n\n- draft\n\n"
            + "## Spec Sync\n\n- Record living spec updates.\n\n"
            + "## Final Evidence\n\n- Link verification and critique evidence.\n"
        )

    if filename == "findings.md":
        return (
            header
            + f"{heading}\n\n"
            + "## Research Question\n\n{title}\n\n"
            + "## Sources Inspected\n\n- Record sources, files, commands, or URLs.\n\n"
            + "## Findings\n\n- Record findings.\n\n"
            + "## Unresolved Questions\n\n- Record remaining uncertainty or write `None`.\n"
        )

    if filename == "decision.md":
        return (
            header
            + f"{heading}\n\n"
            + "## Recommendation\n\n- Record the recommendation.\n\n"
            + "## Rationale\n\n- Record the rationale.\n\n"
            + "## Tradeoffs\n\n- Record tradeoffs.\n"
        )

    return header + f"{heading}\n"


def read_frontmatter(path: Path) -> tuple[dict[str, str], str | None]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "missing opening frontmatter marker"

    close_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_index = index
            break

    if close_index is None:
        return {}, "missing closing frontmatter marker"

    frontmatter: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:close_index], start=2):
        stripped = line.strip()
        if not stripped:
            continue
        if ":" not in stripped:
            return {}, f"invalid frontmatter line {line_number}: expected key: value"
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = raw_value.strip().strip('"').strip("'")
        if not key:
            return {}, f"invalid frontmatter line {line_number}: empty key"
        frontmatter[key] = value

    return frontmatter, None


def validate_required_directories(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for directory in REQUIRED_DIRECTORIES:
        path = logical_path(root, directory)
        if not path.is_dir():
            findings.append(Finding("error", path, "required directory is missing"))
    return findings


def validate_required_files(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for required_file in [".sdd/protocol.md", ".sdd/constitution.md"]:
        path = logical_path(root, required_file)
        if not path.is_file():
            findings.append(Finding("error", path, "required file is missing"))

    for adapter in REQUIRED_ADAPTERS:
        path = logical_path(root, f".sdd/adapters/{adapter}")
        if not path.is_file():
            findings.append(Finding("error", path, "required adapter manifest is missing"))

    for agent in REQUIRED_AGENTS:
        path = logical_path(root, f".sdd/agents/{agent}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required agent is missing"))

    for profile in REQUIRED_PROFILES:
        path = logical_path(root, f".sdd/profiles/{profile}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required profile is missing"))

    for skill in REQUIRED_SKILLS:
        path = logical_path(root, f".sdd/skills/{skill}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required skill is missing"))

    for schema_name in REQUIRED_SCHEMAS:
        path = logical_path(root, f".sdd/schemas/{schema_name}")
        if not path.is_file():
            findings.append(Finding("error", path, "required schema is missing"))

    return findings


def validate_markdown_frontmatter(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    sdd_root = root / ".sdd"
    if not sdd_root.exists():
        return findings

    for path in sorted(sdd_root.rglob("*.md")):
        metadata, error = read_frontmatter(path)
        if error is not None:
            findings.append(Finding("error", path, error))
            continue

        for key in ["schema", "artifact", "status"]:
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

        profile = metadata.get("profile")
        if profile and profile not in REQUIRED_PROFILES:
            findings.append(Finding("error", path, f"profile value is not recognized: {profile}"))

    return findings


def validate_json_schemas(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    schema_dir = root / ".sdd" / "schemas"
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
    protocol_path = root / ".sdd" / "protocol.md"
    if not protocol_path.exists():
        return findings

    text = protocol_path.read_text(encoding="utf-8")
    canonical = root / "docs" / "sdd-core-protocol-v0.1.md"
    if "docs/sdd-core-protocol-v0.1.md" not in text and "docs\\sdd-core-protocol-v0.1.md" not in text:
        findings.append(Finding("warning", protocol_path, "protocol pointer does not name the canonical v0.1 spec"))
    if not canonical.is_file():
        findings.append(Finding("error", canonical, "canonical protocol spec is missing"))

    return findings


def validate(root: Path) -> list[Finding]:
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
        return [Finding("error", None, "template .sdd directory is missing")]

    root.mkdir(parents=True, exist_ok=True)
    target = root / ".sdd"
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

    print(f"Initialized SDD-Core at: {target.as_posix()}")
    return []


def detect_change_profile(change_dir: Path) -> str:
    for path in sorted(change_dir.glob("*.md")):
        metadata, error = read_frontmatter(path)
        if error is None:
            profile = metadata.get("profile")
            if profile in PROFILE_ARTIFACTS:
                return profile
    return "unknown"


def summarize_change(change_dir: Path) -> ChangeSummary:
    profile = detect_change_profile(change_dir)
    present = sorted(path.name for path in change_dir.glob("*.md") if path.is_file())
    expected = PROFILE_ARTIFACTS.get(profile, [])
    missing = [filename for filename in expected if filename not in present]
    statuses: dict[str, str] = {}

    for filename in present:
        path = change_dir / filename
        metadata, error = read_frontmatter(path)
        if error is not None:
            statuses[filename] = "invalid-frontmatter"
        else:
            statuses[filename] = metadata.get("status", "unknown")

    return ChangeSummary(
        change_id=change_dir.name,
        profile=profile,
        present=present,
        missing=missing,
        statuses=statuses,
    )


def active_change_directories(root: Path) -> list[Path]:
    changes_dir = root / ".sdd" / "changes"
    if not changes_dir.is_dir():
        return []
    return sorted(path for path in changes_dir.iterdir() if path.is_dir())


def status(root: Path) -> tuple[list[Finding], list[ChangeSummary]]:
    findings = validate(root)
    changes = [summarize_change(path) for path in active_change_directories(root)]
    for change in changes:
        if change.profile == "unknown":
            findings.append(Finding("warning", root / ".sdd" / "changes" / change.change_id, "could not detect profile"))
        if change.missing:
            missing = ", ".join(change.missing)
            findings.append(Finding("warning", root / ".sdd" / "changes" / change.change_id, f"missing profile artifacts: {missing}"))
    return findings, changes


def change_directory(root: Path, change_id: str) -> Path:
    return root / ".sdd" / "changes" / change_id


def validate_change_id(change_id: str) -> list[Finding]:
    if not TOKEN_PATTERN.match(change_id):
        return [Finding("error", None, f"change-id is not valid: {change_id}")]
    return []


def check_change(root: Path, change_id: str) -> list[Finding]:
    findings = validate_change_id(change_id)
    if findings:
        return findings

    change_dir = change_directory(root, change_id)
    if not change_dir.is_dir():
        return [Finding("error", change_dir, "change does not exist")]

    summary = summarize_change(change_dir)
    if summary.profile == "unknown":
        findings.append(Finding("error", change_dir, "could not detect profile"))
        return findings

    for filename in summary.missing:
        findings.append(Finding("error", change_dir / filename, "required profile artifact is missing"))

    for filename in summary.present:
        path = change_dir / filename
        metadata, error = read_frontmatter(path)
        if error is not None:
            findings.append(Finding("error", path, error))
            continue
        if metadata.get("status") == "blocked":
            findings.append(Finding("error", path, "artifact status is blocked"))

    tasks_path = change_dir / "tasks.md"
    if tasks_path.is_file():
        tasks_text = tasks_path.read_text(encoding="utf-8")
        if OPEN_TASK_PATTERN.search(tasks_text):
            findings.append(Finding("error", tasks_path, "open tasks remain"))

    verification_path = change_dir / "verification.md"
    if verification_path.is_file():
        metadata, error = read_frontmatter(verification_path)
        if error is None and metadata.get("status") != "verified":
            findings.append(Finding("error", verification_path, "verification status must be verified"))

        verification_text = verification_path.read_text(encoding="utf-8").lower()
        blocked_terms = ["not-run", "pending verification evidence"]
        for term in blocked_terms:
            if term in verification_text:
                findings.append(Finding("error", verification_path, f"verification still contains: {term}"))

    return findings


def print_check(root: Path, change_id: str) -> int:
    findings = check_change(root, change_id)
    if not findings:
        print(f"Change {change_id} is ready.")
        return 0

    print(f"Change {change_id} is not ready.")
    for finding in findings:
        print(finding.format(root))
    return 1


def archive_change(root: Path, change_id: str) -> list[Finding]:
    findings = check_change(root, change_id)
    if findings:
        return findings

    source = change_directory(root, change_id)
    archive_root = root / ".sdd" / "archive"
    if not archive_root.is_dir():
        return [Finding("error", archive_root, "archive directory is missing")]

    destination = archive_root / f"{date.today().isoformat()}-{change_id}"
    if destination.exists():
        return [Finding("error", destination, "archive destination already exists")]

    changes_root = (root / ".sdd" / "changes").resolve()
    source_resolved = source.resolve()
    if not source_resolved.is_relative_to(changes_root):
        return [Finding("error", source, "resolved change path is outside .sdd/changes")]

    shutil.copytree(source_resolved, destination)
    shutil.rmtree(source_resolved)
    print(f"Archived change: {destination.as_posix()}")
    return []


def strip_frontmatter_text(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :]).lstrip() + ("\n" if text.endswith("\n") else "")
    return text


def append_sync_record(archive_path: Path, spec_path: Path, root: Path) -> None:
    relative_spec = spec_path.relative_to(root).as_posix()
    existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
    marker = f"- Synced living spec: `{relative_spec}`"
    if marker in existing:
        return
    suffix = "\n" if existing.endswith("\n") or not existing else "\n\n"
    archive_path.write_text(existing + suffix + "## Sync Record\n\n" + marker + "\n", encoding="utf-8")


def sync_specs(root: Path, change_id: str) -> list[Finding]:
    findings = check_change(root, change_id)
    if findings:
        return findings

    change_dir = change_directory(root, change_id)
    delta_path = change_dir / "delta-spec.md"
    if not delta_path.is_file():
        return [Finding("error", delta_path, "delta-spec.md is required for spec sync")]

    specs_root = root / ".sdd" / "specs"
    if not specs_root.is_dir():
        return [Finding("error", specs_root, "specs directory is missing")]

    spec_dir = specs_root / change_id
    spec_path = spec_dir / "spec.md"
    if spec_path.exists():
        return [Finding("error", spec_path, "living spec already exists")]

    today = date.today().isoformat()
    delta_body = strip_frontmatter_text(delta_path.read_text(encoding="utf-8"))
    spec_dir.mkdir(parents=True)
    spec_path.write_text(
        living_spec_frontmatter(change_id, today)
        + f"# {change_id.replace('-', ' ').title()} Spec\n\n"
        + "## Source Change\n\n"
        + f"- `{change_dir.relative_to(root).as_posix()}`\n\n"
        + "## Behavior Delta Applied\n\n"
        + delta_body,
        encoding="utf-8",
    )

    archive_path = change_dir / "archive.md"
    if archive_path.is_file():
        append_sync_record(archive_path, spec_path, root)

    print(f"Synced living spec: {spec_path.as_posix()}")
    return []


def print_status(root: Path) -> int:
    findings, changes = status(root)
    errors = [finding for finding in findings if finding.severity == "error"]
    warnings = [finding for finding in findings if finding.severity == "warning"]

    print("SDD status")
    print(f"- root: {root}")
    print(f"- validation: {'fail' if errors else 'pass'}")
    print(f"- active changes: {len(changes)}")

    if changes:
        print("")
        print("Changes:")
        for change in changes:
            completeness = "complete" if change.is_complete else "incomplete"
            print(f"- {change.change_id} [{change.profile}] {completeness}")
            if change.present:
                present = ", ".join(change.present)
                print(f"  present: {present}")
            if change.missing:
                missing = ", ".join(change.missing)
                print(f"  missing: {missing}")

    if findings:
        print("")
        print("Findings:")
        for finding in findings:
            print(finding.format(root))

    return 1 if errors else 0


def create_change(root: Path, change_id: str, profile: str, title: str | None) -> list[Finding]:
    findings: list[Finding] = []
    if not TOKEN_PATTERN.match(change_id):
        return [Finding("error", None, f"change-id is not valid: {change_id}")]

    if profile not in PROFILE_ARTIFACTS:
        return [Finding("error", None, f"profile is not recognized: {profile}")]

    changes_dir = root / ".sdd" / "changes"
    profile_path = root / ".sdd" / "profiles" / f"{profile}.md"
    if not changes_dir.is_dir():
        findings.append(Finding("error", changes_dir, "required changes directory is missing"))
    if not profile_path.is_file():
        findings.append(Finding("error", profile_path, "selected profile file is missing"))
    if findings:
        return findings

    change_dir = changes_dir / change_id
    if change_dir.exists():
        return [Finding("error", change_dir, "change already exists")]

    today = date.today().isoformat()
    resolved_title = title or change_id.replace("-", " ")
    change_dir.mkdir(parents=True)
    for filename in PROFILE_ARTIFACTS[profile]:
        path = change_dir / filename
        path.write_text(artifact_body(filename, change_id, resolved_title, profile, today), encoding="utf-8")

    print(f"Created change: {change_dir.as_posix()}")
    for filename in PROFILE_ARTIFACTS[profile]:
        print(f"- {filename}")
    return []


def print_findings(root: Path, findings: Iterable[Finding]) -> int:
    findings = list(findings)
    if not findings:
        print("SDD validation passed.")
        return 0

    for finding in findings:
        print(finding.format(root))

    has_error = any(finding.severity == "error" for finding in findings)
    return 1 if has_error else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SDD-Core utility")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate_parser = subcommands.add_parser("validate", help="validate SDD-Core repository artifacts")
    validate_parser.add_argument(
        "--root",
        default=".",
        help="repository root to validate; defaults to the current directory",
    )

    subcommands.add_parser("version", help="show SSD-Core version")

    init_parser = subcommands.add_parser("init", help="initialize SDD-Core artifacts in a repository")
    init_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    status_parser = subcommands.add_parser("status", help="show SDD-Core repository status")
    status_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    check_parser = subcommands.add_parser("check", help="check whether an SDD-Core change is ready to archive")
    check_parser.add_argument("change_id", help="kebab-case change identifier")
    check_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    archive_parser = subcommands.add_parser("archive", help="archive a verified SDD-Core change")
    archive_parser.add_argument("change_id", help="kebab-case change identifier")
    archive_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    sync_parser = subcommands.add_parser("sync-specs", help="sync a verified change delta into living specs")
    sync_parser.add_argument("change_id", help="kebab-case change identifier")
    sync_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    new_parser = subcommands.add_parser("new", help="create a new SDD-Core change artifact set")
    new_parser.add_argument("change_id", help="kebab-case change identifier")
    new_parser.add_argument(
        "--profile",
        default="standard",
        choices=REQUIRED_PROFILES,
        help="profile to use for the change; defaults to standard",
    )
    new_parser.add_argument(
        "--title",
        help="human-readable change intent for the proposal",
    )
    new_parser.add_argument(
        "--root",
        default=".",
        help="repository root; defaults to the current directory",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        root = Path(args.root).resolve()
        return print_findings(root, validate(root))

    if args.command == "version":
        print(f"SSD-Core {VERSION}")
        return 0

    if args.command == "init":
        root = Path(args.root).resolve()
        findings = init_project(root)
        if findings:
            return print_findings(root, findings)
        return print_findings(root, validate(root))

    if args.command == "status":
        root = Path(args.root).resolve()
        return print_status(root)

    if args.command == "check":
        root = Path(args.root).resolve()
        return print_check(root, args.change_id)

    if args.command == "archive":
        root = Path(args.root).resolve()
        findings = archive_change(root, args.change_id)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "sync-specs":
        root = Path(args.root).resolve()
        findings = sync_specs(root, args.change_id)
        if findings:
            return print_findings(root, findings)
        return 0

    if args.command == "new":
        root = Path(args.root).resolve()
        findings = create_change(root, args.change_id, args.profile, args.title)
        if findings:
            return print_findings(root, findings)
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
