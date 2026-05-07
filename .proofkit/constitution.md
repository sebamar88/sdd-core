---
schema: sdd.constitution.v1
artifact: constitution
status: active
created: 2026-05-03
updated: 2026-05-03
---

# SDD-Core Constitution

## Principles

- Specifications are the durable source of intent.
- Implementation serves the approved specification and profile.
- The protocol core is independent from any agent, IDE, model, operating system, shell, terminal, package manager, or path separator.
- Platform-specific behavior belongs in adapters.
- Agents and adapters work from artifact references whenever practical.
- DRY: avoid duplicating behavior contracts or workflow logic.
- KISS: prefer the simplest design that still preserves quality gates.
- YAGNI: defer features until they are required by validated use cases.
- SOLID: keep modules focused, composable, and stable at their boundaries.
- GRASP: place responsibilities where domain information naturally lives.
- LoD: reduce coupling by limiting dependencies to immediate collaborators.

## Engineering Constraints

- Keep the protocol core minimal.
- Add workflow detail through profiles rather than changing core requirements.
- Do not introduce adapter-specific assumptions into core artifacts.
- Treat `.sdd/specs/` as living behavior documentation.
- Treat `.sdd/changes/` as isolated proposed or active changes.

## Testing Policy

- Every completed change needs verification evidence.
- Verification evidence must name what was checked and how it was checked.
- A checked task is not proof of completion by itself.
- Known gaps must be documented instead of hidden.

## Dependency Policy

- The core protocol must not require new runtime dependencies.
- Optional tooling may depend on libraries or CLIs, but those dependencies belong to adapter or implementation documentation.

## Adapter Policy

- Adapters must preserve artifact contracts.
- Adapters must translate logical paths and commands to host-native behavior.
- Adapters must not require a specific agent capability unless the adapter declares that limitation.

## Definition Of Done

A change is complete only when the selected profile's required artifacts exist, verification evidence is recorded, unresolved blockers are absent or explicitly waived, and behavior-changing work has been synchronized into living specs.

## Amendment Process

Constitution changes must explain the reason, scope, compatibility impact, and affected profiles or adapters.
