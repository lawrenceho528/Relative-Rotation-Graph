$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$requiredFiles = @(
  "index.html",
  ".nojekyll",
  "styles.css",
  "src/app.js",
  "public/data/rrg.json",
  "REFERENCE_ALIGNMENT.md",
  "scripts/accessibility-audit.py",
  "scripts/app-shell-update-audit.py",
  "scripts/update_rrg_data.py",
  "scripts/visual-audit.py",
  "scripts/workflow-audit.py",
  "scripts/browser-smoke.ps1",
  "scripts/browser-capture.py",
  "scripts/browser-interaction.py",
  "scripts/browser-pointer.py",
  "scripts/data-freshness-audit.py",
  "scripts/data-update-audit.py",
  "scripts/deploy-audit.ps1",
  "scripts/dist-runtime-audit.py",
  "scripts/install-preflight.ps1",
  "scripts/install-preflight-local.py",
  "scripts/ipad-qr-handoff.py",
  "scripts/ipad-touch-audit.py",
  "scripts/layout-audit.py",
  "scripts/offline-audit.py",
  "scripts/performance-audit.py",
  "scripts/pwa-audit.py",
  "scripts/qr-handoff-audit.py",
  "scripts/package-dist.ps1",
  "scripts/prepare-dist.ps1",
  "scripts/run-all-checks.ps1",
  "scripts/universe-audit.py",
  ".github/workflows/deploy-pages.yml",
  ".github/workflows/update-data.yml",
  "IPAD_INSTALL_CHECKLIST.md",
  "TARGET_DEVICE.md",
  "manifest.webmanifest",
  "service-worker.js",
  "icons/icon.svg",
  "icons/apple-touch-icon.png",
  "icons/icon-192.png",
  "icons/icon-512.png"
)

foreach ($file in $requiredFiles) {
  $path = Join-Path $root $file
  if (-not (Test-Path $path)) {
    throw "Missing required file: $file"
  }
}

$html = Get-Content (Join-Path $root "index.html") -Raw
$css = Get-Content (Join-Path $root "styles.css") -Raw
$js = Get-Content (Join-Path $root "src/app.js") -Raw
$manifest = Get-Content (Join-Path $root "manifest.webmanifest") -Raw | ConvertFrom-Json
$serviceWorker = Get-Content (Join-Path $root "service-worker.js") -Raw
$updater = Get-Content (Join-Path $root "scripts/update_rrg_data.py") -Raw
$targetDevice = Get-Content (Join-Path $root "TARGET_DEVICE.md") -Raw
$referenceAlignment = Get-Content (Join-Path $root "REFERENCE_ALIGNMENT.md") -Raw

function Assert-Check {
  param(
    [bool] $Condition,
    [string] $Label
  )

  if (-not $Condition) {
    throw "Verification failed: $Label"
  }

  Write-Output "OK: $Label"
}

Assert-Check ($html.Contains('name="apple-mobile-web-app-capable" content="yes"')) "iPad standalone meta tag"
Assert-Check ($html.Contains('maximum-scale=1') -and $html.Contains('user-scalable=no')) "double tap zoom locked viewport"
Assert-Check ($html.Contains('rel="manifest"')) "web app manifest link"
Assert-Check ($html.Contains('<title>RRG</title>') -and $html.Contains('apple-mobile-web-app-title" content="RRG"') -and $html.Contains('<h1>RRG</h1>')) "RRG app name"
Assert-Check ($html.Contains('./icons/apple-touch-icon.png')) "iPad PNG touch icon"
Assert-Check ($html.Contains('id="dateSlider"')) "date slider control"
Assert-Check ($html.Contains('data-universe="sectors"') -and $html.Contains('data-universe="industries"') -and $html.Contains('data-universe="indices"')) "sectors industries and indices universe controls"
Assert-Check ($html.Contains('data-timeframe="daily"') -and $html.Contains('data-timeframe="weekly"') -and $html.Contains('data-timeframe="monthly"')) "daily weekly monthly timeframe controls"
Assert-Check ($html.Contains('id="benchmarkBar"')) "SPY benchmark price bar"
Assert-Check ($html.Contains('id="spySparkline"')) "SPY price sparkline"
Assert-Check ($html.Contains('id="lastUpdated"')) "visible generated data timestamp"
Assert-Check ($html.Contains('id="stepBackButton"') -and $html.Contains('id="playPauseButton"') -and $html.Contains('id="stepForwardButton"')) "timeline transport controls"
Assert-Check ($html.Contains('id="lengthPeriod"') -and $html.Contains('id="smoothPeriod"') -and $html.Contains('value="14" selected') -and $html.Contains('value="20" selected') -and $html.Contains('value="200"')) "Length and Smooth period selectors"
Assert-Check (-not ($html.Contains('id="zoomInButton"') -or $html.Contains('id="zoomOutButton"') -or $html.Contains('id="zoomValue"'))) "manual zoom buttons removed"
Assert-Check ($html.Contains('id="hideAllButton"') -and $html.Contains('id="showAllButton"')) "bulk hide and show controls"
Assert-Check ($html.Contains('id="rrgChart"')) "interactive RGG chart"
Assert-Check ($manifest.name -eq "RRG" -and $manifest.short_name -eq "RRG") "RRG manifest app name"
Assert-Check ($manifest.display -eq "standalone") "standalone manifest display"
Assert-Check ([bool]($manifest.icons | Where-Object { $_.src -eq "./icons/icon-192.png" })) "192px manifest icon"
Assert-Check ([bool]($manifest.icons | Where-Object { $_.src -eq "./icons/icon-512.png" })) "512px manifest icon"
Assert-Check ($serviceWorker.Contains('self.addEventListener("fetch"')) "service worker fetch cache"
Assert-Check (-not $serviceWorker.Contains('stooq.com/q/d/l/')) "no browser market data provider cache"
Assert-Check ($serviceWorker.Contains('./data/rrg.json')) "same-origin RRG data cache"
Assert-Check ($serviceWorker.Contains('build-info.json')) "build identity cache"
Assert-Check ($serviceWorker.Contains('url.pathname.endsWith("/data/rrg.json")') -and $serviceWorker.Contains('networkFirst(request, cacheKey)')) "generated RRG data network-first cache strategy"
Assert-Check ($serviceWorker.Contains('new URL("data/rrg.json", self.registration.scope)')) "canonical RRG data cache key"
Assert-Check ($serviceWorker.Contains('url.origin === self.location.origin') -and $serviceWorker.Contains('event.respondWith(networkFirst(request))')) "same-origin app shell network-first cache strategy"
Assert-Check ($updater.Contains('class TiingoProvider') -and $updater.Contains('TIINGO_API_KEY') -and $updater.Contains('default="tiingo"') -and $updater.Contains('class StooqProvider') -and $updater.Contains('https://stooq.com/q/d/l/')) "Tiingo-first updater with Stooq optional fallback"
Assert-Check (Test-Path (Join-Path $root "scripts/app-shell-update-audit.py")) "app shell update audit"
Assert-Check (Test-Path (Join-Path $root "scripts/visual-audit.py")) "iPad screenshot visual audit"
Assert-Check (Test-Path (Join-Path $root "scripts/install-preflight.ps1")) "iPad install URL preflight"
Assert-Check (Test-Path (Join-Path $root "scripts/install-preflight-local.py")) "local install URL preflight runner"
Assert-Check (Test-Path (Join-Path $root "scripts/ipad-qr-handoff.py")) "iPad QR handoff helper"
Assert-Check (Test-Path (Join-Path $root "scripts/qr-handoff-audit.py")) "iPad QR handoff audit"
Assert-Check (Test-Path (Join-Path $root "scripts/package-dist.ps1")) "verified deploy package helper"
Assert-Check (Test-Path (Join-Path $root "scripts/data-freshness-audit.py")) "daily data freshness audit"
Assert-Check (Test-Path (Join-Path $root "scripts/universe-audit.py")) "sector and industry universe audit"
Assert-Check (Test-Path (Join-Path $root "scripts/workflow-audit.py")) "GitHub workflow audit"
Assert-Check (Test-Path (Join-Path $root "scripts/performance-audit.py")) "iPad performance and payload audit"
Assert-Check (Test-Path (Join-Path $root "scripts/ipad-touch-audit.py")) "iPad touch emulation audit"
Assert-Check (Test-Path (Join-Path $root ".github/workflows/deploy-pages.yml")) "GitHub Pages deployment workflow"
Assert-Check (Test-Path (Join-Path $root ".github/workflows/update-data.yml")) "daily generated RRG data workflow"
Assert-Check (Test-Path (Join-Path $root "IPAD_INSTALL_CHECKLIST.md")) "iPad install checklist"
Assert-Check ($targetDevice.Contains('A2993') -and $targetDevice.Contains('iPad mini (A17 Pro)')) "target A2993 iPad mini documented"
Assert-Check ($targetDevice.Contains('2266-by-1488') -and $targetDevice.Contains('744 x 1133') -and $targetDevice.Contains('1133 x 744')) "target display and viewport proxy documented"
Assert-Check ($referenceAlignment.Contains('stockcharts.com/freecharts/rrg') -and $referenceAlignment.Contains('Horizontal time scrubbing') -and $referenceAlignment.Contains('TradingView Pine-style')) "StockCharts RRG reference alignment documented"
Assert-Check (-not $js.Contains('stooq.com/q/d/l/') -and -not $js.Contains('query1.finance.yahoo.com') -and -not $js.Contains('TIINGO_API_KEY')) "no market data API calls or keys in frontend"
Assert-Check ($js.Contains('DATA_URLS = ["./data/rrg.json", "./public/data/rrg.json"]') -and $js.Contains('loadSameOriginHistories')) "generated RRG JSON loader"
Assert-Check ($js.Contains('generatedAt: payload.generatedAt') -and $js.Contains('function updateLastUpdated') -and $js.Contains('RRG data loaded')) "generated data freshness status"
Assert-Check ($js.Contains('const TIMEFRAMES') -and $js.Contains('weekly:') -and $js.Contains('monthly:')) "weekly and monthly timeframe models"
Assert-Check ($js.Contains('function sampleHistory') -and $js.Contains('function getWeekKey')) "daily data resampling"
Assert-Check ($js.Contains('function updateBenchmarkBar') -and $js.Contains('benchmarkCloses')) "SPY price level display"
Assert-Check ($js.Contains('function renderSpySparkline') -and $js.Contains('dataset.spySparkline')) "SPY price line rendering"
Assert-Check ($js.Contains('Generated RRG data missing benchmark') -and $js.Contains('.filter((asset) => histories.has(asset.symbol))')) "generated data skips missing non-benchmark symbols"
Assert-Check ($js.Contains('SCALE_LIMITS = { min: 1, max: 50, step: 1, initial: 10 }') -and $js.Contains('chartExtent: SCALE_LIMITS.initial') -and $js.Contains('chartCenterX: CHART_CENTER') -and $js.Contains('chartCenterY: CHART_CENTER') -and $js.Contains('const extent = state.chartExtent') -and $js.Contains('dataset.chartMin') -and $js.Contains('dataset.chartMax') -and $js.Contains('dataset.chartMinY') -and $js.Contains('dataset.chartMaxY') -and -not $js.Contains('function getExtent')) "fixed chart scale starts at 90-110 with pannable viewport center"
Assert-Check ($js.Contains('const plot = { left: 74, top: 40, width: 862, height: 560 }') -and $js.Contains('dataset.plotWidth') -and -not $js.Contains('X_AXIS_TO_Y_AXIS_SCALE')) "previous chart scaling geometry"
Assert-Check ($js.Contains('function setChartExtent') -and $js.Contains('function updateZoomOutput') -and -not ($js.Contains('zoomInButton') -or $js.Contains('zoomOutButton') -or $js.Contains('zoomValue'))) "gesture-only chart scale controls"
Assert-Check ($js.Contains('activePointers: new Map()') -and $js.Contains('function startChartPinch') -and $js.Contains('function updateChartPinch') -and $js.Contains('pointerDistance') -and $js.Contains('pointerMidpoint') -and $js.Contains('setChartExtent(state.pinchZoom.startExtent / zoomRatio)')) "two-finger continuous chart pinch and pan"
Assert-Check (-not $js.Contains('CHART_PAN_HOLD_DELAY') -and -not $js.Contains('scheduleChartPan') -and $js.Contains('function startChartPan') -and $js.Contains('function updateChartPan') -and $js.Contains('state.chartCenterX') -and $js.Contains('state.chartCenterY')) "immediate single-finger chart pan"
Assert-Check (-not $js.Contains('setDateIndex(state.dragStart.index')) "chart drag no longer changes date"
Assert-Check ($js.Contains('hiddenSymbols: new Set()') -and $js.Contains('function toggleSymbolVisibility') -and $js.Contains('function hideAllSymbols') -and $js.Contains('function showAllSymbols') -and $js.Contains('visibility-toggle')) "show hide symbol controls"
Assert-Check ($js.Contains('sectors: [') -and $js.Contains('industries: [') -and $js.Contains('indices: [') -and $js.Contains('"SPX"') -and $js.Contains('"NDX"') -and $js.Contains('"IWM"') -and $js.Contains('"DJI"')) "sector industry and indices universes"
Assert-Check ($js.Contains('function assetSubtitle') -and $js.Contains('industry proxy') -and $js.Contains('GICS Sector') -and $js.Contains('Market Index')) "user-visible GICS sector industry and index context"
Assert-Check ($js.Contains('function computeRrgPoints')) "RRG calculation"
Assert-Check ($js.Contains('RRG_PERIODS = [10, 14, 20, 50, 100, 150, 200]') -and $js.Contains('DEFAULT_LENGTH_PERIOD = 14') -and $js.Contains('DEFAULT_SMOOTH_PERIOD = 20') -and $js.Contains('lengthPeriod: DEFAULT_LENGTH_PERIOD') -and $js.Contains('smoothPeriod: DEFAULT_SMOOTH_PERIOD') -and $js.Contains('CHART_CENTER = 100')) "Pine-style 100-centered Length and Smooth configuration"
Assert-Check ($js.Contains('function ema') -and $js.Contains('relativeStrengthRatio') -and $js.Contains('smoothedRelativeStrength = ema(relativeStrength, lengthPeriod)') -and $js.Contains('ema(relativeStrengthRatio, smoothPeriod)') -and $js.Contains('ratioValue / smoothedRatioValue')) "Pine-style user-defined Length and Smooth formula"
Assert-Check (-not ($js.Contains('function normalizeSeries') -or $js.Contains('function toJdkValue') -or $js.Contains('RRG_BASE_LENGTH') -or $js.Contains('NORMALIZATION_SCALE') -or $js.Contains('MIN_NORMALIZATION_SAMPLES') -or $js.Contains('function wilderRsi') -or $js.Contains('function rsiFromAverages') -or $js.Contains('calculateRelativePerformance') -or $js.Contains('stockReturn') -or $js.Contains('benchmarkReturn') -or $js.Contains('ratioPeriod') -or $js.Contains('momentumPeriod') -or $js.Contains('trendWeight') -or $js.Contains('performanceWeight') -or $js.Contains('logRelativeStrength'))) "retired fixed-base z-score RSI return-relative and calibrated blend formulas removed"
Assert-Check (Test-Path (Join-Path $root "scripts/rrg-formula-audit.py")) "RRG formula audit"
Assert-Check (Test-Path (Join-Path $root "scripts/zoom-lock-audit.py")) "double tap zoom lock audit"
Assert-Check ($js.Contains('function addSmoothPath') -and $js.Contains('function smoothPath') -and $js.Contains('dataset.tailPath')) "smooth RRG tail curves"
Assert-Check ($js.Contains('function animateVisualDate') -and $js.Contains('requestAnimationFrame') -and $js.Contains('visualDateIndex')) "animated timeline marker movement"
Assert-Check ($js.Contains('function addTailDots') -and $js.Contains('dataset.tailDot')) "RRG tail history dots"
Assert-Check ($js.Contains('function preventDoubleTapZoom') -and $js.Contains('DOUBLE_TAP_ZOOM_DELAY') -and $js.Contains('gesturestart')) "double tap zoom prevention"
Assert-Check ($js.Contains('els.dateSlider.addEventListener("input"')) "date slider interaction"
Assert-Check ($js.Contains('function startPlayback') -and $js.Contains('function stepDate')) "timeline step and playback interaction"
Assert-Check ($js.Contains('pointerdown') -and $js.Contains('pointermove')) "touch chart interaction"
Assert-Check ($js.Contains('function updateLaunchMode') -and $js.Contains('dataset.launchMode') -and $js.Contains('display-mode: standalone')) "runtime iPad launch-mode marker"
Assert-Check ($js.Contains('function loadBuildInfo') -and $js.Contains('dataset.buildId')) "runtime build identity marker"
Assert-Check ($css.Contains('-webkit-text-size-adjust: 100%') -and $css.Contains('-webkit-tap-highlight-color: transparent') -and $css.Contains('touch-action: manipulation') -and $css.Contains('.ema-control')) "iPad Safari touch/text polish"
Assert-Check ($css.Contains('-webkit-overflow-scrolling: touch') -and $css.Contains('touch-action: pan-x') -and $css.Contains('touch-action: none')) "iPad touch scrolling and chart pinch controls"
Assert-Check ($css.Contains('@media (max-width: 900px)')) "iPad mini responsive layout"

Write-Output "Static verification passed."
