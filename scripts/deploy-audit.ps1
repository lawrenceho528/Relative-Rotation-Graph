$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"

& (Join-Path $PSScriptRoot "prepare-dist.ps1")

$required = @(
  ".nojekyll",
  "index.html",
  "styles.css",
  "manifest.webmanifest",
  "service-worker.js",
  "build-info.json",
  "src/app.js",
  "data/rrg.json",
  "icons/apple-touch-icon.png",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon.svg"
)

foreach ($file in $required) {
  $path = Join-Path $dist $file
  if (-not (Test-Path $path)) {
    throw "Missing dist artifact file: $file"
  }
}

$forbidden = @(".github", "scripts", ".chrome-profile", ".edge-profile", "chrome-dom.txt", "VERIFICATION.md")
foreach ($item in $forbidden) {
  if (Test-Path (Join-Path $dist $item)) {
    throw "Forbidden file or directory was copied into dist: $item"
  }
}

$html = Get-Content (Join-Path $dist "index.html") -Raw
$manifest = Get-Content (Join-Path $dist "manifest.webmanifest") -Raw | ConvertFrom-Json
$serviceWorker = Get-Content (Join-Path $dist "service-worker.js") -Raw
$data = Get-Content (Join-Path $dist "data/rrg.json") -Raw | ConvertFrom-Json
$buildInfo = Get-Content (Join-Path $dist "build-info.json") -Raw | ConvertFrom-Json

if (-not $html.Contains('./src/app.js')) {
  throw "Dist HTML does not load the app JavaScript."
}
if ($manifest.display -ne "standalone") {
  throw "Dist manifest is not standalone."
}
if (-not $serviceWorker.Contains('./data/rrg.json')) {
  throw "Dist service worker does not cache generated RRG data."
}
if (-not $serviceWorker.Contains('build-info.json')) {
  throw "Dist service worker does not cache build identity."
}
if (-not $data.symbols.SPY -or $data.symbols.SPY.Count -lt 180) {
  throw "Dist generated RRG data is missing SPY history."
}
if (-not $buildInfo.buildId -or $buildInfo.dataGeneratedAt -ne $data.generatedAt) {
  throw "Dist build identity is missing or not aligned with generated RRG data."
}

$fileCount = (Get-ChildItem -LiteralPath $dist -Recurse -File).Count
$bytes = (Get-ChildItem -LiteralPath $dist -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Output "Deploy audit passed: files=$fileCount bytes=$bytes source=$($data.source) generatedAt=$($data.generatedAt) buildId=$($buildInfo.buildId)"
