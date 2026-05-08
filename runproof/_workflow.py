"""Public interface for the runproof workflow subsystem.

This module is a thin aggregator — all implementation lives in the _wf_*
sub-modules.  External callers (cli.py, __init__.py, tests) continue to
import from here without any changes.
"""
from __future__ import annotations

# ── Extensions (re-exported so existing callers keep working) ─────────────────
from ._extensions import *     # noqa: F401, F403

# ── Sub-module public surfaces ─────────────────────────────────────────────────
from ._wf_artifacts import *   # noqa: F401, F403
from ._wf_templates import *   # noqa: F401, F403
from ._wf_validation import *  # noqa: F401, F403
from ._wf_changeops import *   # noqa: F401, F403
from ._wf_evidence import *    # noqa: F401, F403
from ._wf_discovery import *   # noqa: F401, F403
from ._wf_registry import *    # noqa: F401, F403
from ._wf_inference import *   # noqa: F401, F403
from ._wf_engine import *      # noqa: F401, F403
from ._wf_infra import *       # noqa: F401, F403

# ── Private names that cli.py / _render.py imports explicitly ─────────────────
from ._wf_registry import _PHASE_ARTIFACT_FILE  # noqa: F401
from ._wf_engine import _auto_advance           # noqa: F401
from ._wf_infra import _CI_TEMPLATES            # noqa: F401
from ._wf_templates import _memory_word_count   # noqa: F401
