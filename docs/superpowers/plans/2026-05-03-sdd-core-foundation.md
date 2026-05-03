# SDD-Core Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the first repository-native SDD-Core foundation artifacts: protocol pointer, constitution, profiles, and schemas.

**Architecture:** Keep the protocol document in `docs/` as the canonical explanatory spec, while `.sdd/` contains operational artifacts that adapters and future tooling can consume. Profiles remain Markdown-first. Schemas are JSON Schema draft 2020-12 and validate metadata/result structures without assuming an agent or operating system.

**Tech Stack:** Markdown, YAML frontmatter, JSON Schema draft 2020-12, git.

---

### Task 1: Operational SDD Directory

**Files:**
- Create: `.sdd/protocol.md`
- Create: `.sdd/constitution.md`

- [x] **Step 1: Create `.sdd/protocol.md`**

Create a short operational pointer to the canonical protocol spec. This avoids copying the whole protocol into two places.

- [x] **Step 2: Create `.sdd/constitution.md`**

Create an initial constitution that anchors agent and OS agnosticism, verification discipline, platform independence, and adapter boundaries.

### Task 2: Profile Artifacts

**Files:**
- Create: `.sdd/profiles/quick.md`
- Create: `.sdd/profiles/standard.md`
- Create: `.sdd/profiles/bugfix.md`
- Create: `.sdd/profiles/refactor.md`
- Create: `.sdd/profiles/enterprise.md`
- Create: `.sdd/profiles/research.md`

- [x] **Step 1: Create one Markdown profile per lifecycle track**

Each profile defines when to use it, required artifacts, allowed shortcuts, hard gates, and completion evidence.

- [x] **Step 2: Keep profiles protocol-neutral**

No profile may require a specific agent, OS, shell, package manager, or CLI.

### Task 3: Schema Artifacts

**Files:**
- Create: `.sdd/schemas/artifact.schema.json`
- Create: `.sdd/schemas/phase-result.schema.json`
- Create: `.sdd/schemas/verification.schema.json`

- [x] **Step 1: Create artifact metadata schema**

Validate common frontmatter fields such as `schema`, `artifact`, `change_id`, `status`, `created`, and `updated`.

- [x] **Step 2: Create phase result schema**

Validate phase result envelopes with `change_id`, `phase`, `status`, `reads`, `writes`, `next`, `risk`, and `blocking_issues`.

- [x] **Step 3: Create verification schema**

Validate requirement-to-evidence matrices without assuming a concrete test runner.

### Task 4: Review And Commit

**Files:**
- Read: all created files

- [x] **Step 1: Scan for placeholders**

Run: `rg -n "T[B]D|T[O]DO|F[I]XME|NEEDS CLARIFICATI[O]N|\\?\\?" .sdd docs/superpowers/plans`

Expected: no matches.

- [x] **Step 2: Review git status and staged diff**

Run: `git status --short` and `git diff --stat`.

Expected: only planned artifacts are changed.

- [x] **Step 3: Commit**

Create a lore-style commit describing why the foundation artifacts exist before adapter implementation.
