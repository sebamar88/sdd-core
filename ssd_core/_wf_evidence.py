"""Execution evidence collection and verify_change gate.

Imports from _wf_changeops and _wf_registry are deferred to verify_change
to break the circular import cycle.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import uuid
from datetime import date
from pathlib import Path

from ._types import (
    Finding,
    WorkflowPhase,
    WorkflowState,
    _green,
    _bold,
    trace,
)
from ._extensions import run_extension_hooks


def utc_timestamp() -> str:
    from datetime import datetime, timezone
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


def append_execution_evidence_to_verification(
    root: Path,
    verification_path: Path,
    records: list[dict[str, object]],
) -> None:
    text = verification_path.read_text(encoding="utf-8")
    text = set_frontmatter_value(text, "status", "verified")
    text = set_frontmatter_value(text, "updated", date.today().isoformat())
    text = text.replace("pending verification evidence", "execution evidence recorded")
    text = re.sub(r"(\|\s*)not-run(\s*\|)", r"\1pass\2", text)
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


def run_verification_command(
    root: Path,
    change_id: str,
    command: str,
    timeout_seconds: int,
) -> tuple[dict[str, object], Finding | None]:
    trace("EVIDENCE", f"run_cmd {command!r}")
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


def execution_evidence_records(
    root: Path,
    change_id: str,
) -> tuple[list[dict[str, object]], list[Finding]]:
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


def print_check(root: Path, change_id: str) -> int:
    from ._wf_changeops import check_change
    from ._types import _green, _yellow, _red

    findings = check_change(root, change_id)
    if not findings:
        print(_green("\u2714") + f" Change {change_id} is ready.")
        return 0

    print(_yellow("\u25ce") + f" Change {change_id} is not ready.")
    for finding in findings:
        pre = _red("\u2717") if finding.severity == "error" else _yellow("\u26a0")
        print(pre + " " + finding.format(root))
    return 1


def verify_change(
    root: Path,
    change_id: str,
    commands: list[str] | None = None,
    *,
    require_command: bool = False,
    timeout_seconds: int = 120,
) -> list[Finding]:
    """Explicit governance gate: validate evidence quality and record VERIFY phase."""
    trace("EVIDENCE", f"verify_change {change_id} commands={len(commands or [])} require={require_command}")
    from ._wf_registry import COMMAND_GATES, gate_command, record_workflow_state
    from ._wf_changeops import (
        change_directory,
        check_change_artifacts,
        validate_verification_evidence,
        validate_verification_matrix,
        summarize_change,
        check_change,
    )
    from ._wf_artifacts import read_frontmatter

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

    ext_findings = run_extension_hooks(root, "on_verify", change_id=change_id, findings=[])
    if ext_findings:
        return ext_findings

    return []
