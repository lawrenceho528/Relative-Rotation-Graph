$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
  $pythonCommand = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $pythonCommand) {
  throw "Neither python nor python3 was found on PATH."
}
$python = $pythonCommand.Source

function Find-Browser {
  $override = $env:RGG_BROWSER
  if ($override) {
    if (Test-Path -LiteralPath $override -PathType Leaf) { return (Resolve-Path $override).Path }
    $resolved = (Get-Command $override -ErrorAction SilentlyContinue).Source
    if ($resolved) { return $resolved }
    throw "RGG_BROWSER='$override' is not an executable browser."
  }

  $candidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
  )
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) { return $candidate }
  }

  foreach ($name in @("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")) {
    $resolved = (Get-Command $name -ErrorAction SilentlyContinue).Source
    if ($resolved) { return $resolved }
  }

  $roots = @()
  if ($env:PLAYWRIGHT_BROWSERS_PATH) { $roots += $env:PLAYWRIGHT_BROWSERS_PATH }
  $roots += Join-Path $HOME ".cache/ms-playwright"
  if ($env:LOCALAPPDATA) { $roots += Join-Path $env:LOCALAPPDATA "ms-playwright" }
  else { $roots += Join-Path $HOME "AppData/Local/ms-playwright" }

  $patterns = @(
    "chromium-*/chrome-linux*/chrome",
    "chromium-*/chrome-win*/chrome.exe",
    "chromium_headless_shell-*/chrome-linux*/headless_shell"
  )
  foreach ($rootDir in $roots) {
    if (-not (Test-Path $rootDir)) { continue }
    foreach ($pattern in $patterns) {
      $expected = Join-Path $rootDir $pattern
      $match = Get-ChildItem -Path $rootDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like $expected } |
        Sort-Object FullName | Select-Object -Last 1
      if ($match) { return $match.FullName }
    }
  }

  throw "No Chrome, Edge, or Chromium executable found. Install google-chrome or chromium, or point RGG_BROWSER at an executable."
}

$browser = Find-Browser

$domPath = Join-Path $root "chrome-dom.txt"
$job = Start-Job -ScriptBlock {
  param($AppRoot, $Python)
  Set-Location $AppRoot
  & $Python -m http.server 4173 --bind 127.0.0.1
} -ArgumentList $root, $python

try {
  Start-Sleep -Seconds 2
  & $browser --headless=new --disable-gpu --no-sandbox --virtual-time-budget=5000 --dump-dom "http://127.0.0.1:4173/" | Set-Content -Path $domPath

  $dom = Get-Content $domPath -Raw
  $circleCount = ([regex]::Matches($dom, "<circle\b(?=[^>]*data-symbol=)")).Count
  $tailDotCount = ([regex]::Matches($dom, "<circle\b(?=[^>]*data-tail-dot=)")).Count
  $tailCount = ([regex]::Matches($dom, "<path\b(?=[^>]*data-tail-path=)")).Count

  if (-not ($dom.Contains("RRG data loaded") -and $dom.Contains("Last updated:"))) {
    throw "RRG data status was not rendered."
  }
  if (-not ($dom.Contains("Leading") -and $dom.Contains("Weakening") -and $dom.Contains("Lagging") -and $dom.Contains("Improving"))) {
    throw "RRG quadrant labels were not rendered."
  }
  if ($circleCount -lt 11) {
    throw "Expected at least 11 rendered sector markers; found $circleCount."
  }
  if ($tailDotCount -lt 11) {
    throw "Expected at least 11 rendered tail history dots; found $tailDotCount."
  }
  if ($tailCount -lt 11) {
    throw "Expected at least 11 rendered RGG tails; found $tailCount."
  }
  if (-not $dom.Contains("XLK")) {
    throw "Expected selected/default ticker details were not rendered."
  }
  if (-not $dom.Contains("GICS Sector")) {
    throw "Expected user-visible GICS sector context was not rendered."
  }
  if (-not $dom.Contains('data-install-target="ipad-pwa"') -or -not $dom.Contains('data-launch-mode="browser"')) {
    throw "Expected runtime launch-mode markers were not rendered."
  }

  Write-Output "Browser smoke passed: circles=$circleCount tailDots=$tailDotCount tails=$tailCount domBytes=$($dom.Length)"
} finally {
  Stop-Job $job -ErrorAction SilentlyContinue
  Remove-Job $job -Force -ErrorAction SilentlyContinue
}
