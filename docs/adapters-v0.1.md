---
schema: sdd.adapters.v1
artifact: adapters
status: active
created: 2026-05-03
updated: 2026-05-03
---

# RunProof Runtime Adapters v0.1

RunProof keeps the protocol independent from any specific agent. Runtime adapters describe how a concrete tool should apply the same `.runproof` artifacts, roles, skills, and verification gates.

The shipped v0.1 adapters are capability manifests, not vendor plugins. They are intentionally plain JSON so any CLI, IDE, or agent runtime can read them.

## Included Adapters

| Adapter | Runtime | Manifest |
| --- | --- | --- |
| Generic Markdown | Human or any Markdown-capable agent | `.runproof/adapters/generic-markdown.json` |
| Codex | Codex-style coding agents | `.runproof/adapters/codex.json` |
| Claude Code | Claude Code CLI/runtime | `.runproof/adapters/claude-code.json` |
| Gemini CLI | Gemini command-line agent | `.runproof/adapters/gemini-cli.json` |
| OpenCode | OpenCode agentic coding runtime | `.runproof/adapters/opencode.json` |
| Qwen Code | Qwen Code CLI/runtime | `.runproof/adapters/qwen-code.json` |

## Adapter Rules

Every shipped adapter preserves these rules:

- `.runproof` artifacts are the source of truth.
- Runtime state must stay outside the core protocol artifacts.
- Paths are repository-relative at the protocol boundary.
- Verification evidence must be written back to RunProof artifacts.
- Archive remains blocked until `runproof check <change-id>` passes.
- Unsupported runtime features must be reported instead of silently assumed.

## Mapping Model

Adapters map portable RunProof contracts to runtime behavior:

- `.runproof/agents/*.md` become runtime roles, prompts, subagents, or phase responsibilities.
- `.runproof/skills/*.md` become task instructions, slash commands, workflow stages, or prompt prefixes.
- `.runproof/profiles/*.md` control the artifact set and rigor level.
- `runproof validate`, `runproof status`, and `runproof check` remain the common lifecycle gates.

## Implementation Status

The v0.1 adapter manifests are production-ready as static capability declarations. They do not yet install vendor-specific command wrappers or mutate external tool configuration.

Concrete runtime automation can build on these manifests without changing the RunProof protocol.
