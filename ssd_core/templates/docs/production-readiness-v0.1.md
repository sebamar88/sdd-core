---
schema: sdd.document.v1
artifact: production-readiness
status: active
created: 2026-05-03
updated: 2026-05-03
---

# SSD-Core v0.1 Production Readiness

This document defines what "production ready" means for SSD-Core v0.1.

It does not mean the protocol is finished. It means the current framework can be installed, initialized, validated, and used as a stable repository-native SDD baseline without depending on one agent runtime or one operating system.

## Supported Guarantees

- The reference CLI is dependency-free at runtime.
- The CLI installs as the `ssd-core` command from a Python wheel.
- Packaged installs include the required `.sdd` templates and protocol docs.
- Source checkouts remain usable through `python scripts/sdd.py`.
- `ssd-core init` does not overwrite existing foundation files.
- `ssd-core validate` checks required directories, foundation files, JSON schema syntax, Markdown frontmatter, profile names, artifact statuses, and protocol doc pointers.
- `ssd-core new` creates profile-specific Markdown artifacts with stable frontmatter.
- `ssd-core check` blocks archive when tasks remain open or verification is incomplete.
- `ssd-core sync-specs` creates conservative living specs from verified delta specs.
- `ssd-core archive` refuses incomplete changes and moves verified changes into `.sdd/archive`.

## Non-Goals For v0.1

- No concrete IDE or agent adapter is bundled beyond the generic Markdown adapter.
- No network services, telemetry, daemon, database, or hosted state.
- No dependency on JSON Schema libraries.
- No semantic merge engine for living specs.
- No guarantee that project-specific implementation tests are correct; SSD-Core records and gates evidence, but the host project owns test quality.

## Release Checks

Run these checks before tagging or publishing v0.1.x:

```text
python -m py_compile scripts/sdd.py ssd_core/cli.py tests/test_sdd.py
python -m unittest tests/test_sdd.py
python scripts/sdd.py validate
python scripts/sdd.py status
python -m pip install . --dry-run
python -m venv .tmp-venv-prod
```

Then run the installed CLI from the virtual environment:

```text
# Windows
.tmp-venv-prod/Scripts/python.exe -m pip install .
.tmp-venv-prod/Scripts/ssd-core.exe version
.tmp-venv-prod/Scripts/ssd-core.exe init --root .tmp-prod-smoke
.tmp-venv-prod/Scripts/ssd-core.exe validate --root .tmp-prod-smoke

# POSIX
.tmp-venv-prod/bin/python -m pip install .
.tmp-venv-prod/bin/ssd-core version
.tmp-venv-prod/bin/ssd-core init --root .tmp-prod-smoke
.tmp-venv-prod/bin/ssd-core validate --root .tmp-prod-smoke
```

## Compatibility Policy

For v0.1.x:

- Existing artifact filenames should remain stable.
- Existing frontmatter keys should not be removed.
- Existing CLI commands should not change behavior incompatibly without a minor version bump.
- New validation checks may be added when they detect objectively invalid artifacts.
- Adapter authors should treat `.sdd` artifacts as the source of truth and keep runtime state outside the protocol core.

## Known Gaps

- Full JSON Schema validation is intentionally deferred until the schema surface stabilizes.
- Living spec sync is append/create oriented and avoids semantic rewriting.
- Agent and skill contracts are portable Markdown contracts, not executable runtime integrations.
