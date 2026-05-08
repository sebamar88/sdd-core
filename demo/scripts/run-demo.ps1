$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DemoDir = Resolve-Path (Join-Path $ScriptDir "..")
$RepoRoot = Resolve-Path (Join-Path $DemoDir "..")
$WorkDir = Join-Path $DemoDir ".demo-workdir"

if ($env:PYTHONPATH) {
  $env:PYTHONPATH = "$RepoRoot$([IO.Path]::PathSeparator)$env:PYTHONPATH"
} else {
  $env:PYTHONPATH = "$RepoRoot"
}

function Section($Text) {
  Write-Host ""
  Write-Host "-- $Text"
}

function Invoke-ExpectFail([scriptblock]$Command, [string]$Label) {
  & $Command
  if ($LASTEXITCODE -eq 0) {
    throw "Expected failure, but command passed: $Label"
  }
  Write-Host "✓ blocked as expected (exit $LASTEXITCODE)"
}

if (Test-Path $WorkDir) {
  Remove-Item -Recurse -Force $WorkDir
}
New-Item -ItemType Directory -Path $WorkDir | Out-Null
Copy-Item -Recurse (Join-Path $DemoDir "broken-app") (Join-Path $WorkDir "broken-app")

Section "1/7 Start the normal RunProof workflow"
python -m runproof init --no-prompt --root $WorkDir
python -m runproof run demo-sum-bug --profile quick --title "Fix broken sum demo" --root $WorkDir

Section "2/7 User edits proposal.md, then marks it ready"
@'
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
'@ | Set-Content -Path (Join-Path $WorkDir ".runproof/changes/demo-sum-bug/proposal.md") -NoNewline
python -m runproof ready demo-sum-bug --root $WorkDir
python -m runproof transition demo-sum-bug task --root $WorkDir
python -m runproof run demo-sum-bug --no-create --root $WorkDir

Section "3/7 User edits tasks.md, then marks it ready"
@'
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
'@ | Set-Content -Path (Join-Path $WorkDir ".runproof/changes/demo-sum-bug/tasks.md") -NoNewline
python -m runproof ready demo-sum-bug --root $WorkDir
python -m runproof run demo-sum-bug --no-create --root $WorkDir

Section "4/7 An agent claims: 'done, tests pass'"
Write-Host "🤖 Agent: done, tests pass."

Section "5/7 Reality check: the command fails"
Invoke-ExpectFail { npm test --prefix (Join-Path $WorkDir "broken-app") } "npm test"

Section "6/7 RunProof blocks the fake completion"
Invoke-ExpectFail { python -m runproof verify demo-sum-bug --command "npm test --prefix broken-app" --root $WorkDir } "runproof verify"

Section "7/7 Apply the one-line fix and record real passing evidence"
$AppPath = Join-Path $WorkDir "broken-app/app.js"
(Get-Content $AppPath -Raw).Replace("return a - b;", "return a + b;") | Set-Content -Path $AppPath -NoNewline
npm test --prefix (Join-Path $WorkDir "broken-app")
python -m runproof verify demo-sum-bug --command "npm test --prefix broken-app" --root $WorkDir

Write-Host ""
Write-Host "✅ Demo complete. Evidence is in $WorkDir/.runproof/evidence/demo-sum-bug/"
