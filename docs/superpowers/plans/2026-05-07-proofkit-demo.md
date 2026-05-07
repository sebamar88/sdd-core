# ProofKit Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tiny standalone repository at `C:\Users\sebam\Desktop\Development\proofkit-demo` that shows one broken test, one blocked ProofKit verification, one one-line fix, and one successful verification.

**Architecture:** The demo repo is `README-first`: a minimal Node app lives under `broken-app/`, while a pre-bootstrapped `.sdd/` quick-profile change keeps the ProofKit verification command valid without forcing the reader through a long setup flow. Scripts under `scripts/` replay the same commands shown in the README for video capture and fast reruns.

**Tech Stack:** Node.js, npm, plain CommonJS, ProofKit CLI via `npx -y proofkit@latest`, PowerShell, POSIX shell

---

## File Structure

- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\README.md`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\package.json`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\app.js`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\test.js`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.ps1`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.sh`
- Create via ProofKit commands: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\...`
- Modify after bootstrap: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\changes\demo-sum-bug\proposal.md`
- Modify after bootstrap: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\changes\demo-sum-bug\tasks.md`

### Task 1: Prove the minimal ProofKit path in a scratch repo

**Files:**
- Create temporarily: `C:\tmp\proofkit-demo-scratch\...`
- Inspect: `C:\Users\sebam\Desktop\Development\SSD-God\README.md`

- [ ] **Step 1: Create a clean scratch directory**

Run:

```powershell
Remove-Item -Recurse -Force C:\tmp\proofkit-demo-scratch -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path C:\tmp\proofkit-demo-scratch | Out-Null
New-Item -ItemType Directory -Path C:\tmp\proofkit-demo-scratch\broken-app | Out-Null
```

Expected: `C:\tmp\proofkit-demo-scratch` exists with an empty `broken-app` subdirectory.

- [ ] **Step 2: Add the minimal broken app in scratch**

Write `C:\tmp\proofkit-demo-scratch\broken-app\package.json`:

```json
{
  "name": "broken-app",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "test": "node test.js"
  }
}
```

Write `C:\tmp\proofkit-demo-scratch\broken-app\app.js`:

```javascript
function sum(a, b) {
  return a - b;
}

module.exports = { sum };
```

Write `C:\tmp\proofkit-demo-scratch\broken-app\test.js`:

```javascript
const assert = require("node:assert/strict");
const { sum } = require("./app");

assert.equal(sum(2, 2), 4);
console.log("PASS");
```

- [ ] **Step 3: Initialize ProofKit and create the demo change**

Run:

```powershell
npx -y proofkit@latest init --root C:\tmp\proofkit-demo-scratch
npx -y proofkit@latest run demo-sum-bug --profile quick --title "Fix broken sum demo" --root C:\tmp\proofkit-demo-scratch
```

Expected:

- `C:\tmp\proofkit-demo-scratch\.sdd\` is created
- `C:\tmp\proofkit-demo-scratch\.sdd\changes\demo-sum-bug\` exists
- the recorded phase is `propose`

- [ ] **Step 4: Mark the quick-profile artifacts ready**

Overwrite `C:\tmp\proofkit-demo-scratch\.sdd\changes\demo-sum-bug\proposal.md`:

```markdown
---
schema: sdd.artifact.v1
artifact: proposal
change_id: demo-sum-bug
profile: quick
status: ready
created: 2026-05-07
updated: 2026-05-07
---

# Proposal

## Intent

Demonstrate that ProofKit blocks a broken test run even when a fix is claimed to be complete.

## Scope

- Keep one intentionally broken function under `broken-app/`.
- Verify the demo through one failing `npm test --prefix broken-app` command.
- Re-run the same command after the one-line fix.

## Non-Scope

- No UI.
- No multiple bugs.
- No full archive walkthrough.
```

Overwrite `C:\tmp\proofkit-demo-scratch\.sdd\changes\demo-sum-bug\tasks.md`:

```markdown
---
schema: sdd.artifact.v1
artifact: tasks
change_id: demo-sum-bug
profile: quick
status: ready
created: 2026-05-07
updated: 2026-05-07
---

# Tasks

- [x] T-001 Create the broken sum demo under `broken-app/`.
  - Requirement: broken app exists
  - Evidence: `npm test --prefix broken-app`

- [x] T-002 Prepare ProofKit to verify the broken app from the repository root.
  - Requirement: ProofKit verify command is runnable
  - Evidence: `npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root .`
```

- [ ] **Step 5: Record the change at `task` and verify the failure path**

Run:

```powershell
npx -y proofkit@latest transition demo-sum-bug task --root C:\tmp\proofkit-demo-scratch
npm test --prefix C:\tmp\proofkit-demo-scratch\broken-app
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root C:\tmp\proofkit-demo-scratch
```

Expected:

- `npm test` fails with an assertion error
- `proofkit verify` fails and records evidence instead of marking the change verified
- the failure message is real and reusable in the final README

- [ ] **Step 6: Fix the bug in scratch and verify the success path**

Overwrite `C:\tmp\proofkit-demo-scratch\broken-app\app.js`:

```javascript
function sum(a, b) {
  return a + b;
}

module.exports = { sum };
```

Run:

```powershell
npm test --prefix C:\tmp\proofkit-demo-scratch\broken-app
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root C:\tmp\proofkit-demo-scratch
```

Expected:

- `npm test` prints `PASS`
- `proofkit verify` succeeds
- `C:\tmp\proofkit-demo-scratch\.sdd\evidence\` contains a new evidence record

- [ ] **Step 7: Note the exact reader-facing command sequence**

Capture the exact commands that worked:

```text
npm test --prefix broken-app
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root .
```

Expected: these two commands become the canonical repo narrative and script inputs.

- [ ] **Step 8: Commit the scratch findings only mentally, not in git**

Expected: the implementer now knows the exact minimal supported workflow and can build the real demo repo without guessing.

### Task 2: Scaffold the real demo repository

**Files:**
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\README.md`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\package.json`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\app.js`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\test.js`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.ps1`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.sh`

- [ ] **Step 1: Create the repository directories**

Run:

```powershell
New-Item -ItemType Directory -Path C:\Users\sebam\Desktop\Development\proofkit-demo | Out-Null
New-Item -ItemType Directory -Path C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app | Out-Null
New-Item -ItemType Directory -Path C:\Users\sebam\Desktop\Development\proofkit-demo\scripts | Out-Null
```

Expected: the repo root, `broken-app`, and `scripts` directories exist.

- [ ] **Step 2: Write the minimal package manifest**

Create `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\package.json`:

```json
{
  "name": "broken-app",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "test": "node test.js"
  }
}
```

- [ ] **Step 3: Write the intentionally broken implementation**

Create `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\app.js`:

```javascript
function sum(a, b) {
  return a - b;
}

module.exports = { sum };
```

- [ ] **Step 4: Write the one-assertion test**

Create `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\test.js`:

```javascript
const assert = require("node:assert/strict");
const { sum } = require("./app");

assert.equal(sum(2, 2), 4);
console.log("PASS");
```

- [ ] **Step 5: Run the bare test once**

Run:

```powershell
npm test --prefix C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app
```

Expected: assertion failure before any ProofKit setup.

- [ ] **Step 6: Commit the scaffold**

Run:

```powershell
git -C C:\Users\sebam\Desktop\Development\proofkit-demo init
git -C C:\Users\sebam\Desktop\Development\proofkit-demo add broken-app
git -C C:\Users\sebam\Desktop\Development\proofkit-demo commit -m "Create the minimal broken app for the ProofKit demo"
```

Expected: the demo repo exists and the initial broken state is committed.

### Task 3: Bootstrap the minimal governed ProofKit fixture

**Files:**
- Create via command: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\...`
- Modify: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\changes\demo-sum-bug\proposal.md`
- Modify: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\changes\demo-sum-bug\tasks.md`

- [ ] **Step 1: Initialize ProofKit in the demo repo**

Run:

```powershell
npx -y proofkit@latest init --root C:\Users\sebam\Desktop\Development\proofkit-demo
npx -y proofkit@latest run demo-sum-bug --profile quick --title "Fix broken sum demo" --root C:\Users\sebam\Desktop\Development\proofkit-demo
```

Expected:

- `.sdd/` exists in the repo
- `.sdd/changes/demo-sum-bug/` exists
- the change is recorded at `propose`

- [ ] **Step 2: Replace the generated proposal with focused demo copy**

Overwrite `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\changes\demo-sum-bug\proposal.md`:

```markdown
---
schema: sdd.artifact.v1
artifact: proposal
change_id: demo-sum-bug
profile: quick
status: ready
created: 2026-05-07
updated: 2026-05-07
---

# Proposal

## Intent

Demonstrate that ProofKit blocks a claimed fix when the underlying test still fails.

## Scope

- Keep one broken function in `broken-app/app.js`.
- Use `npm test --prefix broken-app` as the single verification command.
- Keep the repo optimized for a sub-60-second explanation.

## Non-Scope

- No additional workflows beyond the verify gate.
- No multiple scenarios or edge-case catalog.
```

- [ ] **Step 3: Replace the generated tasks artifact with completed quick-profile tasks**

Overwrite `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\changes\demo-sum-bug\tasks.md`:

```markdown
---
schema: sdd.artifact.v1
artifact: tasks
change_id: demo-sum-bug
profile: quick
status: ready
created: 2026-05-07
updated: 2026-05-07
---

# Tasks

- [x] T-001 Create the broken Node demo under `broken-app/`.
  - Requirement: broken demo exists
  - Evidence: `npm test --prefix broken-app`

- [x] T-002 Prepare the demo repo for a single ProofKit verify command from the repo root.
  - Requirement: verify command is runnable
  - Evidence: `npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root .`
```

- [ ] **Step 4: Record the artifact changes and advance the change to `task`**

Run:

```powershell
npx -y proofkit@latest transition demo-sum-bug task --root C:\Users\sebam\Desktop\Development\proofkit-demo
```

Expected:

- the recorded phase becomes `task`
- `proofkit verify` is now a valid next command for the repo

- [ ] **Step 5: Confirm the broken-state verify gate in the real repo**

Run:

```powershell
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root C:\Users\sebam\Desktop\Development\proofkit-demo
```

Expected:

- the command fails
- `.sdd/evidence/` receives a failed run record
- the change does not advance to verified

- [ ] **Step 6: Commit the governed fixture**

Run:

```powershell
git -C C:\Users\sebam\Desktop\Development\proofkit-demo add .sdd
git -C C:\Users\sebam\Desktop\Development\proofkit-demo commit -m "Bootstrap the minimal ProofKit change for the demo"
```

Expected: the repo contains a legitimate active change in phase `task`.

### Task 4: Add replay scripts for manual demos and video capture

**Files:**
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.ps1`
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.sh`

- [ ] **Step 1: Write the PowerShell demo runner**

Create `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.ps1`:

```powershell
$ErrorActionPreference = "Continue"

$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Running broken test..."
npm test --prefix "$repoRoot\broken-app"

Write-Host ""
Write-Host "Running ProofKit verify..."
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root $repoRoot
```

- [ ] **Step 2: Write the POSIX shell demo runner**

Create `C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.sh`:

```bash
#!/usr/bin/env bash
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Running broken test..."
npm test --prefix "$REPO_ROOT/broken-app"

echo
echo "Running ProofKit verify..."
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root "$REPO_ROOT"
```

- [ ] **Step 3: Run the PowerShell script from the repo root**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\sebam\Desktop\Development\proofkit-demo\scripts\run-demo.ps1
```

Expected: both the failing test and the blocked ProofKit verification are replayed using the same commands shown in the README.

- [ ] **Step 4: Commit the scripts**

Run:

```powershell
git -C C:\Users\sebam\Desktop\Development\proofkit-demo add scripts
git -C C:\Users\sebam\Desktop\Development\proofkit-demo commit -m "Add replay scripts for the ProofKit demo"
```

Expected: the repo now supports fast manual and recorded demos.

### Task 5: Write the conversion-first README with real outputs

**Files:**
- Create: `C:\Users\sebam\Desktop\Development\proofkit-demo\README.md`

- [ ] **Step 1: Capture the actual failing command output**

Run:

```powershell
npm test --prefix C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app
```

Expected: the assertion stack and error text are available to quote accurately in the README.

- [ ] **Step 2: Capture the actual blocked verify output**

Run:

```powershell
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root C:\Users\sebam\Desktop\Development\proofkit-demo
```

Expected: the ProofKit failure wording is available to quote accurately in the README.

- [ ] **Step 3: Write the README around the real outputs**

Create `C:\Users\sebam\Desktop\Development\proofkit-demo\README.md`:

```markdown
# ProofKit Demo

> **Make AI prove it works.**

This demo shows how ProofKit prevents an AI agent from claiming work is done when the code is still broken.

---

## Step 1: Reality

Run the broken test:

```bash
npm test --prefix broken-app
```

Expected result: the assertion fails because `sum(2, 2)` returns the wrong value.

---

## Step 2: ProofKit blocks fake completion

Run ProofKit against the same broken code:

```bash
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root .
```

Expected result: ProofKit records the failed execution and refuses to mark the change verified.

---

## Step 3: Fix one line

Change `broken-app/app.js` from:

```javascript
function sum(a, b) {
  return a - b;
}
```

to:

```javascript
function sum(a, b) {
  return a + b;
}
```

---

## Step 4: Re-run the same commands

```bash
npm test --prefix broken-app
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root .
```

Expected result: the test passes, then ProofKit accepts the verification because the command really ran and succeeded.

---

## What this proves

- AI can say "done" when the code is still wrong.
- ProofKit does not trust the claim.
- Only real execution evidence moves the workflow forward.

That is the product.
```

- [ ] **Step 4: Replace generic “Expected result” lines with the real captured output excerpts**

Update the README so the failing test section shows the real assertion excerpt and the ProofKit section shows the real blocked verify excerpt from Steps 1 and 2.

Expected: the README contains believable output copied from actual execution, not invented snippets.

- [ ] **Step 5: Commit the README**

Run:

```powershell
git -C C:\Users\sebam\Desktop\Development\proofkit-demo add README.md
git -C C:\Users\sebam\Desktop\Development\proofkit-demo commit -m "Write the conversion-first README for the ProofKit demo"
```

Expected: the demo story is readable and convincing from the README alone.

### Task 6: Verify the full end-to-end demo state

**Files:**
- Modify temporarily during test: `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\app.js`
- Inspect: `C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\evidence\...`

- [ ] **Step 1: Confirm the repo starts broken on a fresh checkout**

Run:

```powershell
npm test --prefix C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app
```

Expected: FAIL.

- [ ] **Step 2: Confirm ProofKit blocks the broken state**

Run:

```powershell
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root C:\Users\sebam\Desktop\Development\proofkit-demo
```

Expected: FAIL with recorded evidence.

- [ ] **Step 3: Apply the final one-line fix**

Overwrite `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\app.js`:

```javascript
function sum(a, b) {
  return a + b;
}

module.exports = { sum };
```

- [ ] **Step 4: Confirm the fixed state passes**

Run:

```powershell
npm test --prefix C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app
npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root C:\Users\sebam\Desktop\Development\proofkit-demo
```

Expected: PASS, then verified.

- [ ] **Step 5: Revert the working tree back to the intentionally broken state**

Overwrite `C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app\app.js`:

```javascript
function sum(a, b) {
  return a - b;
}

module.exports = { sum };
```

Run:

```powershell
npm test --prefix C:\Users\sebam\Desktop\Development\proofkit-demo\broken-app
```

Expected: FAIL again, so the committed demo remains in the correct starting state.

- [ ] **Step 6: Inspect evidence artifacts**

Run:

```powershell
Get-ChildItem C:\Users\sebam\Desktop\Development\proofkit-demo\.sdd\evidence -Recurse
```

Expected: at least one failed and one passing verification run exists.

- [ ] **Step 7: Run repository status checks**

Run:

```powershell
git -C C:\Users\sebam\Desktop\Development\proofkit-demo status --short
```

Expected: only intentional uncommitted broken-state differences remain, or the tree is fully clean if the final chosen presentation is committed explicitly.

- [ ] **Step 8: Commit the final repo state**

Run:

```powershell
git -C C:\Users\sebam\Desktop\Development\proofkit-demo add .
git -C C:\Users\sebam\Desktop\Development\proofkit-demo commit -m "Finalize the ProofKit demo repository"
```

Expected: the repository is ready for sharing.

## Self-Review

### Spec coverage

- Broken one-line bug: covered by Task 2.
- Real failing test: covered by Task 2 and Task 6.
- ProofKit blocked verification: covered by Task 1, Task 3, and Task 6.
- One-line fix then passing verification: covered by Task 1 and Task 6.
- README-first conversion narrative: covered by Task 5.
- Replay scripts: covered by Task 4.

No spec gaps remain.

### Placeholder scan

- No `TODO`, `TBD`, or deferred implementation markers remain.
- Every file creation step includes concrete content.
- Every command step includes an explicit command and expected outcome.

### Type consistency

- The canonical change id is `demo-sum-bug` in every task.
- The canonical verification command is `npm test --prefix broken-app` in every task.
- The canonical reader-facing ProofKit command is `npx -y proofkit@latest verify demo-sum-bug --command "npm test --prefix broken-app" --root .`.
