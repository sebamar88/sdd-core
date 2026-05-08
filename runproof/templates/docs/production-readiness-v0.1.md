---
schema: sdd.document.v1
artifact: production-readiness
status: active
created: 2026-05-03
updated: 2026-05-07
---

# ProofKit v0.1 Production Readiness

This document defines what "production ready" means for ProofKit v0.1.

It does not mean the protocol is finished. It means the current framework can be installed, initialized, validated, and used as a stable repository-native SDD baseline without depending on one agent runtime or one operating system.

## Supported Guarantees

- The reference CLI is dependency-free at runtime.
- The CLI installs as the `runproof` command from a Python wheel.
- Stable Python installs are published on PyPI as `runproof-cli`.
- The npm wrapper exposes the same `runproof` command for Node-based teams and delegates to the Python core.
- Stable Node installs are published on npm as `runproof`.
- Packaged installs include the required `.runproof` templates and protocol docs.
- Source checkouts remain usable through `python scripts/sdd.py`.
- `runproof init` does not overwrite existing foundation files.
- `runproof validate` checks required directories, foundation files, JSON schema syntax, Markdown frontmatter, profile names, artifact statuses, and protocol doc pointers.
- `runproof new` creates profile-specific Markdown artifacts with stable frontmatter.
- `runproof check` blocks archive when tasks remain open or verification is incomplete.
- `runproof sync-specs` creates conservative living specs from verified delta specs.
- `runproof archive` refuses incomplete changes and moves verified changes into `.runproof/archive`.
- Release readiness can be checked with one portable command: `python scripts/release_check.py`.

## Non-Goals For v0.1

- No executable runtime command wrappers are bundled for concrete adapters; v0.1 ships capability manifests for Codex, Claude Code, Gemini CLI, OpenCode, and Qwen Code.
- No network services, telemetry, daemon, database, or hosted state.
- No dependency on JSON Schema libraries.
- No semantic merge engine for living specs.
- No guarantee that project-specific implementation tests are correct; ProofKit records and gates evidence, but the host project owns test quality.

## Release Checks

Run these checks before tagging or publishing v0.1.x:

```text
python scripts/release_check.py
```

The release check verifies version consistency, source validation, tests, package dry-run, isolated wheel install, installed CLI smoke tests, workflow binding through `runproof run`, explicit state enforcement through `.runproof/state.json`, executable verification evidence through `runproof verify --command`, hard enforcement through `runproof guard --strict-state` and `install-hooks`, npm wrapper smoke tests when Node/npm are available, caller-directory relative path behavior, and packaged template checks.

On Debian/Ubuntu systems where `python3-venv` is not installed, the release check falls back to `uv venv --seed` when `uv` is available.

For manual debugging, keep the generated temporary repository and virtual environment:

```text
python scripts/release_check.py --keep-temp
```

CI should run the same command on Windows, macOS, and Linux before release.

## npm Publishing

The repository includes a `Publish npm` workflow for publishing the npm wrapper package.
The repository also includes a `Publish PyPI` workflow for publishing the Python package to PyPI.

Required GitHub secret:

```text
NPM_REPOSITORY_TOKEN
```

The npm workflow runs `python scripts/release_check.py` before `npm publish --provenance`, and only publishes on manual `workflow_dispatch` or `v*` tags. For tag releases, the tag must match the package version, for example `v0.1.0`.

The PyPI workflow runs `python scripts/release_check.py`, builds distributions with `python -m build`, and publishes through PyPI Trusted Publishing on manual `workflow_dispatch` or GitHub `release.published`.

Configure the PyPI project `runproof-cli` with a GitHub Actions trusted publisher using:

- Repository owner: `sebamar88`
- Repository name: `ProofKit`
- Workflow file: `.github/workflows/pypi-publish.yml`
- Environment: `pypi`

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
