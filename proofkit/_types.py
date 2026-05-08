from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, Iterable, Protocol

VERSION = "0.27.0"


# ── Terminal color helpers ───────────────────────────────────────────────────

_DISPLAY_FALLBACKS = str.maketrans(
    {
        "✔": "OK",
        "✗": "x",
        "⚠": "!",
        "○": "o",
        "◎": "*",
        "◉": "@",
        "⟳": "~",
        "→": "->",
        "─": "-",
        "—": "-",
    }
)


def _display_text(text: str) -> str:
    """Return *text* adapted to the active stdout encoding when needed."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        return text.translate(_DISPLAY_FALLBACKS)
    return text

def _use_color() -> bool:
    """Return True when the terminal supports ANSI color sequences."""
    return (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and not os.environ.get("NO_COLOR")
        and os.environ.get("TERM") != "dumb"
    )


def _c(code: str, text: str) -> str:
    text = _display_text(text)
    return f"\033[{code}m{text}\033[0m" if _use_color() else text


def _green(t: str) -> str:  return _c("32", t)
def _yellow(t: str) -> str: return _c("33", t)
def _red(t: str) -> str:    return _c("31", t)
def _cyan(t: str) -> str:   return _c("36", t)
def _bold(t: str) -> str:   return _c("1",  t)
def _dim(t: str) -> str:    return _c("2",  t)


# ── Trace / debug mode ───────────────────────────────────────────────────────

_TRACE_ENABLED: bool = False


def enable_trace() -> None:
    """Activate component-level trace output for the current process."""
    global _TRACE_ENABLED
    _TRACE_ENABLED = True


def trace(component: str, message: str) -> None:
    """Emit a single debug trace line to stderr when --trace is active."""
    if _TRACE_ENABLED:
        print(f"[TRACE] {component:<12} → {message}", file=sys.stderr)


_PHASE_ICON: dict[str, str] = {
    "not-started":    "○",
    "propose":        "◎",
    "specify":        "◎",
    "design":         "◎",
    "task":           "◎",
    "verify":         "◉",
    "critique":       "◎",
    "archive-record": "◎",
    "sync-specs":     "⟳",
    "archive":        "⟳",
    "archived":       "✔",
    "blocked":        "✗",
}

SDD_DIR = ".proofkit"

REQUIRED_DIRECTORIES = [
    ".proofkit",
    ".proofkit/adapters",
    ".proofkit/agents",
    ".proofkit/memory",
    ".proofkit/profiles",
    ".proofkit/schemas",
    ".proofkit/skills",
    ".proofkit/specs",
    ".proofkit/changes",
    ".proofkit/archive",
    ".proofkit/evidence",
    ".proofkit/extensions",
]

REQUIRED_ADAPTERS = [
    "claude-code.json",
    "codex.json",
    "cursor.json",
    "generic-markdown.json",
    "gemini-cli.json",
    "github-copilot.json",
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
    "extension.schema.json",
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
    "state.json",
]

MEMORY_COPY_FILES = [
    "project.md",
    "decisions.md",
]

MEMORY_KEYS = ["project", "decisions"]

FOUNDATION_DOC_FILES = [
    "adapter-contract-v0.1.md",
    "adapter-authoring-v0.1.md",
    "adapters-v0.1.md",
    "production-readiness-v0.1.md",
    "proofkit-protocol-v0.1.md",
    "sdd-validator-v0.1.md",
]

EMPTY_STATE_DIRECTORIES = [
    "archive",
    "changes",
    "evidence",
    "extensions",
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
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPEN_TASK_PATTERN = re.compile(r"^\s*-\s+\[\s\]", re.MULTILINE)

# Matches a verification matrix row (5 pipe-separated cells) whose last cell is
# a recognised passing status.  Separator rows (--- | --- ...) are skipped because
# they contain only hyphens/spaces, not word characters in between.
MATRIX_PASSING_ROW_PATTERN = re.compile(
    r"^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|\s*(?:pass|verified|complete)\s*\|\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Terms that indicate placeholder evidence in verification.md.
# If any appear in a verification artifact, it cannot be recorded as verified.
VERIFICATION_EVIDENCE_BLOCKERS: frozenset[str] = frozenset({
    "not-run",
    "pending verification evidence",
    "record host-project verification actions.",
})


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
class RepositoryInfo:
    """Detected characteristics of an existing repository."""

    languages: tuple[str, ...]
    test_command: str | None
    has_ci: bool
    has_sdd: bool


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


class WorkflowPhase(str, Enum):
    NOT_STARTED = "not-started"
    PROPOSE = "propose"
    SPECIFY = "specify"
    DESIGN = "design"
    TASK = "task"
    VERIFY = "verify"
    CRITIQUE = "critique"
    ARCHIVE_RECORD = "archive-record"
    SYNC_SPECS = "sync-specs"
    ARCHIVE = "archive"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


# Ordered phase list used for pipeline visualisation.  Phases not in this list
# (BLOCKED, NOT_STARTED) are intentionally excluded from the linear pipeline.
_PIPELINE_PHASES: list[WorkflowPhase] = [
    WorkflowPhase.PROPOSE,
    WorkflowPhase.SPECIFY,
    WorkflowPhase.DESIGN,
    WorkflowPhase.TASK,
    WorkflowPhase.VERIFY,
    WorkflowPhase.CRITIQUE,
    WorkflowPhase.ARCHIVE_RECORD,
    WorkflowPhase.SYNC_SPECS,
    WorkflowPhase.ARCHIVE,
    WorkflowPhase.ARCHIVED,
]


WORKFLOW_STATE_SCHEMA = "sdd.state.v1"

PHASE_ORDER = {
    WorkflowPhase.NOT_STARTED: 0,
    WorkflowPhase.PROPOSE: 10,
    WorkflowPhase.SPECIFY: 20,
    WorkflowPhase.DESIGN: 30,
    WorkflowPhase.TASK: 40,
    WorkflowPhase.VERIFY: 50,
    WorkflowPhase.CRITIQUE: 60,
    WorkflowPhase.ARCHIVE_RECORD: 70,
    WorkflowPhase.SYNC_SPECS: 80,
    WorkflowPhase.ARCHIVE: 90,
    WorkflowPhase.ARCHIVED: 100,
}

# Maps each phase to its canonical next-action message.  Used by workflow_state
# when returning a state.json-declared phase so we don't re-scan artifacts.
PHASE_NEXT_ACTIONS: dict[WorkflowPhase, str] = {
    WorkflowPhase.NOT_STARTED:    "Create the governed change artifacts.",
    WorkflowPhase.PROPOSE:        "Complete proposal.md and set status to ready.",
    WorkflowPhase.SPECIFY:        "Complete delta-spec.md and set status to ready.",
    WorkflowPhase.DESIGN:         "Complete design.md and set status to ready.",
    WorkflowPhase.TASK:           "Complete tasks.md, close all task checkboxes, and set status to ready.",
    WorkflowPhase.VERIFY:         "Record passing evidence in verification.md and set status to verified.",
    WorkflowPhase.CRITIQUE:       "Resolve critique.md and set status to ready or verified.",
    WorkflowPhase.ARCHIVE_RECORD: "Complete archive.md and set status to ready.",
    WorkflowPhase.SYNC_SPECS:     "Run `proofkit sync-specs <change_id> --root <repo>`.",
    WorkflowPhase.ARCHIVE:        "Run `proofkit archive <change_id> --root <repo>`.",
    WorkflowPhase.ARCHIVED:       "Review archived change evidence.",
    WorkflowPhase.BLOCKED:        "Resolve blocking findings before continuing.",
}

ALLOWED_TRANSITIONS = {
    WorkflowPhase.NOT_STARTED: {WorkflowPhase.PROPOSE},
    WorkflowPhase.PROPOSE: {WorkflowPhase.SPECIFY, WorkflowPhase.TASK},
    WorkflowPhase.SPECIFY: {WorkflowPhase.DESIGN, WorkflowPhase.TASK},
    WorkflowPhase.DESIGN: {WorkflowPhase.TASK},
    WorkflowPhase.TASK: {WorkflowPhase.VERIFY},
    WorkflowPhase.VERIFY: {WorkflowPhase.CRITIQUE, WorkflowPhase.ARCHIVE_RECORD, WorkflowPhase.SYNC_SPECS, WorkflowPhase.ARCHIVE},
    WorkflowPhase.CRITIQUE: {WorkflowPhase.ARCHIVE_RECORD, WorkflowPhase.SYNC_SPECS, WorkflowPhase.ARCHIVE},
    WorkflowPhase.ARCHIVE_RECORD: {WorkflowPhase.SYNC_SPECS, WorkflowPhase.ARCHIVE},
    WorkflowPhase.SYNC_SPECS: {WorkflowPhase.ARCHIVE},
    WorkflowPhase.ARCHIVE: {WorkflowPhase.ARCHIVED},
    WorkflowPhase.ARCHIVED: set(),
}


class WorkflowFailureKind(str, Enum):
    VALIDATION = "validation"
    CREATION = "creation"
    PHASE_ORDER = "phase-order"
    COMMAND = "command"


@dataclass(frozen=True)
class WorkflowFailure:
    kind: WorkflowFailureKind
    message: str
    path: Path | None = None

    @classmethod
    def from_finding(cls, kind: WorkflowFailureKind, finding: Finding) -> "WorkflowFailure":
        return cls(kind, finding.message, finding.path)

    def to_finding(self) -> Finding:
        return Finding("error", self.path, self.message)


@dataclass(frozen=True)
class WorkflowState:
    change_id: str
    phase: WorkflowPhase
    profile: str
    next_action: str
    findings: list[Finding]

    @property
    def is_blocked(self) -> bool:
        return self.phase == WorkflowPhase.BLOCKED


@dataclass(frozen=True)
class WorkflowResult:
    state: WorkflowState
    failures: list[WorkflowFailure]

    @property
    def ok(self) -> bool:
        return not self.failures and not self.state.is_blocked

