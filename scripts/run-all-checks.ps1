$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# Prefer `python`, fall back to `python3` (typical on Linux distributions).
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
  $pythonCommand = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCommand) {
  throw "Neither python nor python3 was found on PATH."
}
$python = $pythonCommand.Source

function Run-Step {
  param(
    [string] $Name,
    [scriptblock] $Command
  )

  Write-Output ""
  Write-Output "== $Name =="
  $global:LASTEXITCODE = 0
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

Run-Step "Static verification" {
  & (Join-Path $PSScriptRoot "verify.ps1")
}

Run-Step "Refresh RRG data" {
  & $python scripts/update_rrg_data.py --validate-only
  & $python -c "import json; d=json.load(open('public/data/rrg.json')); print('source=' + d['source']); print('generatedAt=' + d['generatedAt']); print('symbols=' + str(len(d['symbols']))); print('spyLatest=' + str(d['symbols']['SPY'][-1]['date']))"
}

Run-Step "Data freshness audit" {
  & $python scripts/data-freshness-audit.py
}

Run-Step "Universe coverage audit" {
  & $python scripts/universe-audit.py
}

Run-Step "RRG formula audit" {
  & $python scripts/rrg-formula-audit.py
}

Run-Step "Workflow audit" {
  & $python scripts/workflow-audit.py
}

Run-Step "Deploy artifact audit" {
  & (Join-Path $PSScriptRoot "deploy-audit.ps1")
}

Run-Step "Deploy package audit" {
  & (Join-Path $PSScriptRoot "package-dist.ps1")
}

Run-Step "Install URL preflight" {
  & $python scripts/install-preflight-local.py
}

Run-Step "iPad QR handoff audit" {
  & $python scripts/qr-handoff-audit.py
}

Run-Step "Performance audit" {
  & $python scripts/performance-audit.py
}

Run-Step "Dist runtime audit" {
  & $python scripts/dist-runtime-audit.py
}

Run-Step "App shell update audit" {
  & $python scripts/app-shell-update-audit.py
}

Run-Step "PWA audit" {
  & $python scripts/pwa-audit.py
}

Run-Step "Offline audit" {
  & $python scripts/offline-audit.py
}

Run-Step "Accessibility audit" {
  & $python scripts/accessibility-audit.py
}

Run-Step "Browser DOM smoke" {
  & (Join-Path $PSScriptRoot "browser-smoke.ps1")
}

Run-Step "Programmatic interaction smoke" {
  & $python scripts/browser-interaction.py
}

Run-Step "Pointer interaction smoke" {
  & $python scripts/browser-pointer.py
}

Run-Step "Chart scale and visibility controls audit" {
  & $python scripts/chart-controls-audit.py
}

Run-Step "Double tap zoom lock audit" {
  & $python scripts/zoom-lock-audit.py
}

Run-Step "iPad touch audit" {
  & $python scripts/ipad-touch-audit.py
}

Run-Step "iPad layout audit" {
  & $python scripts/layout-audit.py
}

Run-Step "RRG data cache update audit" {
  & $python scripts/data-update-audit.py
}

Run-Step "iPad viewport screenshots" {
  & $python scripts/browser-capture.py --width 744 --height 1133 --scale 1 --out rgg-ipad-mini-portrait.png
  & $python scripts/browser-capture.py --width 1133 --height 744 --scale 1 --out rgg-ipad-mini-landscape.png
}

Run-Step "iPad screenshot visual audit" {
  & $python scripts/visual-audit.py
}

Write-Output ""
Write-Output "All checks passed."
