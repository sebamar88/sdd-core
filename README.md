# SSD-Core

Spec-driven development for any agent, on any operating system.

SSD-Core is a portable workflow layer for teams using coding agents. It keeps intent, decisions, and evidence in repository artifacts instead of fragile chat memory.

```text
Intent -> Spec -> Design -> Tasks -> Verification -> Archive
```

No lock-in. No hidden state. No runtime-specific source of truth.

## Start Here

Choose your path:

- New to SSD-Core: go to [5-Minute Path](#5-minute-path)
- Running SSD-Core in a team: go to [Team Path](#team-path)

## 5-Minute Path

### 1) Install

Python/uv path:

```text
uv tool install .
```

Node wrapper path:

```text
npm install -g .
```

The npm package delegates to the same Python core and requires Python 3.11+ on `PATH`.

### 2) Verify CLI

```text
ssd-core version
```

### 3) Initialize SDD-Core in a repository

```text
ssd-core init --root path-to-repository
```

### 4) Validate baseline

```text
ssd-core validate --root path-to-repository
```

### 5) Open your first change

```text
ssd-core new add-search --profile standard --title "Add search" --root path-to-repository
```

### 6) Track and close

```text
ssd-core status --root path-to-repository
ssd-core check add-search --root path-to-repository
ssd-core sync-specs add-search --root path-to-repository
ssd-core archive add-search --root path-to-repository
```

## Team Path

If you are adopting SSD-Core across a team, focus on these in order:

1. Read the protocol baseline: [docs/sdd-core-protocol-v0.1.md](docs/sdd-core-protocol-v0.1.md)
2. Align adapter boundaries: [docs/adapter-contract-v0.1.md](docs/adapter-contract-v0.1.md)
3. Select profile defaults (`quick`, `standard`, `bugfix`, `refactor`, `enterprise`, `research`)
4. Enforce release gate in CI with `python scripts/release_check.py`
5. Require verification evidence before archive

## What SSD-Core Adds

SSD-Core is not another agent runtime. It adds a stable repository contract:

- `.sdd/specs/` for living behavior
- `.sdd/changes/<change-id>/` for active deltas
- `.sdd/archive/` for completed changes
- profile-driven rigor without forcing heavy ceremony
- evidence-gated completion criteria

## Repository Layout

```text
.sdd/
  adapters/
  agents/
  constitution.md
  examples/
  protocol.md
  profiles/
  schemas/
  skills/
  specs/
  changes/
  archive/

docs/
  sdd-core-protocol-v0.1.md
  adapter-contract-v0.1.md
  adapter-authoring-v0.1.md
  sdd-validator-v0.1.md
```

## Command Guide

```text
ssd-core version
ssd-core validate
ssd-core init --root <path>
ssd-core status
ssd-core new <change-id> --profile <profile> --title "Human intent"
ssd-core check <change-id>
ssd-core sync-specs <change-id>
ssd-core archive <change-id>
```

## Lifecycle

```text
explore -> propose -> specify -> design -> task -> implement -> verify -> critique -> archive
```

Core rule: no archive without verification evidence.

## Profiles

SSD-Core ships six profiles:

- `quick`
- `standard`
- `bugfix`
- `refactor`
- `enterprise`
- `research`

Use the smallest safe profile for the change type.

## Adapters

### Reference Adapter

The generic baseline is:

- `.sdd/adapters/generic-markdown.json`

Use it as the portable contract for any human or tool workflow that can read/write repo artifacts.

### Concrete Capability Manifests Included in v0.1

- Codex: `.sdd/adapters/codex.json`
- Claude Code: `.sdd/adapters/claude-code.json`
- Gemini CLI: `.sdd/adapters/gemini-cli.json`
- OpenCode: `.sdd/adapters/opencode.json`
- Qwen Code: `.sdd/adapters/qwen-code.json`

v0.1 includes manifests, not executable runtime wrappers.

See [docs/adapters-v0.1.md](docs/adapters-v0.1.md) and [docs/adapter-authoring-v0.1.md](docs/adapter-authoring-v0.1.md).

## Principles

- DRY: avoid duplicated logic, contracts, and workflow decisions
- KISS: choose the simplest design that preserves correctness
- YAGNI: do not ship speculative mechanisms
- SOLID: prefer focused modules and stable boundaries
- GRASP: place responsibilities where knowledge already lives
- LoD: minimize coupling to immediate collaborators

Plus SSD-Core specifics:

- keep the core small
- push runtime specifics into adapters
- prefer files over chat memory
- prefer evidence over confidence
- never archive incomplete work quietly

## Production Readiness

For v0.1, readiness means the project can:

- install as wheel and npm wrapper
- initialize from packaged templates
- validate artifacts consistently
- run cross-platform CI checks

Run the full release gate locally:

```text
python scripts/release_check.py
```

See:

- [docs/production-readiness-v0.1.md](docs/production-readiness-v0.1.md)
- [docs/superpowers/plans/2026-05-03-v0.1-closure-week.md](docs/superpowers/plans/2026-05-03-v0.1-closure-week.md)
- [docs/superpowers/plans/2026-05-03-v0.1-closure-record.md](docs/superpowers/plans/2026-05-03-v0.1-closure-record.md)

## Current Status

Current release: `v0.1.0`

Solid in v0.1:

- protocol, constitution, profiles, schemas
- concrete adapter manifests for major runtimes
- dependency-free reference CLI
- packaged templates and docs
- cross-platform release check and CI

Deferred to future versions:

- deeper artifact JSON Schema validation
- semantic living spec merge
- executable runtime command wrappers for adapters
- richer profile templates

## Influences And Attribution

SSD-Core is original work, informed by MIT-licensed workflow ideas from:

- [GitHub Spec Kit](https://github.com/github/spec-kit)
- [OpenSpec](https://github.com/Fission-AI/OpenSpec)
- [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite)
- [BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)

Attribution and compatibility notes are in [NOTICE.md](NOTICE.md).

## License

SSD-Core is released under the [MIT License](LICENSE).
