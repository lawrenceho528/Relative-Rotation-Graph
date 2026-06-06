$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"

if (Test-Path $dist) {
  $resolvedRoot = (Resolve-Path $root).Path
  $resolvedDist = (Resolve-Path $dist).Path
  if (-not $resolvedDist.StartsWith($resolvedRoot)) {
    throw "Refusing to remove path outside workspace: $resolvedDist"
  }
  Remove-Item -LiteralPath $resolvedDist -Recurse -Force
}

New-Item -ItemType Directory -Force -Path $dist | Out-Null

$files = @(
  ".nojekyll",
  "index.html",
  "styles.css",
  "manifest.webmanifest",
  "service-worker.js"
)

foreach ($file in $files) {
  Copy-Item -LiteralPath (Join-Path $root $file) -Destination (Join-Path $dist $file)
}

foreach ($directory in @("src", "icons")) {
  Copy-Item -LiteralPath (Join-Path $root $directory) -Destination (Join-Path $dist $directory) -Recurse
}

Copy-Item -Path (Join-Path $root "public\*") -Destination $dist -Recurse

$data = Get-Content (Join-Path $dist "data\rrg.json") -Raw | ConvertFrom-Json
$appHash = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $dist "src\app.js")).Hash
$styleHash = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $dist "styles.css")).Hash
$dataHash = (Get-FileHash -Algorithm SHA256 -Path (Join-Path $dist "data\rrg.json")).Hash
$identityInput = "$appHash|$styleHash|$dataHash|$($data.generatedAt)"
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
  $identityBytes = [System.Text.Encoding]::UTF8.GetBytes($identityInput)
  $buildHash = [System.BitConverter]::ToString($sha.ComputeHash($identityBytes)).Replace("-", "")
} finally {
  $sha.Dispose()
}

$buildInfo = [ordered]@{
  buildId = $buildHash.Substring(0, 12)
  generatedAt = "$($data.generatedAt)T00:00:00Z"
  dataGeneratedAt = $data.generatedAt
  dataSource = $data.source
  symbolCount = @($data.symbols.PSObject.Properties).Count
  appSha256 = $appHash
  stylesSha256 = $styleHash
  dataSha256 = $dataHash
}

$buildInfoJson = $buildInfo | ConvertTo-Json -Depth 3
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText((Join-Path $dist "build-info.json"), $buildInfoJson, $utf8NoBom)

Write-Output "Prepared static app artifact at $dist"
