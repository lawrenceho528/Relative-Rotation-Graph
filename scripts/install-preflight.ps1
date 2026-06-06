param(
  [string] $BaseUrl = "http://127.0.0.1:4173"
)

$ErrorActionPreference = "Stop"

$uri = [Uri] $BaseUrl
$isLocalHttp = $uri.Scheme -eq "http" -and @("127.0.0.1", "localhost", "::1") -contains $uri.Host
if ($uri.Scheme -ne "https" -and -not $isLocalHttp) {
  throw "iPad install preflight requires HTTPS hosting, except localhost/127.0.0.1 for local preview: $BaseUrl"
}

$base = $BaseUrl.TrimEnd("/")
$requiredPaths = @(
  "/index.html",
  "/manifest.webmanifest",
  "/service-worker.js",
  "/build-info.json",
  "/data/rrg.json",
  "/icons/apple-touch-icon.png"
)

function Read-Url {
  param([string] $Path)

  $url = "$base$Path"
  $response = Invoke-WebRequest -Uri $url -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 20
  if ($response.StatusCode -ne 200) {
    throw "Expected 200 for $url, got $($response.StatusCode)"
  }
  if ($response.RawContentLength -le 0) {
    throw "Empty response for $url"
  }
  return $response
}

function Read-ResponseText {
  param($Response)

  if ($Response.Content -is [byte[]]) {
    return [System.Text.Encoding]::UTF8.GetString($Response.Content)
  }
  return [string] $Response.Content
}

$responses = @{}
foreach ($path in $requiredPaths) {
  $responses[$path] = Read-Url $path
}

$manifest = Read-ResponseText $responses["/manifest.webmanifest"] | ConvertFrom-Json
if ($manifest.display -ne "standalone") {
  throw "Manifest display must be standalone, got $($manifest.display)"
}
if ($manifest.start_url -ne "./index.html") {
  throw "Manifest start_url changed: $($manifest.start_url)"
}
if (-not [bool]($manifest.icons | Where-Object { $_.src -eq "./icons/icon-192.png" })) {
  throw "Manifest is missing 192px icon"
}
if (-not [bool]($manifest.icons | Where-Object { $_.src -eq "./icons/icon-512.png" })) {
  throw "Manifest is missing 512px icon"
}

$serviceWorker = Read-ResponseText $responses["/service-worker.js"]
if (-not $serviceWorker.Contains("networkFirst(request, cacheKey)")) {
  throw "Service worker is missing network-first RRG data caching"
}
if (-not $serviceWorker.Contains("url.origin === self.location.origin")) {
  throw "Service worker is missing network-first app-shell caching"
}

$buildInfo = Read-ResponseText $responses["/build-info.json"] | ConvertFrom-Json
if (-not $buildInfo.buildId) {
  throw "Build identity is missing buildId"
}

$data = Read-ResponseText $responses["/data/rrg.json"] | ConvertFrom-Json
if ($data.source -match "synthetic|sample") {
  throw "Market data source is not live daily data: $($data.source)"
}
$symbols = @($data.symbols.PSObject.Properties)
if ($symbols.Count -lt 30) {
  throw "Market data bundle has too few symbols: $($symbols.Count)"
}
$generatedAt = [DateTime]::ParseExact($data.generatedAt, "yyyy-MM-dd", $null)
$today = (Get-Date).Date
if (($today - $generatedAt.Date).TotalDays -gt 2) {
  throw "Market data bundle is stale: generatedAt=$($data.generatedAt)"
}
if ($buildInfo.dataGeneratedAt -ne $data.generatedAt) {
  throw "Build identity data date does not match RRG data: build=$($buildInfo.dataGeneratedAt) data=$($data.generatedAt)"
}
$spyRows = @($data.symbols.SPY)
if ($spyRows.Count -lt 252) {
  throw "SPY history is too short: $($spyRows.Count)"
}
$spyLatest = [DateTime]::ParseExact($spyRows[-1].date, "yyyy-MM-dd", $null)
if (($today - $spyLatest.Date).TotalDays -gt 5) {
  throw "SPY latest row is stale: $($spyRows[-1].date)"
}

Write-Output (
  "Install preflight passed: " +
  "base=$base urls=$($requiredPaths.Count) " +
  "display=$($manifest.display) generatedAt=$($data.generatedAt) " +
  "symbols=$($symbols.Count) spyLatest=$($spyRows[-1].date) buildId=$($buildInfo.buildId)"
)
