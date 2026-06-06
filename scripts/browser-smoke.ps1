$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$chromeCandidates = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
)
$browser = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $browser) {
  throw "No Chrome or Edge executable found for browser smoke test."
}

$domPath = Join-Path $root "chrome-dom.txt"
$job = Start-Job -ScriptBlock {
  param($AppRoot)
  Set-Location $AppRoot
  python -m http.server 4173 --bind 127.0.0.1
} -ArgumentList $root

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
