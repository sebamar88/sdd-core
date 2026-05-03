from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


REQUIRED_DIRECTORIES = [
    ".sdd",
    ".sdd/profiles",
    ".sdd/schemas",
    ".sdd/specs",
    ".sdd/changes",
    ".sdd/archive",
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
    "artifact.schema.json",
    "phase-result.schema.json",
    "verification.schema.json",
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


def logical_path(root: Path, value: str) -> Path:
    return root.joinpath(*value.split("/"))


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

    for profile in REQUIRED_PROFILES:
        path = logical_path(root, f".sdd/profiles/{profile}.md")
        if not path.is_file():
            findings.append(Finding("error", path, "required profile is missing"))

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
