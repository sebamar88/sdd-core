from __future__ import annotations

import hashlib
import json
import re
import shutil
import shlex
import stat
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import ClassVar, Iterable, Protocol

from ._types import (
    VERSION,
    Finding,
    ChangeSummary,
    WorkflowPhase,
    WorkflowFailureKind,
    WorkflowFailure,
    WorkflowState,
    WorkflowResult,
    TemplateResource,
    _PIPELINE_PHASES,
    _use_color,
    _c,
    _green,
    _yellow,
    _red,
    _cyan,
    _bold,
    _dim,
    REQUIRED_DIRECTORIES,
    REQUIRED_ADAPTERS,
    REQUIRED_AGENTS,
    REQUIRED_PROFILES,
    REQUIRED_SCHEMAS,
    REQUIRED_SKILLS,
    PROFILE_ARTIFACTS,
    FOUNDATION_COPY_DIRECTORIES,
    FOUNDATION_COPY_FILES,
    FOUNDATION_DOC_FILES,
    EMPTY_STATE_DIRECTORIES,
    ARTIFACT_STATUSES,
    SCHEMA_PATTERN,
    TOKEN_PATTERN,
    DATE_PATTERN,
    OPEN_TASK_PATTERN,
    MATRIX_PASSING_ROW_PATTERN,
    VERIFICATION_EVIDENCE_BLOCKERS,
    WORKFLOW_STATE_SCHEMA,
    PHASE_ORDER,
    ALLOWED_TRANSITIONS,
    PHASE_NEXT_ACTIONS,
)

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
    for required_file in [".sdd/protocol.md", ".sdd/constitution.md", ".sdd/state.json"]:
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
                findings.append(
                    Finding(
                        "error",
                        path,
                        f"change_id does not match directory name: expected {expected_change_id}",
                    )
                )

            if not profile:
                findings.append(Finding("error", path, "frontmatter missing required key: profile"))

            expected_artifact = path.stem
            if artifact and artifact != expected_artifact:
                findings.append(
                    Finding(
                        "error",
                        path,
                        f"artifact value must match filename stem: expected {expected_artifact}",
                    )
                )

        if is_living_spec:
            change_id = metadata.get("change_id")
            expected_change_id = relative.parts[1]
            if not change_id:
                findings.append(Finding("error", path, "frontmatter missing required key: change_id"))
            elif change_id != expected_change_id:
                findings.append(
                    Finding(
                        "error",
                        path,
                        f"change_id does not match directory name: expected {expected_change_id}",
                    )
                )

            expected_artifact = path.stem
            if path.name == "spec.md":
                expected_artifact = "spec"
            if artifact and artifact != expected_artifact:
                findings.append(
                    Finding(
                        "error",
                        path,
                        f"artifact value must match filename stem: expected {expected_artifact}",
                    )
                )

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


def check_change_artifacts(root: Path, change_dir: Path, change_id: str) -> list[Finding]:
    findings: list[Finding] = []
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

        findings.extend(validate_verification_evidence(verification_path))
        findings.extend(validate_verification_matrix(verification_path))

    return findings


def validate_verification_evidence(verification_path: Path) -> list[Finding]:
    """Check that verification.md contains real evidence, not placeholder text."""
    findings: list[Finding] = []
    if not verification_path.is_file():
        return findings
    text = verification_path.read_text(encoding="utf-8").lower()
    for term in VERIFICATION_EVIDENCE_BLOCKERS:
        if term in text:
            findings.append(Finding("error", verification_path, f"verification still contains placeholder: {term}"))
    return findings


def validate_verification_matrix(verification_path: Path) -> list[Finding]:
    """Semantic check: the verification matrix must contain at least one passing row.

    A passing row has a recognised status value in its last column: pass, verified,
    or complete.  This catches matrices that had placeholder text removed but were
    never updated with real test evidence.
    """
    if not verification_path.is_file():
        return []
    text = verification_path.read_text(encoding="utf-8")
    if MATRIX_PASSING_ROW_PATTERN.search(text):
        return []
    return [
        Finding(
            "error",
            verification_path,
            "verification matrix has no passing rows; at least one row status must be: pass, verified, or complete",
        )
    ]


def check_change(root: Path, change_id: str) -> list[Finding]:
    findings = validate_change_id(change_id)
    if findings:
        return findings
    return check_change_artifacts(root, change_directory(root, change_id), change_id)


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def evidence_directory(root: Path, change_id: str) -> Path:
    return root / ".sdd" / "evidence" / change_id


def execution_evidence_path(root: Path, change_id: str) -> Path:
    return evidence_directory(root, change_id) / "verification.jsonl"


def set_frontmatter_value(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            break
        if line.startswith(f"{key}:"):
            lines[index] = f"{key}: {value}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    return text


def append_execution_evidence_to_verification(root: Path, verification_path: Path, records: list[dict[str, object]]) -> None:
    text = verification_path.read_text(encoding="utf-8")
    text = set_frontmatter_value(text, "status", "verified")
    text = set_frontmatter_value(text, "updated", date.today().isoformat())
    text = text.replace("pending verification evidence", "execution evidence recorded")
    text = text.replace("not-run", "pass")
    text = text.replace("Record host-project verification actions.", "Recorded by `ssd-core verify --command`.")

    lines = ["", "## Execution Evidence", ""]
    for record in records:
        log_path = root / str(record["log_path"])
        try:
            relative_log = log_path.relative_to(root).as_posix()
        except ValueError:
            relative_log = str(record["log_path"])
        dur = record.get("duration_seconds")
        dur_str = f"; duration `{dur}s`" if dur is not None else ""
        chk = str(record.get("output_checksum", ""))[:12]
        lines.append(
            f"- `{record['command']}` exited `{record['exit_code']}`{dur_str}; log `{relative_log}`; sha256 `{chk}...`"
        )

    suffix = "\n" if text.endswith("\n") else "\n\n"
    verification_path.write_text(text + suffix + "\n".join(lines) + "\n", encoding="utf-8")


def append_execution_evidence(
    root: Path,
    change_id: str,
    command: str,
    exit_code: int,
    output: str,
    duration_seconds: float | None = None,
) -> dict[str, object]:
    evidence_id = uuid.uuid4().hex
    evidence_dir = evidence_directory(root, change_id)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    output_checksum = hashlib.sha256(output.encode("utf-8")).hexdigest()
    log_path = evidence_dir / f"{evidence_id}.log"
    log_path.write_text(output, encoding="utf-8")

    record: dict[str, object] = {
        "schema": "sdd.execution-evidence.v1",
        "id": evidence_id,
        "change_id": change_id,
        "phase": WorkflowPhase.VERIFY.value,
        "command": command,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "recorded_at": utc_timestamp(),
        "log_path": log_path.relative_to(root).as_posix(),
        "output_checksum": output_checksum,
    }
    if duration_seconds is not None:
        record["duration_seconds"] = round(duration_seconds, 3)

    evidence_path = execution_evidence_path(root, change_id)
    with evidence_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def run_verification_command(root: Path, change_id: str, command: str, timeout_seconds: int) -> tuple[dict[str, object], Finding | None]:
    t0 = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        duration = time.monotonic() - t0
        output = (
            f"$ {command}\n"
            f"exit_code: {completed.returncode}\n"
            f"duration: {duration:.3f}s\n\n"
            f"--- stdout ---\n{completed.stdout}\n"
            f"--- stderr ---\n{completed.stderr}"
        )
        record = append_execution_evidence(root, change_id, command, completed.returncode, output, duration)
        if completed.returncode != 0:
            return record, Finding("error", evidence_directory(root, change_id), f"verification command failed (exit {completed.returncode}): {command}")
        return record, None
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - t0
        output = (
            f"$ {command}\n"
            f"exit_code: timeout\n"
            f"duration: {duration:.3f}s\n\n"
            f"--- stdout ---\n{(exc.stdout or '').strip()}\n"
            f"--- stderr ---\n{(exc.stderr or '').strip()}"
        )
        record = append_execution_evidence(root, change_id, command, 124, output, duration)
        return record, Finding("error", evidence_directory(root, change_id), f"verification command timed out after {timeout_seconds}s: {command}")


def execution_evidence_records(root: Path, change_id: str) -> tuple[list[dict[str, object]], list[Finding]]:
    path = execution_evidence_path(root, change_id)
    if not path.is_file():
        return [], [Finding("error", path, "execution evidence is missing")]

    records: list[dict[str, object]] = []
    findings: list[Finding] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            findings.append(Finding("error", path, f"invalid execution evidence JSON at line {line_number}: {exc.msg}"))
            continue
        if not isinstance(record, dict):
            findings.append(Finding("error", path, f"execution evidence line {line_number} must be an object"))
            continue
        records.append(record)
    return records, findings


def validate_execution_evidence(root: Path, change_id: str) -> list[Finding]:
    records, findings = execution_evidence_records(root, change_id)
    if findings:
        return findings
    if not any(record.get("passed") is True and record.get("phase") == WorkflowPhase.VERIFY.value for record in records):
        findings.append(Finding("error", execution_evidence_path(root, change_id), "no passing execution evidence is recorded"))
    for record in records:
        log_path_value = record.get("log_path")
        checksum_value = record.get("output_checksum")
        if not isinstance(log_path_value, str) or not isinstance(checksum_value, str):
            findings.append(Finding("error", execution_evidence_path(root, change_id), "execution evidence is missing log_path or output_checksum"))
            continue
        log_path = root / log_path_value
        if not log_path.is_file():
            findings.append(Finding("error", log_path, "execution evidence log is missing"))
            continue
        current_checksum = hashlib.sha256(log_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
        if current_checksum != checksum_value:
            findings.append(Finding("error", log_path, "execution evidence log checksum does not match"))
    return findings


def verify_change(
    root: Path,
    change_id: str,
    commands: list[str] | None = None,
    *,
    require_command: bool = False,
    timeout_seconds: int = 120,
) -> list[Finding]:
    """Explicit governance gate: validate evidence quality and record VERIFY phase.

    Requires that the change has a recorded TASK phase in state.json.  When
    commands are provided, they are executed from the repository root and their
    outputs are captured under .sdd/evidence before the VERIFY phase is recorded.

    Checksum validation is intentionally skipped: editing verification.md after
    recording TASK is the expected workflow for this phase.
    """
    commands = commands or []
    if require_command and not commands:
        return [Finding("error", change_directory(root, change_id), "verify requires at least one --command")]

    required_phase, check_checksum = COMMAND_GATES["verify"]
    findings = gate_command(root, change_id, required_phase, check_checksum=check_checksum)
    if findings:
        return findings

    change_dir = change_directory(root, change_id)
    verification_path = change_dir / "verification.md"
    if not verification_path.is_file():
        return [Finding("error", verification_path, "verification.md is required to run verify")]

    execution_records: list[dict[str, object]] = []
    execution_findings: list[Finding] = []
    for command in commands:
        record, finding = run_verification_command(root, change_id, command, timeout_seconds)
        execution_records.append(record)
        if finding is not None:
            execution_findings.append(finding)

    if execution_records:
        append_execution_evidence_to_verification(root, verification_path, execution_records)
    if execution_findings:
        return execution_findings

    metadata, error = read_frontmatter(verification_path)
    if error is not None:
        return [Finding("error", verification_path, error)]

    if metadata.get("status") != "verified":
        return [Finding("error", verification_path, "verification status must be verified before running verify")]

    evidence_findings = validate_verification_evidence(verification_path)
    if evidence_findings:
        return evidence_findings
    matrix_findings = validate_verification_matrix(verification_path)
    if matrix_findings:
        return matrix_findings
    if commands:
        execution_findings = validate_execution_evidence(root, change_id)
        if execution_findings:
            return execution_findings

    summary = summarize_change(change_dir)
    new_state = WorkflowState(
        change_id,
        WorkflowPhase.VERIFY,
        summary.profile,
        f"Run `ssd-core transition {change_id} archive`.",
        [],
    )
    record_workflow_state(root, new_state, "verify")
    print(_green("\u2714") + f" Verification recorded: {_bold(change_id)}")
    return []


def print_check(root: Path, change_id: str) -> int:
    findings = check_change(root, change_id)
    if not findings:
        print(_green("\u2714") + f" Change {change_id} is ready.")
        return 0

    print(_yellow("\u25ce") + f" Change {change_id} is not ready.")
    for finding in findings:
        pre = _red("\u2717") if finding.severity == "error" else _yellow("\u26a0")
        print(pre + " " + finding.format(root))
    return 1


# ── Test runner discovery ─────────────────────────────────────────────────────

def discover_test_command(root: Path) -> str | None:
    """Auto-discover the project's test runner from common signal files.

    Checks for pytest, npm, cargo, go, and Makefile in that priority order.
    Returns the command string or None when no runner is detected.
    """
    # Python: pytest
    has_pytest_config = (
        (root / "pytest.ini").exists()
        or (root / "setup.cfg").exists()
        or _pyproject_has_pytest(root)
    )
    if has_pytest_config and shutil.which("pytest"):
        return "python -m pytest"
    if has_pytest_config and shutil.which("python"):
        return "python -m pytest"

    # Node.js: npm test
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {}) or {}
            if isinstance(scripts, dict) and "test" in scripts:
                return "npm test"
        except (json.JSONDecodeError, OSError):
            pass

    # Rust: cargo test
    if (root / "Cargo.toml").exists() and shutil.which("cargo"):
        return "cargo test"

    # Go: go test
    if (root / "go.mod").exists() and shutil.which("go"):
        return "go test ./..."

    # Makefile with a test target
    makefile = root / "Makefile"
    if makefile.exists():
        try:
            content = makefile.read_text(encoding="utf-8")
            if re.search(r"^test:", content, re.MULTILINE):
                return "make test"
        except OSError:
            pass

    return None


def _pyproject_has_pytest(root: Path) -> bool:
    """Return True when pyproject.toml declares a [tool.pytest.ini_options] section."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        content = pyproject.read_text(encoding="utf-8")
        return "[tool.pytest" in content or "[tool.setuptools" in content
    except OSError:
        return False


def change_has_delta_spec(change_dir: Path) -> bool:
    return (change_dir / "delta-spec.md").is_file()


def living_spec_path(root: Path, change_id: str) -> Path:
    return root / ".sdd" / "specs" / change_id / "spec.md"


def validate_spec_sync(root: Path, change_dir: Path, change_id: str) -> list[Finding]:
    if change_has_delta_spec(change_dir) and not living_spec_path(root, change_id).is_file():
        return [
            Finding(
                "error",
                living_spec_path(root, change_id),
                "living spec must be synced before archive",
            )
        ]
    return []


def archive_change(root: Path, change_id: str) -> list[Finding]:
    required_phase, check_checksum = COMMAND_GATES["archive"]
    findings = gate_command(root, change_id, required_phase, check_checksum=check_checksum)
    if findings:
        return findings

    findings = check_change(root, change_id)
    if findings:
        return findings

    source = change_directory(root, change_id)
    summary = summarize_change(source)
    spec_findings = validate_spec_sync(root, source, change_id)
    if spec_findings:
        return spec_findings

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
    record_workflow_state(
        root,
        WorkflowState(change_id, WorkflowPhase.ARCHIVED, summary.profile, f"Review archived evidence at {destination.as_posix()}.", []),
        "archive",
    )
    print(_green("\u2714") + f" Archived change: {_bold(destination.relative_to(root).as_posix())}")
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
    required_phase, check_checksum = COMMAND_GATES["sync-specs"]
    findings = gate_command(root, change_id, required_phase, check_checksum=check_checksum)
    if findings:
        return findings

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

    record_workflow_state(root, _infer_workflow_state(root, change_id), "sync-specs")
    print(_green("\u2714") + f" Synced living spec: {_bold(spec_path.relative_to(root).as_posix())}")
    return []


def archived_change_directory(root: Path, change_id: str) -> Path | None:
    archive_root = root / ".sdd" / "archive"
    if not archive_root.is_dir():
        return None
    matches = sorted(path for path in archive_root.glob(f"*-{change_id}") if path.is_dir())
    return matches[-1] if matches else None


def archived_change_id(archive_dir: Path) -> str:
    match = re.match(r"^\d{4}-\d{2}-\d{2}-(?P<change_id>[a-z0-9][a-z0-9-]*)$", archive_dir.name)
    if match:
        return match.group("change_id")
    return archive_dir.name


def workflow_registry_path(root: Path) -> Path:
    return root / ".sdd" / "state.json"


def empty_workflow_registry() -> dict[str, object]:
    return {
        "schema": WORKFLOW_STATE_SCHEMA,
        "updated": date.today().isoformat(),
        "changes": {},
    }


def read_workflow_registry(root: Path) -> tuple[dict[str, object], list[Finding]]:
    path = workflow_registry_path(root)
    if not path.is_file():
        return empty_workflow_registry(), [Finding("error", path, "workflow state registry is missing")]

    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return empty_workflow_registry(), [Finding("error", path, f"invalid workflow state JSON: {exc.msg} at line {exc.lineno}")]

    if not isinstance(registry, dict):
        return empty_workflow_registry(), [Finding("error", path, "workflow state registry must be a JSON object")]
    if registry.get("schema") != WORKFLOW_STATE_SCHEMA:
        return registry, [Finding("error", path, f"workflow state schema must be {WORKFLOW_STATE_SCHEMA}")]
    if not isinstance(registry.get("changes"), dict):
        return registry, [Finding("error", path, "workflow state changes must be a JSON object")]
    return registry, []


def write_workflow_registry(root: Path, registry: dict[str, object]) -> None:
    path = workflow_registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    registry["schema"] = WORKFLOW_STATE_SCHEMA
    registry["updated"] = date.today().isoformat()
    if not isinstance(registry.get("changes"), dict):
        registry["changes"] = {}
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def change_location(root: Path, change_id: str) -> Path | None:
    active_dir = change_directory(root, change_id)
    if active_dir.is_dir():
        return active_dir
    return archived_change_directory(root, change_id)


def artifact_checksum(change_dir: Path) -> str:
    digest = hashlib.sha256()
    if not change_dir.is_dir():
        return ""
    for path in sorted(path for path in change_dir.rglob("*") if path.is_file()):
        relative = path.relative_to(change_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def registry_changes(registry: dict[str, object]) -> dict[str, object]:
    changes = registry.get("changes")
    if isinstance(changes, dict):
        return changes
    registry["changes"] = {}
    return registry["changes"]  # type: ignore[return-value]


def state_entry(registry: dict[str, object], change_id: str) -> dict[str, object] | None:
    entry = registry_changes(registry).get(change_id)
    return entry if isinstance(entry, dict) else None


def record_workflow_state(root: Path, state: WorkflowState, action: str) -> None:
    if state.phase in {WorkflowPhase.NOT_STARTED, WorkflowPhase.BLOCKED}:
        return

    registry, _ = read_workflow_registry(root)
    changes = registry_changes(registry)
    existing = state_entry(registry, state.change_id) or {}
    history = existing.get("history")
    if not isinstance(history, list):
        history = []

    today = date.today().isoformat()
    location = change_location(root, state.change_id)
    checksum = artifact_checksum(location) if location is not None else ""
    history.append(
        {
            "phase": state.phase.value,
            "action": action,
            "at": today,
            "checksum": checksum,
        }
    )
    changes[state.change_id] = {
        "phase": state.phase.value,
        "profile": state.profile,
        "updated": today,
        "checksum": checksum,
        "history": history[-25:],
    }
    write_workflow_registry(root, registry)


def declared_workflow_phase(root: Path, change_id: str) -> WorkflowPhase | None:
    registry, findings = read_workflow_registry(root)
    if findings:
        return None
    entry = state_entry(registry, change_id)
    if entry is None:
        return None
    phase = entry.get("phase")
    try:
        return WorkflowPhase(str(phase))
    except ValueError:
        return None


def phase_is_supported(target: WorkflowPhase, inferred: WorkflowPhase) -> bool:
    return PHASE_ORDER[target] <= PHASE_ORDER[inferred]


# Phases that have a dedicated command and MUST NOT be reached via `transition`.
# Using the dedicated command enforces quality checks that `transition` skips.
TRANSITION_RESTRICTED_PHASES = {
    WorkflowPhase.VERIFY,    # use: ssd-core verify
    WorkflowPhase.ARCHIVED,  # use: ssd-core archive
    WorkflowPhase.NOT_STARTED,
    WorkflowPhase.BLOCKED,
}

# Maps CLI command name to (required_recorded_phase, check_checksum_integrity).
# This is the single authority for which phase a command requires and whether
# it validates artifact integrity before executing.  WorkflowEngine reads it
# directly.  Adding a new gated command means adding one entry here.
COMMAND_GATES: dict[str, tuple[WorkflowPhase, bool]] = {
    "verify":     (WorkflowPhase.TASK,       False),
    "sync-specs": (WorkflowPhase.SYNC_SPECS, True),
    "archive":    (WorkflowPhase.ARCHIVE,    True),
}

# Maps human-work phases to the artifact file that needs editing.
# Used by `ssd-core auto` to tell the user exactly which file to open.
_PHASE_ARTIFACT_FILE: dict[WorkflowPhase, str] = {
    WorkflowPhase.PROPOSE:        "proposal.md",
    WorkflowPhase.SPECIFY:        "delta-spec.md",
    WorkflowPhase.DESIGN:         "design.md",
    WorkflowPhase.TASK:           "tasks.md",
    WorkflowPhase.CRITIQUE:       "critique.md",
    WorkflowPhase.ARCHIVE_RECORD: "archive.md",
}


def transition_workflow(root: Path, change_id: str, target_phase: WorkflowPhase) -> WorkflowState:
    findings = validate_change_id(change_id)
    if findings:
        return WorkflowState(change_id, WorkflowPhase.BLOCKED, "unknown", "Use a kebab-case change id.", findings)
    if target_phase in TRANSITION_RESTRICTED_PHASES:
        if target_phase == WorkflowPhase.VERIFY:
            message = f"use `ssd-core verify {change_id}` to record the verify phase; it enforces evidence quality before recording"
        elif target_phase == WorkflowPhase.ARCHIVED:
            message = f"use `ssd-core archive {change_id}` to archive a change"
        else:
            message = f"cannot transition to {target_phase.value}"
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            "unknown",
            "Choose an active workflow phase.",
            [Finding("error", None, message)],
        )

    state = workflow_state(root, change_id)
    if state.is_blocked:
        return state

    # current is the declared phase when recorded (state.json-primary), otherwise artifact-inferred.
    current = state.phase

    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target_phase not in allowed:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            state.profile,
            state.next_action,
            [
                Finding(
                    "error",
                    change_location(root, change_id),
                    f"invalid workflow transition: {current.value} -> {target_phase.value}",
                )
            ],
        )

    # Readiness check: artifacts must actually support the target phase regardless of what is declared.
    artifact_phase = infer_phase_from_artifacts(root, change_id)
    if not phase_is_supported(target_phase, artifact_phase):
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            state.profile,
            state.next_action,
            [
                Finding(
                    "error",
                    change_location(root, change_id),
                    f"artifacts do not support transition to {target_phase.value}; artifact phase is {artifact_phase.value}",
                )
            ],
        )

    transitioned = WorkflowState(change_id, target_phase, state.profile, state.next_action, [])
    record_workflow_state(root, transitioned, "transition")
    return transitioned


def require_recorded_phase(root: Path, change_id: str, expected: WorkflowPhase) -> list[Finding]:
    findings = validate_change_id(change_id)
    if findings:
        return findings

    registry, findings = read_workflow_registry(root)
    if findings:
        return findings

    entry = state_entry(registry, change_id)
    if entry is None:
        return [
            Finding(
                "error",
                change_location(root, change_id) or workflow_registry_path(root),
                f"workflow phase must be recorded before running this command; run `ssd-core transition {change_id} {expected.value}`",
            )
        ]

    try:
        declared = WorkflowPhase(str(entry.get("phase")))
    except ValueError:
        return [Finding("error", workflow_registry_path(root), f"workflow state phase is invalid for {change_id}: {entry.get('phase')}")]

    if declared != expected:
        return [
            Finding(
                "error",
                change_location(root, change_id) or workflow_registry_path(root),
                f"workflow phase must be {expected.value}; recorded phase is {declared.value}",
            )
        ]
    return []


def gate_command(
    root: Path,
    change_id: str,
    required_phase: WorkflowPhase,
    *,
    check_checksum: bool = False,
) -> list[Finding]:
    """Central command gate used by all destructive workflow commands.

    Calls ``require_recorded_phase`` to assert the correct phase is declared in
    ``state.json``, then (when ``check_checksum=True``) compares the stored
    artifact checksum against the current on-disk state.  A mismatch means
    artifacts were silently mutated after the last explicit transition and the
    command is blocked until the transition is re-recorded.

    Set ``check_checksum=False`` for commands where artifact changes are
    *expected* between the preceding phase and the command invocation — e.g.
    ``verify``, where editing ``verification.md`` after recording TASK is the
    whole point of that phase.
    """
    findings = require_recorded_phase(root, change_id, required_phase)
    if findings or not check_checksum:
        return findings

    registry, reg_findings = read_workflow_registry(root)
    if reg_findings:
        return reg_findings

    entry = state_entry(registry, change_id)
    if entry is None:
        return []

    stored = str(entry.get("checksum", ""))
    if not stored:
        return []

    location = change_location(root, change_id)
    current = artifact_checksum(location) if location is not None else ""
    if current != stored:
        return [
            Finding(
                "error",
                location or workflow_registry_path(root),
                f"artifact checksum is stale since {required_phase.value} was recorded; "
                f"run `ssd-core transition {change_id} {required_phase.value}` to acknowledge changes before proceeding",
            )
        ]
    return []


def validate_workflow_registry(root: Path, *, strict_state: bool = False) -> list[Finding]:
    registry, findings = read_workflow_registry(root)
    if findings:
        return findings

    changes = registry_changes(registry)
    for change_id, raw_entry in changes.items():
        path = workflow_registry_path(root)
        if not isinstance(change_id, str) or validate_change_id(change_id):
            findings.append(Finding("error", path, f"workflow state change id is invalid: {change_id}"))
            continue
        if not isinstance(raw_entry, dict):
            findings.append(Finding("error", path, f"workflow state entry must be an object: {change_id}"))
            continue

        raw_phase = raw_entry.get("phase")
        try:
            declared = WorkflowPhase(str(raw_phase))
        except ValueError:
            findings.append(Finding("error", path, f"workflow state phase is invalid for {change_id}: {raw_phase}"))
            continue

        artifact_state = _infer_workflow_state(root, change_id)
        if artifact_state.phase == WorkflowPhase.NOT_STARTED:
            findings.append(Finding("error", path, f"workflow state references missing change: {change_id}"))
            continue
        if artifact_state.is_blocked:
            findings.extend(artifact_state.findings)
            continue
        if PHASE_ORDER[declared] > PHASE_ORDER[artifact_state.phase]:
            findings.append(
                Finding(
                    "error",
                    change_location(root, change_id),
                    f"declared phase {declared.value} is ahead of artifact phase {artifact_state.phase.value}",
                )
            )

        if strict_state:
            location = change_location(root, change_id)
            current_checksum = artifact_checksum(location) if location is not None else ""
            if raw_entry.get("checksum") != current_checksum:
                findings.append(
                    Finding(
                        "error",
                        location or path,
                        f"workflow state checksum is stale for {change_id}; run `ssd-core transition {change_id} <phase>` after intentional artifact changes",
                    )
                )

    if strict_state:
        tracked_changes = {str(change_id) for change_id in changes}
        for change_dir in active_change_directories(root):
            if change_dir.name not in tracked_changes:
                findings.append(
                    Finding(
                        "error",
                        change_dir,
                        f"active change is not recorded in .sdd/state.json: {change_dir.name}",
                    )
                )

    return findings


def artifact_status(change_dir: Path, filename: str) -> tuple[str, Finding | None]:
    path = change_dir / filename
    metadata, error = read_frontmatter(path)
    if error is not None:
        return "invalid-frontmatter", Finding("error", path, error)
    return metadata.get("status", "unknown"), None


def _infer_workflow_state(root: Path, change_id: str) -> WorkflowState:
    """Return workflow state inferred purely from artifact content, ignoring state.json.

    Private implementation consumed by ``workflow_state`` (as the state.json-less
    fallback), ``infer_phase_from_artifacts``, ``transition_workflow`` (readiness
    check), ``validate_workflow_registry`` (consistency cross-check), and
    ``sync_specs`` (post-sync phase advancement).
    """
    findings = validate_change_id(change_id)
    if findings:
        return WorkflowState(change_id, WorkflowPhase.BLOCKED, "unknown", "Use a kebab-case change id.", findings)

    archived_dir = archived_change_directory(root, change_id)
    if archived_dir is not None:
        return WorkflowState(
            change_id,
            WorkflowPhase.ARCHIVED,
            "archived",
            f"Review archived evidence at {archived_dir.relative_to(root).as_posix()}.",
            [],
        )

    change_dir = change_directory(root, change_id)
    if not change_dir.is_dir():
        return WorkflowState(
            change_id,
            WorkflowPhase.NOT_STARTED,
            "unknown",
            "Create the governed change artifacts.",
            [],
        )

    summary = summarize_change(change_dir)
    if summary.profile == "unknown":
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Fix change artifact frontmatter so the profile can be detected.",
            [Finding("error", change_dir, "could not detect profile")],
        )

    structural_findings: list[Finding] = []
    for filename in summary.missing:
        structural_findings.append(Finding("error", change_dir / filename, "required profile artifact is missing"))
    for filename in summary.present:
        status_value, status_finding = artifact_status(change_dir, filename)
        if status_finding is not None:
            structural_findings.append(status_finding)
        elif status_value == "blocked":
            structural_findings.append(Finding("error", change_dir / filename, "artifact status is blocked"))
    if structural_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Resolve blocking artifact findings before continuing.",
            structural_findings,
        )

    phase_artifacts = [
        ("proposal.md", WorkflowPhase.PROPOSE, "Complete proposal.md and set status to ready."),
        ("delta-spec.md", WorkflowPhase.SPECIFY, "Complete delta-spec.md and set status to ready."),
        ("design.md", WorkflowPhase.DESIGN, "Complete design.md and set status to ready."),
        ("tasks.md", WorkflowPhase.TASK, "Complete tasks.md, close all task checkboxes, and set status to ready."),
        ("verification.md", WorkflowPhase.VERIFY, "Record passing evidence in verification.md and set status to verified."),
        ("critique.md", WorkflowPhase.CRITIQUE, "Resolve critique.md and set status to ready or verified."),
        ("archive.md", WorkflowPhase.ARCHIVE_RECORD, "Complete archive.md and set status to ready."),
    ]

    for filename, phase, next_action in phase_artifacts:
        if filename not in summary.present:
            continue
        path = change_dir / filename
        status_value, _ = artifact_status(change_dir, filename)
        if filename == "tasks.md" and OPEN_TASK_PATTERN.search(path.read_text(encoding="utf-8")):
            return WorkflowState(change_id, phase, summary.profile, next_action, [])
        if filename == "verification.md":
            verification_text = path.read_text(encoding="utf-8").lower()
            if status_value != "verified" or "not-run" in verification_text or "pending verification evidence" in verification_text:
                return WorkflowState(change_id, phase, summary.profile, next_action, [])
            continue
        if filename == "critique.md":
            if status_value not in {"ready", "verified"}:
                return WorkflowState(change_id, phase, summary.profile, next_action, [])
            continue
        if status_value != "ready":
            return WorkflowState(change_id, phase, summary.profile, next_action, [])

    readiness_findings = check_change(root, change_id)
    if readiness_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Resolve readiness findings before syncing specs or archiving.",
            readiness_findings,
        )

    spec_path = root / ".sdd" / "specs" / change_id / "spec.md"
    if "delta-spec.md" in summary.present and not spec_path.is_file():
        return WorkflowState(
            change_id,
            WorkflowPhase.SYNC_SPECS,
            summary.profile,
            f"Run `ssd-core sync-specs {change_id} --root <repo>`.",
            [],
        )

    return WorkflowState(
        change_id,
        WorkflowPhase.ARCHIVE,
        summary.profile,
        f"Run `ssd-core archive {change_id} --root <repo>`.",
        [],
    )


def workflow_state(root: Path, change_id: str) -> WorkflowState:
    """Return the current workflow state.

    ``state.json`` is the authoritative phase source when a phase has been
    recorded for this change.  Structural blockers (missing artifacts, blocked
    statuses) still gate execution regardless of the declared phase.  For
    changes with no recorded phase the function falls back to pure artifact
    inference via ``_infer_workflow_state``.
    """
    findings = validate_change_id(change_id)
    if findings:
        return WorkflowState(change_id, WorkflowPhase.BLOCKED, "unknown", "Use a kebab-case change id.", findings)

    archived_dir = archived_change_directory(root, change_id)
    if archived_dir is not None:
        return WorkflowState(
            change_id,
            WorkflowPhase.ARCHIVED,
            "archived",
            f"Review archived evidence at {archived_dir.relative_to(root).as_posix()}.",
            [],
        )

    change_dir = change_directory(root, change_id)
    if not change_dir.is_dir():
        return WorkflowState(
            change_id, WorkflowPhase.NOT_STARTED, "unknown", "Create the governed change artifacts.", []
        )

    summary = summarize_change(change_dir)
    if summary.profile == "unknown":
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Fix change artifact frontmatter so the profile can be detected.",
            [Finding("error", change_dir, "could not detect profile")],
        )

    structural_findings: list[Finding] = []
    for filename in summary.missing:
        structural_findings.append(Finding("error", change_dir / filename, "required profile artifact is missing"))
    for filename in summary.present:
        status_value, status_finding = artifact_status(change_dir, filename)
        if status_finding is not None:
            structural_findings.append(status_finding)
        elif status_value == "blocked":
            structural_findings.append(Finding("error", change_dir / filename, "artifact status is blocked"))
    if structural_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            summary.profile,
            "Resolve blocking artifact findings before continuing.",
            structural_findings,
        )

    # state.json is authoritative when a phase has been recorded.
    declared = declared_workflow_phase(root, change_id)
    if declared is not None:
        next_action = PHASE_NEXT_ACTIONS.get(declared, f"Continue {declared.value} phase.")
        return WorkflowState(change_id, declared, summary.profile, next_action, [])

    # No recorded phase — fall back to artifact inference.
    return _infer_workflow_state(root, change_id)


def infer_phase_from_artifacts(root: Path, change_id: str) -> WorkflowPhase:
    """Return the phase implied by artifact state alone, ignoring state.json.

    Use this when you need to know what artifacts actually support,
    independent of what has been declared in ``state.json``.  Consumed by
    ``transition_workflow`` for artifact readiness checks and by
    ``validate_workflow_registry`` for consistency cross-checks.
    """
    return _infer_workflow_state(root, change_id).phase


def infer_state_from_artifacts(root: Path, change_id: str) -> WorkflowState:
    """Return the full WorkflowState inferred from artifact content, ignoring state.json.

    Useful when you need the complete state (phase, next_action, profile, findings)
    as determined by artifacts alone.  ``infer_phase_from_artifacts`` is a
    convenience wrapper around this that returns only the phase.
    """
    return _infer_workflow_state(root, change_id)


def run_workflow(root: Path, change_id: str, profile: str, title: str | None, *, create: bool = True) -> WorkflowState:
    foundation_findings = validate(root)
    foundation_errors = [finding for finding in foundation_findings if finding.severity == "error"]
    if foundation_errors:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            profile,
            "Initialize or repair the SSD-Core foundation before running a workflow.",
            foundation_errors,
        )

    state = workflow_state(root, change_id)
    if state.phase != WorkflowPhase.NOT_STARTED or not create:
        record_workflow_state(root, state, "run")
        return state

    create_findings = create_change(root, change_id, profile, title)
    if create_findings:
        return WorkflowState(
            change_id,
            WorkflowPhase.BLOCKED,
            profile,
            "Fix change creation findings before continuing.",
            create_findings,
        )
    state = workflow_state(root, change_id)
    record_workflow_state(root, state, "run")
    return state


class SDDWorkflow:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def state(self, change_id: str) -> WorkflowState:
        return workflow_state(self.root, change_id)

    def run(
        self,
        change_id: str,
        *,
        profile: str = "standard",
        title: str | None = None,
        create: bool = True,
    ) -> WorkflowResult:
        state = run_workflow(self.root, change_id, profile, title, create=create)
        failures = [
            WorkflowFailure.from_finding(WorkflowFailureKind.VALIDATION, finding)
            for finding in state.findings
            if state.is_blocked
        ]
        return WorkflowResult(state, failures)

    def require_phase(self, change_id: str, expected: WorkflowPhase, *, check_checksum: bool = False) -> WorkflowResult:
        gate_findings = gate_command(self.root, change_id, expected, check_checksum=check_checksum)
        state = self.state(change_id)
        if gate_findings:
            failure = WorkflowFailure.from_finding(WorkflowFailureKind.PHASE_ORDER, gate_findings[0])
            blocked_state = WorkflowState(
                change_id,
                WorkflowPhase.BLOCKED,
                state.profile,
                state.next_action,
                gate_findings,
            )
            return WorkflowResult(blocked_state, [failure])

        if state.phase != expected:
            failure = WorkflowFailure(
                WorkflowFailureKind.PHASE_ORDER,
                f"workflow phase must be {expected.value}; current phase is {state.phase.value}",
                change_directory(self.root, change_id),
            )
            blocked_state = WorkflowState(
                change_id,
                WorkflowPhase.BLOCKED,
                state.profile,
                state.next_action,
                [failure.to_finding()],
            )
            return WorkflowResult(blocked_state, [failure])
        return WorkflowResult(state, [])

    def transition(self, change_id: str, target_phase: WorkflowPhase | str) -> WorkflowResult:
        try:
            phase = target_phase if isinstance(target_phase, WorkflowPhase) else WorkflowPhase(str(target_phase))
        except ValueError:
            failure = WorkflowFailure(
                WorkflowFailureKind.PHASE_ORDER,
                f"unknown workflow phase: {target_phase}",
                change_directory(self.root, change_id),
            )
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    "unknown",
                    "Choose a valid workflow phase.",
                    [failure.to_finding()],
                ),
                [failure],
            )
        state = transition_workflow(self.root, change_id, phase)
        failures = [
            WorkflowFailure.from_finding(WorkflowFailureKind.PHASE_ORDER, finding)
            for finding in state.findings
            if state.is_blocked
        ]
        return WorkflowResult(state, failures)

    def sync_specs(self, change_id: str) -> WorkflowResult:
        required = self.require_phase(change_id, WorkflowPhase.SYNC_SPECS, check_checksum=True)
        if not required.ok:
            return required

        findings = sync_specs(self.root, change_id)
        if findings:
            failures = [WorkflowFailure.from_finding(WorkflowFailureKind.COMMAND, finding) for finding in findings]
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    required.state.profile,
                    "Resolve sync-specs findings before continuing.",
                    [failure.to_finding() for failure in failures],
                ),
                failures,
            )
        return WorkflowResult(self.state(change_id), [])

    def verify(
        self,
        change_id: str,
        commands: list[str] | None = None,
        *,
        require_command: bool = False,
        timeout_seconds: int = 120,
    ) -> WorkflowResult:
        required = self.require_phase(change_id, WorkflowPhase.TASK, check_checksum=False)
        if not required.ok:
            return required

        findings = verify_change(
            self.root,
            change_id,
            commands,
            require_command=require_command,
            timeout_seconds=timeout_seconds,
        )
        if findings:
            failures = [WorkflowFailure.from_finding(WorkflowFailureKind.COMMAND, finding) for finding in findings]
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    required.state.profile,
                    "Resolve verification findings before continuing.",
                    [failure.to_finding() for failure in failures],
                ),
                failures,
            )
        return WorkflowResult(self.state(change_id), [])

    def archive(self, change_id: str) -> WorkflowResult:
        required = self.require_phase(change_id, WorkflowPhase.ARCHIVE, check_checksum=True)
        if not required.ok:
            return required

        findings = archive_change(self.root, change_id)
        if findings:
            failures = [WorkflowFailure.from_finding(WorkflowFailureKind.COMMAND, finding) for finding in findings]
            return WorkflowResult(
                WorkflowState(
                    change_id,
                    WorkflowPhase.BLOCKED,
                    required.state.profile,
                    "Resolve archive findings before continuing.",
                    [failure.to_finding() for failure in failures],
                ),
                failures,
            )
        return WorkflowResult(self.state(change_id), [])


def _suggested_command(phase: WorkflowPhase, change_id: str) -> str | None:
    """Return the canonical CLI command that advances *change_id* past *phase*.

    Returns None for terminal or blocked phases where no single command applies.
    """
    mapping: dict[WorkflowPhase, str | None] = {
        WorkflowPhase.NOT_STARTED:    f"ssd-core new {change_id} --profile <profile> --title '<intent>'",
        WorkflowPhase.PROPOSE:        f"ssd-core transition {change_id} propose",
        WorkflowPhase.SPECIFY:        f"ssd-core transition {change_id} specify",
        WorkflowPhase.DESIGN:         f"ssd-core transition {change_id} design",
        WorkflowPhase.TASK:           f"ssd-core transition {change_id} task",
        WorkflowPhase.VERIFY:         f"ssd-core verify {change_id} --command '<test-command>'",
        WorkflowPhase.CRITIQUE:       f"ssd-core transition {change_id} archive-record",
        WorkflowPhase.ARCHIVE_RECORD: f"ssd-core transition {change_id} sync-specs",
        WorkflowPhase.SYNC_SPECS:     f"ssd-core sync-specs {change_id}",
        WorkflowPhase.ARCHIVE:        f"ssd-core archive {change_id}",
        WorkflowPhase.ARCHIVED:       None,
        WorkflowPhase.BLOCKED:        None,
    }
    return mapping.get(phase)


@dataclass(frozen=True)
class EngineStep:
    """Structured description of the current workflow position, designed for agent consumption.

    A single call to ``WorkflowEngine.next_step()`` gives an agent or IDE tool
    everything it needs to advance the workflow without additional lookups:

    - ``phase`` — where the change is now
    - ``next_action`` — human-readable instruction for the *current* phase
    - ``suggested_command`` — the CLI call that records completion of this phase
    - ``allowed_commands`` — gated commands (verify / sync-specs / archive) that
      would pass their gate right now; empty when none apply
    - ``blocking_findings`` — non-empty only when the workflow is blocked

    Usage::

        engine = WorkflowEngine("my-repo")
        step = engine.next_step("harden-login-rate-limit")
        if step.is_blocked:
            for f in step.blocking_findings:
                print(f.message)
        else:
            agent_do_work(step.next_action)
            # then run step.suggested_command
    """

    change_id: str
    phase: WorkflowPhase
    next_action: str
    suggested_command: str | None
    allowed_commands: list[str]
    blocking_findings: list[Finding]

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocking_findings)

    @property
    def is_complete(self) -> bool:
        return self.phase == WorkflowPhase.ARCHIVED


@dataclass(frozen=True)
class AutoStep:
    """Return type for ``WorkflowEngine.execute_next()`` and ``ssd-core auto``.

    A single call to ``execute_next()`` either advances the workflow one step
    (recording a transition, running sync-specs, or archiving) or returns
    guidance on the human work that must happen first.

    - ``executed_command`` — the command that was run; ``None`` when human work
      is needed or the workflow is already complete / blocked
    - ``step`` — the current ``EngineStep`` reflecting state *after* any
      execution; inspect ``step.phase``, ``step.next_action``, and
      ``step.blocking_findings`` for context

    Properties:

    - ``is_blocked`` — workflow is blocked; see ``step.blocking_findings``
    - ``is_complete`` — change is archived; nothing left to do
    - ``needs_human_work`` — engine ran what it could; a file edit is required
      before the next ``execute_next()`` call can advance further
    """

    executed_command: str | None
    step: EngineStep

    @property
    def is_blocked(self) -> bool:
        return self.step.is_blocked

    @property
    def is_complete(self) -> bool:
        return self.step.is_complete

    @property
    def needs_human_work(self) -> bool:
        return not self.is_blocked and not self.is_complete and self.executed_command is None


class WorkflowEngine:
    """Declarative workflow engine.

    ``COMMAND_GATES`` is the single definition of which phase each gated command
    requires and whether it enforces artifact checksum integrity before executing.
    Changing an entry here propagates to every command that calls ``guard()``.

    Intended use by external tooling and CI:

        engine = WorkflowEngine("/path/to/repo")
        findings = engine.guard("my-change", "archive")
        if findings:
            ...blocked...

    Intended use for agent-driven loops:

        step = engine.next_step("my-change")
        while not step.is_complete and not step.is_blocked:
            agent_do_work(step.next_action)
            # run step.suggested_command, then:
            step = engine.next_step("my-change")
    """

    COMMAND_GATES: ClassVar[dict[str, tuple[WorkflowPhase, bool]]] = COMMAND_GATES

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()

    def guard(self, change_id: str, command: str) -> list[Finding]:
        """Return block findings for *command* against *change_id*, or [] if the gate passes."""
        if command not in self.COMMAND_GATES:
            return [Finding("error", None, f"no gate registered for command: {command}")]
        required_phase, check_checksum = self.COMMAND_GATES[command]
        return gate_command(self.root, change_id, required_phase, check_checksum=check_checksum)

    def allowed_commands(self, change_id: str) -> list[str]:
        """Return the names of gated commands that would pass the gate right now for *change_id*."""
        return sorted(
            command
            for command, (phase, checksum) in self.COMMAND_GATES.items()
            if not gate_command(self.root, change_id, phase, check_checksum=checksum)
        )

    def next_step(self, change_id: str) -> "EngineStep":
        """Return a structured description of the current workflow position.

        A single call gives an agent or IDE integration everything it needs:
        the current phase, a human-readable next action, the CLI command that
        advances the workflow, the gated commands that pass right now, and any
        blocking findings.  Designed for agent-driven execution loops::

            step = engine.next_step("my-change")
            while not step.is_complete and not step.is_blocked:
                agent_do_work(step.next_action)
                run_command(step.suggested_command)
                step = engine.next_step("my-change")
        """
        state = workflow_state(self.root, change_id)
        return EngineStep(
            change_id=change_id,
            phase=state.phase,
            next_action=state.next_action,
            suggested_command=_suggested_command(state.phase, change_id),
            allowed_commands=self.allowed_commands(change_id),
            blocking_findings=list(state.findings),
        )

    def execute(
        self,
        change_id: str,
        command: str,
        *,
        verification_commands: list[str] | None = None,
        require_command: bool = False,
        timeout_seconds: int = 120,
    ) -> list[Finding]:
        """Execute a gated workflow command after checking its declared phase."""
        findings = self.guard(change_id, command)
        if findings:
            return findings
        if command == "verify":
            return verify_change(
                self.root,
                change_id,
                verification_commands,
                require_command=require_command,
                timeout_seconds=timeout_seconds,
            )
        if command == "sync-specs":
            return sync_specs(self.root, change_id)
        if command == "archive":
            return archive_change(self.root, change_id)
        return [Finding("error", None, f"no executor registered for command: {command}")]

    def execute_next(self, change_id: str) -> "AutoStep":
        """Advance the workflow one step automatically.

        Executes the next engine-driveable action (a phase transition,
        ``sync-specs``, or ``archive``) when artifacts are ready.  For phases
        that require human file edits (proposal, delta-spec, tasks, etc.), no
        command is executed — the returned ``AutoStep.needs_human_work`` is
        ``True`` and ``AutoStep.step.next_action`` describes what to do.

        Designed for agent-driven loops::

            step = engine.execute_next("my-change")
            while not step.is_complete and not step.is_blocked:
                if step.needs_human_work:
                    agent_edit_file(step.step.next_action)
                step = engine.execute_next("my-change")
        """
        return _auto_advance(self.root, change_id)


def guard_repository(
    root: Path,
    *,
    require_active_change: bool = False,
    strict_state: bool = False,
    require_execution_evidence: bool = False,
) -> list[Finding]:
    findings = [finding for finding in validate(root) if finding.severity == "error"]
    if findings:
        return findings

    findings.extend(validate_workflow_registry(root, strict_state=strict_state))

    active_changes = active_change_directories(root)
    if require_active_change and not active_changes:
        findings.append(
            Finding(
                "error",
                root / ".sdd" / "changes",
                "active SDD change is required by guard policy",
            )
        )

    for change_dir in active_changes:
        state = workflow_state(root, change_dir.name)
        if state.is_blocked:
            findings.extend(state.findings)
        if require_execution_evidence and PHASE_ORDER[state.phase] >= PHASE_ORDER[WorkflowPhase.VERIFY]:
            findings.extend(validate_execution_evidence(root, change_dir.name))

    archive_root = root / ".sdd" / "archive"
    if archive_root.is_dir():
        for archive_dir in sorted(path for path in archive_root.iterdir() if path.is_dir()):
            change_id = archived_change_id(archive_dir)
            findings.extend(check_change_artifacts(root, archive_dir, change_id))
            findings.extend(validate_spec_sync(root, archive_dir, change_id))
            if require_execution_evidence:
                findings.extend(validate_execution_evidence(root, change_id))

    return findings



def _auto_advance(root: Path, change_id: str) -> "AutoStep":
    """Advance the workflow one step automatically.

    Executes exactly one engine-driveable action when artifacts are ready:
    - A phase transition (when the declared phase is behind the artifact phase).
    - ``sync-specs`` when the change is at ``SYNC_SPECS``.
    - ``archive`` when the change is at ``ARCHIVE``.

    For phases that require human file edits, no command is executed and the
    returned ``AutoStep.needs_human_work`` is ``True``.

    This function is called by ``WorkflowEngine.execute_next()`` and
    ``ssd-core auto``.  It intentionally does ONE thing per call and returns;
    callers re-invoke to continue advancing.
    """
    engine = WorkflowEngine(root)

    def current_step() -> "EngineStep":
        return engine.next_step(change_id)

    state = workflow_state(root, change_id)

    # Terminal and gate states — nothing to execute.
    if state.is_blocked or state.phase == WorkflowPhase.ARCHIVED or state.phase == WorkflowPhase.NOT_STARTED:
        return AutoStep(executed_command=None, step=current_step())

    # Direct execute: SYNC_SPECS.
    if state.phase == WorkflowPhase.SYNC_SPECS:
        findings = sync_specs(root, change_id)
        cmd = f"sync-specs {change_id}"
        return AutoStep(executed_command=None if findings else cmd, step=current_step())

    # Direct execute: ARCHIVE.
    if state.phase == WorkflowPhase.ARCHIVE:
        findings = archive_change(root, change_id)
        cmd = f"archive {change_id}"
        return AutoStep(executed_command=None if findings else cmd, step=current_step())

    # Catch-up: artifact phase is ahead of the declared state.json phase.
    artifact_phase = infer_phase_from_artifacts(root, change_id)
    if PHASE_ORDER.get(artifact_phase, 0) > PHASE_ORDER.get(state.phase, 0):
        # Find the best (highest-order) transition reachable from the current
        # declared phase that is still within what artifacts support and is not
        # restricted to a dedicated command.
        eligible = ALLOWED_TRANSITIONS.get(state.phase, set()) - TRANSITION_RESTRICTED_PHASES
        target = max(
            (t for t in eligible if PHASE_ORDER.get(t, 0) <= PHASE_ORDER.get(artifact_phase, 0)),
            key=lambda t: PHASE_ORDER.get(t, 0),
            default=None,
        )
        if target is not None:
            if target == WorkflowPhase.SYNC_SPECS or target == WorkflowPhase.ARCHIVE:
                # Record the phase transition first; the next execute_next / auto call
                # enters the direct-execute path above which then runs sync_specs /
                # archive_change with the correct declared phase in state.json.
                new_state = transition_workflow(root, change_id, target)
                if new_state.is_blocked:
                    return AutoStep(executed_command=None, step=current_step())
                return AutoStep(executed_command=f"transition {change_id} {target.value}", step=current_step())
            new_state = transition_workflow(root, change_id, target)
            if new_state.is_blocked:
                return AutoStep(executed_command=None, step=current_step())
            return AutoStep(executed_command=f"transition {change_id} {target.value}", step=current_step())

    # Human work needed — return guidance via the current EngineStep.
    return AutoStep(executed_command=None, step=current_step())



def pre_commit_hook_text(root: Path) -> str:
    root_arg = root.as_posix()
    command = f"ssd-core guard --root {shlex.quote(root_arg)} --require-active-change --strict-state"
    return "\n".join(
        [
            "#!/bin/sh",
            "# Generated by SSD-Core. Edit with care.",
            command,
            "",
        ]
    )


def pre_push_hook_text(root: Path) -> str:
    root_arg = root.as_posix()
    command = f"ssd-core guard --root {shlex.quote(root_arg)} --strict-state"
    return "\n".join(
        [
            "#!/bin/sh",
            "# Generated by SSD-Core. Edit with care.",
            command,
            "",
        ]
    )


def install_hooks(root: Path) -> list[Finding]:
    git_dir = root / ".git"
    if not git_dir.is_dir():
        return [Finding("error", git_dir, "git repository is required to install hooks")]

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    pre_commit = hooks_dir / "pre-commit"
    pre_commit.write_text(pre_commit_hook_text(root), encoding="utf-8")
    try:
        pre_commit.chmod(0o755)
    except OSError:
        pass
    print(f"Installed SSD-Core pre-commit hook: {pre_commit.as_posix()}")

    pre_push = hooks_dir / "pre-push"
    pre_push.write_text(pre_push_hook_text(root), encoding="utf-8")
    try:
        pre_push.chmod(0o755)
    except OSError:
        pass
    print(f"Installed SSD-Core pre-push hook: {pre_push.as_posix()}")

    return []


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

    record_workflow_state(root, workflow_state(root, change_id), "new")
    print(_green("\u2714") + f" Created change: {_bold(change_dir.relative_to(root).as_posix())}")
    for filename in PROFILE_ARTIFACTS[profile]:
        print("  " + _dim("-") + f" {filename}")
    return []


# \u2500\u2500 CI template ──────────────────────────────────────────────────────────────

_GITHUB_ACTIONS_TEMPLATE = """\
name: SDD Governance Guard

on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]

jobs:
  sdd-guard:
    name: SDD governance check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install SDD-Core
        run: pip install ssd-core

      - name: SDD governance guard
        run: ssd-core guard --root . --strict-state

      # Uncomment to require passing execution evidence for verified changes:
      # - name: SDD evidence guard
      #   run: ssd-core guard --root . --strict-state --require-execution-evidence
"""

_GITLAB_CI_TEMPLATE = """\
sdd-governance-guard:
  stage: test
  image: python:3.11-slim
  script:
    - pip install ssd-core
    - ssd-core guard --root . --strict-state
  # Uncomment to require passing execution evidence:
  # - ssd-core guard --root . --strict-state --require-execution-evidence
"""

_CI_TEMPLATES: dict[str, tuple[str, str]] = {
    "github-actions": (_GITHUB_ACTIONS_TEMPLATE, ".github/workflows/sdd-guard.yml"),
    "gitlab-ci":      (_GITLAB_CI_TEMPLATE,       ".gitlab-ci-sdd.yml"),
}


def write_ci_template(root: Path, template_type: str) -> list[Finding]:
    """Write a CI template file for *template_type* under *root*.

    Supported types: ``github-actions`` (default), ``gitlab-ci``.
    Fails when the destination file already exists.
    """
    if template_type not in _CI_TEMPLATES:
        choices = ", ".join(sorted(_CI_TEMPLATES))
        return [Finding("error", None, f"unknown CI template type: {template_type}; choose from: {choices}")]

    content, relative_dest = _CI_TEMPLATES[template_type]
    destination = root / Path(relative_dest)
    if destination.exists():
        return [Finding("error", destination, f"CI template already exists: {relative_dest}")]

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content.lstrip(), encoding="utf-8")
    print(_green("\u2714") + f" CI template written: {_bold(relative_dest)}")
    print(f"  type    : {template_type}")
    print(f"  path    : {relative_dest}")
    print(f"  next    : commit this file, then enable CI in your repository")
    return []
