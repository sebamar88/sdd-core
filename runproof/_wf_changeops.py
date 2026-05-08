"""Change directory operations: create, summarise, check, archive, sync-specs.

Imports from _wf_registry and _wf_inference are deferred to function bodies
(lazy imports) to break the circular dependency between this module and those.
"""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from ._types import (
    Finding,
    ChangeSummary,
    WorkflowPhase,
    WorkflowState,
    SDD_DIR,
    PROFILE_ARTIFACTS,
    TOKEN_PATTERN,
    OPEN_TASK_PATTERN,
    MATRIX_PASSING_ROW_PATTERN,
    VERIFICATION_EVIDENCE_BLOCKERS,
    _green,
    _bold,
    _dim,
)
from ._wf_artifacts import (
    read_frontmatter,
    artifact_body,
    living_spec_frontmatter,
    artifact_name,
)


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
    changes_dir = root / SDD_DIR / "changes"
    if not changes_dir.is_dir():
        return []
    return sorted(path for path in changes_dir.iterdir() if path.is_dir())


def status(root: Path) -> tuple[list[Finding], list[ChangeSummary]]:
    from ._wf_validation import validate
    findings = validate(root)
    changes = [summarize_change(path) for path in active_change_directories(root)]
    for change in changes:
        if change.profile == "unknown":
            findings.append(Finding("warning", root / SDD_DIR / "changes" / change.change_id, "could not detect profile"))
        if change.missing:
            missing = ", ".join(change.missing)
            findings.append(Finding("warning", root / SDD_DIR / "changes" / change.change_id, f"missing profile artifacts: {missing}"))
    return findings, changes


def change_directory(root: Path, change_id: str) -> Path:
    return root / SDD_DIR / "changes" / change_id


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
    """Semantic check: the verification matrix must contain at least one passing row."""
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


def artifact_status(change_dir: Path, filename: str) -> tuple[str, Finding | None]:
    path = change_dir / filename
    metadata, error = read_frontmatter(path)
    if error is not None:
        return "invalid-frontmatter", Finding("error", path, error)
    return metadata.get("status", "unknown"), None


def change_location(root: Path, change_id: str) -> Path | None:
    active_dir = change_directory(root, change_id)
    if active_dir.is_dir():
        return active_dir
    return archived_change_directory(root, change_id)


def archived_change_directory(root: Path, change_id: str) -> Path | None:
    archive_root = root / SDD_DIR / "archive"
    if not archive_root.is_dir():
        return None
    matches = sorted(path for path in archive_root.glob(f"*-{change_id}") if path.is_dir())
    return matches[-1] if matches else None


def archived_change_id(archive_dir: Path) -> str:
    match = re.match(r"^\d{4}-\d{2}-\d{2}-(?P<change_id>[a-z0-9][a-z0-9-]*)$", archive_dir.name)
    if match:
        return match.group("change_id")
    return archive_dir.name


def change_has_delta_spec(change_dir: Path) -> bool:
    return (change_dir / "delta-spec.md").is_file()


def living_spec_path(root: Path, change_id: str) -> Path:
    return root / SDD_DIR / "specs" / change_id / "spec.md"


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


def strip_frontmatter_text(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1:]).lstrip() + ("\n" if text.endswith("\n") else "")
    return text


def append_sync_record(archive_path: Path, spec_path: Path, root: Path) -> None:
    relative_spec = spec_path.relative_to(root).as_posix()
    existing = archive_path.read_text(encoding="utf-8") if archive_path.exists() else ""
    marker = f"- Synced living spec: `{relative_spec}`"
    if marker in existing:
        return
    suffix = "\n" if existing.endswith("\n") or not existing else "\n\n"
    archive_path.write_text(existing + suffix + "## Sync Record\n\n" + marker + "\n", encoding="utf-8")


def archive_change(root: Path, change_id: str) -> list[Finding]:
    from ._wf_registry import COMMAND_GATES, gate_command, record_workflow_state

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

    archive_root = root / SDD_DIR / "archive"
    if not archive_root.is_dir():
        return [Finding("error", archive_root, "archive directory is missing")]

    destination = archive_root / f"{date.today().isoformat()}-{change_id}"
    if destination.exists():
        return [Finding("error", destination, "archive destination already exists")]

    changes_root = (root / SDD_DIR / "changes").resolve()
    source_resolved = source.resolve()
    if not source_resolved.is_relative_to(changes_root):
        return [Finding("error", source, f"resolved change path is outside {SDD_DIR}/changes")]

    shutil.copytree(source_resolved, destination)
    shutil.rmtree(source_resolved)
    record_workflow_state(
        root,
        WorkflowState(change_id, WorkflowPhase.ARCHIVED, summary.profile, f"Review archived evidence at {destination.as_posix()}.", []),
        "archive",
    )
    print(_green("\u2714") + f" Archived change: {_bold(destination.relative_to(root).as_posix())}")
    return []


def sync_specs(root: Path, change_id: str) -> list[Finding]:
    from ._wf_registry import COMMAND_GATES, gate_command, record_workflow_state
    from ._wf_inference import _infer_workflow_state

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

    specs_root = root / SDD_DIR / "specs"
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


def create_change(root: Path, change_id: str, profile: str, title: str | None) -> list[Finding]:
    from ._wf_registry import record_workflow_state
    from ._wf_inference import workflow_state

    findings: list[Finding] = []
    if not TOKEN_PATTERN.match(change_id):
        return [Finding("error", None, f"change-id is not valid: {change_id}")]

    if profile not in PROFILE_ARTIFACTS:
        return [Finding("error", None, f"profile is not recognized: {profile}")]

    changes_dir = root / SDD_DIR / "changes"
    profile_path = root / SDD_DIR / "profiles" / f"{profile}.md"
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


def mark_artifact_ready(root: Path, change_id: str) -> list[Finding]:
    """Mark the current phase artifact as status: ready.

    This is the UX-friendly alternative to manually editing the frontmatter.
    The user still fills in the artifact content; this command signals
    completion once the content is done.
    """
    from ._wf_registry import _PHASE_ARTIFACT_FILE
    from ._wf_inference import workflow_state
    from ._wf_evidence import set_frontmatter_value

    findings = validate_change_id(change_id)
    if findings:
        return findings

    change_dir = change_directory(root, change_id)
    if not change_dir.is_dir():
        return [Finding("error", change_dir, "change does not exist")]

    state = workflow_state(root, change_id)

    artifact_filename = _PHASE_ARTIFACT_FILE.get(state.phase)
    if artifact_filename is None:
        phase_label = state.phase.value
        return [
            Finding(
                "error",
                change_dir,
                f"phase '{phase_label}' has no editable artifact — "
                "use `runproof verify` to advance through the verify phase, "
                "or `runproof transition` for automated phases",
            )
        ]

    path = change_dir / artifact_filename
    if not path.is_file():
        return [Finding("error", path, f"{artifact_filename} is missing — run `runproof run {change_id}` to recreate it")]

    text = path.read_text(encoding="utf-8")
    text = set_frontmatter_value(text, "status", "ready")
    text = set_frontmatter_value(text, "updated", date.today().isoformat())
    path.write_text(text, encoding="utf-8")

    rel = path.relative_to(root).as_posix()
    print(_green("\u2714") + f" Marked ready: {_bold(rel)}")
    print(_dim(f"  Next: runproof transition {change_id} {state.phase.value}"))
    return []
