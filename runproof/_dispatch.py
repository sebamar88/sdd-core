"""Multi-agent dispatcher for RunProof.

Provides a lightweight, pluggable interface for running AI agent CLI tools as
subprocesses.  Zero runtime dependencies — uses only the stdlib ``subprocess``
and ``shutil`` modules.

Public surface
--------------
DispatchRequest  — frozen dataclass describing what to run.
DispatchResult   — frozen dataclass holding the outcome.
ShellAgentDispatcher  — runs any prompt as a shell command.
ClaudeCodeDispatcher  — runs the ``claude`` CLI (Claude Code).
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DispatchRequest:
    """Everything a dispatcher needs to run one agent invocation."""

    agent: str
    """Logical agent identifier, e.g. ``"shell"``, ``"claude-code"``."""

    prompt: str
    """Prompt or command to pass to the agent."""

    working_dir: Path
    """Directory in which the agent should run."""

    timeout_seconds: int = 60
    """Hard wall-clock timeout for the subprocess."""


@dataclass(frozen=True)
class DispatchResult:
    """Outcome of a single agent invocation."""

    exit_code: int
    stdout: str
    stderr: str
    elapsed_seconds: float

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class ShellAgentDispatcher:
    """Run the prompt as a plain shell command via ``subprocess``.

    The ``prompt`` field of :class:`DispatchRequest` is treated as a shell
    command string and executed with ``shell=True``.  This is intentionally
    limited to trusted, developer-controlled inputs — never pass untrusted
    user input as the prompt.
    """

    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        start = time.monotonic()
        try:
            proc = subprocess.run(
                request.prompt,
                shell=True,
                cwd=request.working_dir,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
            )
            elapsed = time.monotonic() - start
            return DispatchResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                elapsed_seconds=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return DispatchResult(
                exit_code=124,
                stdout="",
                stderr=f"timeout after {request.timeout_seconds}s",
                elapsed_seconds=elapsed,
            )
        except OSError as exc:
            elapsed = time.monotonic() - start
            return DispatchResult(
                exit_code=1,
                stdout="",
                stderr=str(exc),
                elapsed_seconds=elapsed,
            )


class ClaudeCodeDispatcher:
    """Run the ``claude`` CLI (Claude Code) with a non-interactive prompt.

    Passes the prompt via ``--print`` / ``-p`` flags so the process exits
    immediately after producing output, which is suitable for automation.

    Returns a failed :class:`DispatchResult` (exit_code=127) when the
    ``claude`` binary is not found on ``PATH``.
    """

    _CLI_NAME = "claude"

    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        if not shutil.which(self._CLI_NAME):
            return DispatchResult(
                exit_code=127,
                stdout="",
                stderr=f"'{self._CLI_NAME}' not found on PATH",
                elapsed_seconds=0.0,
            )

        cmd = [self._CLI_NAME, "--print", request.prompt]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=request.working_dir,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
            )
            elapsed = time.monotonic() - start
            return DispatchResult(
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                elapsed_seconds=elapsed,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            return DispatchResult(
                exit_code=124,
                stdout="",
                stderr=f"timeout after {request.timeout_seconds}s",
                elapsed_seconds=elapsed,
            )
        except OSError as exc:
            elapsed = time.monotonic() - start
            return DispatchResult(
                exit_code=1,
                stdout="",
                stderr=str(exc),
                elapsed_seconds=elapsed,
            )
