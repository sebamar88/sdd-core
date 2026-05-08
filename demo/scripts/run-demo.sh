#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/.." && pwd)"
WORKDIR="$DEMO_DIR/.demo-workdir"
RUNPROOF=(python -m runproof)

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

section() {
  printf '\n── %s\n' "$1"
}

run_expect_fail() {
  set +e
  "$@"
  status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    printf 'Expected failure, but command passed: %s\n' "$*" >&2
    exit 1
  fi
  printf '✓ blocked as expected (exit %s)\n' "$status"
}

set -e
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"
cp -R "$DEMO_DIR/broken-app" "$WORKDIR/broken-app"

section "1/7 Start the normal RunProof workflow"
"${RUNPROOF[@]}" init --no-prompt --root "$WORKDIR"
"${RUNPROOF[@]}" run demo-sum-bug --profile quick --title "Fix broken sum demo" --root "$WORKDIR"

section "2/7 User edits proposal.md, then marks it ready"
cat > "$WORKDIR/.runproof/changes/demo-sum-bug/proposal.md" <<'MARKDOWN'
---
schema: sdd.artifact.v1
artifact: proposal
change_id: demo-sum-bug
profile: quick
status: draft
created: 2026-05-08
updated: 2026-05-08
---
# Proposal

## Intent

Demonstrate that RunProof blocks a broken test run even when an agent claims the fix is complete.

## Scope

- Keep one intentionally broken function under `broken-app/`.
- Verify the change with `npm test --prefix broken-app`.

## Non-Scope

- No UI.
- No external dependencies.
MARKDOWN
"${RUNPROOF[@]}" ready demo-sum-bug --root "$WORKDIR"
"${RUNPROOF[@]}" transition demo-sum-bug task --root "$WORKDIR"
"${RUNPROOF[@]}" run demo-sum-bug --no-create --root "$WORKDIR"

section "3/7 User edits tasks.md, then marks it ready"
cat > "$WORKDIR/.runproof/changes/demo-sum-bug/tasks.md" <<'MARKDOWN'
---
schema: sdd.artifact.v1
artifact: tasks
change_id: demo-sum-bug
profile: quick
status: draft
created: 2026-05-08
updated: 2026-05-08
---
# Tasks

- [x] T-001 Reproduce the failing test for the broken sum demo.
  - Requirement: failing baseline is visible
  - Evidence: `npm test --prefix broken-app`
- [x] T-002 Verify RunProof blocks the failing command before the fix.
  - Requirement: fake completion is blocked
  - Evidence: `runproof verify demo-sum-bug --command "npm test --prefix broken-app"`
- [x] T-003 Apply the one-line fix and capture passing evidence.
  - Requirement: real execution passes
  - Evidence: `npm test --prefix broken-app`
MARKDOWN
"${RUNPROOF[@]}" ready demo-sum-bug --root "$WORKDIR"
"${RUNPROOF[@]}" run demo-sum-bug --no-create --root "$WORKDIR"

section "4/7 An agent claims: 'done, tests pass'"
printf '🤖 Agent: done, tests pass.\n'

section "5/7 Reality check: the command fails"
run_expect_fail npm test --prefix "$WORKDIR/broken-app"

section "6/7 RunProof blocks the fake completion"
run_expect_fail "${RUNPROOF[@]}" verify demo-sum-bug --command "npm test --prefix broken-app" --root "$WORKDIR"

section "7/7 Apply the one-line fix and record real passing evidence"
python - <<'PY' "$WORKDIR/broken-app/app.js"
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text()
path.write_text(text.replace("return a - b;", "return a + b;"))
PY
npm test --prefix "$WORKDIR/broken-app"
"${RUNPROOF[@]}" verify demo-sum-bug --command "npm test --prefix broken-app" --root "$WORKDIR"

printf '\n✅ Demo complete. Evidence is in %s/.runproof/evidence/demo-sum-bug/\n' "$WORKDIR"
