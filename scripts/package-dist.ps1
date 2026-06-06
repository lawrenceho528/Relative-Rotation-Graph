$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"
$packageDir = Join-Path $root "deploy"
$zipPath = Join-Path $packageDir "rgg-rotation-ipad-pwa.zip"
$reportPath = Join-Path $packageDir "rgg-rotation-ipad-pwa-report.md"

& (Join-Path $PSScriptRoot "deploy-audit.ps1") | Write-Output

New-Item -ItemType Directory -Force -Path $packageDir | Out-Null

$resolvedRoot = (Resolve-Path $root).Path
$resolvedPackageDir = (Resolve-Path $packageDir).Path
if (-not $resolvedPackageDir.StartsWith($resolvedRoot)) {
  throw "Refusing to write package outside workspace: $resolvedPackageDir"
}

foreach ($path in @($zipPath, $reportPath)) {
  if (Test-Path $path) {
    $resolvedPath = (Resolve-Path $path).Path
    if (-not $resolvedPath.StartsWith($resolvedPackageDir)) {
      throw "Refusing to remove path outside package directory: $resolvedPath"
    }
    Remove-Item -LiteralPath $resolvedPath -Force
  }
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$data = Get-Content (Join-Path $dist "data/rrg.json") -Raw | ConvertFrom-Json
$archiveDate = [DateTime]::ParseExact($data.generatedAt, "yyyy-MM-dd", $null)
$archiveTime = [DateTimeOffset]::new($archiveDate.Year, $archiveDate.Month, $archiveDate.Day, 0, 0, 0, [TimeSpan]::Zero)
$distRoot = (Resolve-Path $dist).Path.TrimEnd("\")
$zipStream = [System.IO.File]::Open($zipPath, [System.IO.FileMode]::CreateNew)
try {
  $archive = [System.IO.Compression.ZipArchive]::new($zipStream, [System.IO.Compression.ZipArchiveMode]::Create)
  try {
    $files = Get-ChildItem -LiteralPath $dist -Recurse -File | Sort-Object FullName
    foreach ($file in $files) {
      $entryName = $file.FullName.Substring($distRoot.Length + 1).Replace("\", "/")
      $entry = $archive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
      $entry.LastWriteTime = $archiveTime
      $entryStream = $entry.Open()
      try {
        $fileStream = [System.IO.File]::OpenRead($file.FullName)
        try {
          $fileStream.CopyTo($entryStream)
        } finally {
          $fileStream.Dispose()
        }
      } finally {
        $entryStream.Dispose()
      }
    }
  } finally {
    $archive.Dispose()
  }
} finally {
  $zipStream.Dispose()
}

$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
  $entries = @($zip.Entries | ForEach-Object { $_.FullName.Replace("\", "/") })
} finally {
  $zip.Dispose()
}

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
  if ($entries -notcontains $file) {
    throw "Package zip missing required file: $file"
  }
}

$forbiddenPrefixes = @(".github/", "scripts/", "dist/", "deploy/")
foreach ($entry in $entries) {
  foreach ($prefix in $forbiddenPrefixes) {
    if ($entry.StartsWith($prefix)) {
      throw "Package zip contains forbidden entry: $entry"
    }
  }
}

$hash = Get-FileHash -Algorithm SHA256 -Path $zipPath
$bytes = (Get-Item -LiteralPath $zipPath).Length
$symbolCount = @($data.symbols.PSObject.Properties).Count
$spyLatest = @($data.symbols.SPY)[-1].date
$buildInfo = Get-Content (Join-Path $dist "build-info.json") -Raw | ConvertFrom-Json
$timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")

$report = @"
# RGG Rotation iPad PWA Package

Generated: $timestamp

Package:

~~~text
$zipPath
~~~

SHA256:

~~~text
$($hash.Hash)
~~~

Contents:

- Files: $($entries.Count)
- Bytes: $bytes
- RRG data source: $($data.source)
- RRG data generatedAt: $($data.generatedAt)
- Symbols: $symbolCount
- SPY latest row: $spyLatest
- Build ID: $($buildInfo.buildId)
- ZIP entry timestamp: $($archiveTime.ToString("yyyy-MM-dd HH:mm:ss zzz"))

The ZIP uses sorted entries and a fixed entry timestamp derived from `generatedAt`, so repeated packaging of the same app/data state should produce the same SHA256.

Upload the ZIP contents, not the ZIP file itself, to the HTTPS static host root for the app. After hosting, run:

~~~powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-preflight.ps1 -BaseUrl "https://your-host.example/rgg"
~~~
"@

Set-Content -Path $reportPath -Value $report -Encoding UTF8

Write-Output (
  "Deploy package passed: " +
  "zip=$zipPath bytes=$bytes sha256=$($hash.Hash) " +
  "symbols=$symbolCount generatedAt=$($data.generatedAt) buildId=$($buildInfo.buildId)"
)
