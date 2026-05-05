# Changelog

## Unreleased

## 0.1.1 - 2026-05-05

- Fixed the npm wrapper so relative `--root` paths resolve from the caller's current directory instead of the installed package directory.
- Added a release gate that smoke-tests npm-installed wrapper behavior with a relative project root.
- Aligned production-readiness wording with v0.1 scope: concrete adapter manifests are included, executable runtime wrappers are deferred.
- Added explicit DRY, KISS, YAGNI, SOLID, GRASP, and LoD principles to project guidance and constitutions.
- Hardened frontmatter validation with ISO date checks and consistency checks for change and living spec artifacts.
- Added regression tests for validation edge cases and mismatch scenarios.
- Added one-week closure plan and closure record artifacts under `docs/superpowers/plans/`.
- Updated npm publish workflow to use `--access public` with provenance publishing.

## 0.1.0 - 2026-05-03

Initial SSD-Core production candidate.

- Added protocol v0.1, constitution, profiles, schemas, adapter contract, agent contracts, and skill contracts.
- Added dependency-free reference CLI with `init`, `validate`, `status`, `new`, `check`, `sync-specs`, `archive`, and `version`.
- Added packaged `ssd-core` command with bundled templates and docs.
- Added concrete adapter manifests for Codex, Claude Code, Gemini CLI, OpenCode, and Qwen Code.
- Added a portable release readiness script and CI workflow.
- Added an npm wrapper package that delegates to the Python core.
- Added a GitHub Actions npm publish workflow using `NPM_REPOSITORY_TOKEN`.
- Added release-time version consistency checks across Python, npm, and Git tags.
- Added a `uv venv --seed` fallback for Linux environments without `python3-venv`.
- Added end-to-end lifecycle tests and a standard verified change example.
- Added MIT license and attribution notices for the MIT-licensed projects that influenced SSD-Core.
