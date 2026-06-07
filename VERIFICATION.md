# Verification Record

Date: 2026-05-30

## GitHub Pages Generated Data Migration

Date: 2026-06-06

The app now reads generated RRG data from `public/data/rrg.json`, published as `data/rrg.json` in `dist`. The browser no longer calls market-data APIs. GitHub Actions includes a weekday post-close data workflow using Stooq first and a Pages deploy workflow that publishes `dist`. The graph starts at `90` to `110` on both axes, chart dragging pans instead of changing date, and two-finger gestures pan and zoom continuously.

Result:

```text
Static verification passed.
Workflow audit passed: updateSchedule=22:30UTC weekdays deploysDist=true
Universe audit passed: sectors=11 industries=29 dataSymbols=41
RRG formula audit passed: points=879760
RRG data freshness audit passed: source=Existing local market-data.json generatedAt=2026-06-06 symbols=41 spyLatest=2026-06-01
Deploy audit passed: files=12 bytes=2050720 source=Existing local market-data.json generatedAt=2026-06-06 buildId=ADEFBA1F9391
Chart controls audit passed: extent 10->9->10 pinch 4.55->9.1 pan 100/100->96.82/102.83 twoFinger 9.1->4.9 plot=862x560 markers 11->10->11
Interaction smoke passed: date Jun 1, 2026 -> May 27, 2026, length=14->50 smooth=20->150, weeklyMax=259 monthlyMax=60, playback=1245->1246, industryMarkers=29 tailDots=493, selected=XTL
iPad touch audit passed: sliderDate=Jun 27, 2022 chartPan=100/100->105.6/100 industryMarkers=29 tailDots=493 markerSelected=SOXX rankSelected=XSD touchPoints=5
Zoom lock audit passed.
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=ADEFBA1F9391 offlineCircles=11 offlineTailDots=187 offlineTails=11
Performance audit passed: navigationMs=439 appLoadMs=125 modelBuildMs=19 svgRenderMs=5 totalBytes=2050720 dataBytes=1968345 resources=7
RRG data update audit passed: cachedGeneratedAt 2026-06-06 -> 2099-01-01
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=397152 sha256=FD2164C60690DEF85CED89027B4DA9B667704D30BD12CB2B3FABF77920550E9C symbols=41 generatedAt=2026-06-06 buildId=ADEFBA1F9391
```

## Chart Hold Pan Update

Date: 2026-06-03

The graph region now supports immediate panning by dragging inside the graph. Dragging moves the visible chart center while preserving the current chart scale. Pinch zoom, date scrub, symbol selection, and the document-level double-tap zoom lock remain active.

Targeted checks:

```powershell
python .\scripts\chart-controls-audit.py
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
python .\scripts\browser-interaction.py
python .\scripts\ipad-touch-audit.py
python .\scripts\zoom-lock-audit.py
```

Result:

```text
Chart controls audit passed: extent 5->4->5 pinch 2.27->4.54 pan 100/100->98.41/101.41 plot=862x560 markers 11->10->11
Static verification passed.
Interaction smoke passed: date Jun 1, 2026 -> May 27, 2026, length=14->50 smooth=20->150, weeklyMax=259 monthlyMax=60, playback=1245->1246, industryMarkers=29 tailDots=493, selected=XTL
iPad touch audit passed: sliderDate=Jun 27, 2022 chartDate=Jun 14, 2022 industryMarkers=29 tailDots=493 markerSelected=SOXX rankSelected=XSD touchPoints=5
Zoom lock audit passed: viewport='width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover' touchAction=manipulation secondTapPrevented=True gesturePrevented=True
```

## Chart Pinch Zoom Update

Date: 2026-06-02

The graph region now supports custom two-finger pinch zooming. Spreading two fingers zooms in by reducing chart extent; pinching inward zooms out by increasing chart extent. The document-level double-tap and gesture zoom lock remains active so the page itself does not magnify.

Targeted checks:

```powershell
python .\scripts\chart-controls-audit.py
python .\scripts\browser-interaction.py
python .\scripts\ipad-touch-audit.py
python .\scripts\zoom-lock-audit.py
```

Result:

```text
Chart controls audit passed: extent 5->4->5 pinch 3.64->5.46 plot=862x560 markers 11->10->11
Interaction smoke passed: date Jun 1, 2026 -> May 27, 2026, length=14->50 smooth=20->150, weeklyMax=259 monthlyMax=60, playback=1245->1246, industryMarkers=29 tailDots=493, selected=XTL
iPad touch audit passed: sliderDate=Jun 27, 2022 chartDate=Jun 6, 2022 industryMarkers=29 tailDots=493 markerSelected=SOXX rankSelected=XSD touchPoints=5
Zoom lock audit passed: viewport='width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover' touchAction=manipulation secondTapPrevented=True gesturePrevented=True
Performance audit passed: navigationMs=270 appLoadMs=75 modelBuildMs=12 svgRenderMs=5 totalBytes=2039526 dataBytes=1960333 resources=7
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=ACBFDF327B03 offlineCircles=11 offlineTailDots=187 offlineTails=11
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=394901 sha256=CD5BD1CCB5C1CC6900BABA5712310736DFCE257212E51C1B738832B5788EE591 symbols=41 generatedAt=2026-06-02 buildId=ACBFDF327B03
```

## Length And Smooth Controls Update

Date: 2026-06-02

The Pine-style formula now exposes both formula inputs. `Length` controls the EMA applied to relative strength in `RS / EMA(RS, length)`, and `Smooth` controls the EMA applied to that ratio and to `RS-Ratio` momentum. Both controls offer `10`, `14`, `20`, `50`, `100`, `150`, and `200`, with defaults of `14` and `20`.

Formula audit:

```powershell
python .\scripts\rrg-formula-audit.py
```

Result:

```text
RRG formula audit passed: points=879760 length10XLK=102.36/100.50 length14XLK=103.24/100.64 length200XLK=113.18/103.57 smooth10XLK=103.69/100.65 smooth20XLK=103.24/100.64 smooth200XLK=100.89/100.68 smooth20XLE=98.11/99.49
Static verification passed.
Interaction smoke passed: date Jun 1, 2026 -> Mar 20, 2025, length=14->50 smooth=20->150, weeklyMax=259 monthlyMax=60, playback=1245->1246, industryMarkers=29 tailDots=493, selected=XTL
Chart controls audit passed: extent 5->4->5 plot=862x560 markers 11->10->11
Layout audit passed: portrait: overflow=-15 sliderY=272 chartY=466, landscape: overflow=-15 sliderY=206 chartY=369
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=114D9111A8F6 offlineCircles=11 offlineTailDots=187 offlineTails=11
Performance audit passed: navigationMs=532 appLoadMs=66 modelBuildMs=8 svgRenderMs=4 totalBytes=2037290 dataBytes=1960333 resources=7
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=394423 sha256=F2F76ECB37A5E3F21B2E18EAFA8F7939BC81E81C29972B648205FBC860AE8203 symbols=41 generatedAt=2026-06-02 buildId=114D9111A8F6
```

## Initial Axis Scale Update

Date: 2026-06-02

The chart now starts at `100 +/- 5`, so both the X-axis `RS-Ratio` and Y-axis `RS-Momentum` initially render from `95` to `105`. Zoom controls step from that starting range by `1` extent unit.

Targeted audit:

```powershell
python .\scripts\chart-controls-audit.py
```

Result:

```text
Chart controls audit passed: extent 5->4->5 plot=862x560 markers 11->10->11
Static verification passed.
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=5123D8634CC2 offlineCircles=11 offlineTailDots=187 offlineTails=11
Performance audit passed: navigationMs=558 appLoadMs=88 modelBuildMs=17 svgRenderMs=6 totalBytes=2036329 dataBytes=1960333 resources=7
Interaction smoke passed: date Jun 1, 2026 -> Jun 9, 2021, ema=20->150, weeklyMax=259 monthlyMax=60, playback=1245->1249, industryMarkers=29 tailDots=493, selected=IGV
Layout audit passed: portrait: overflow=-15 sliderY=240 chartY=434, landscape: overflow=-15 sliderY=240 chartY=434
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=394343 sha256=7680E4F0EABF197089FCD9DA854BD148C838CA7627C556C3568591B8B8D91BA3 symbols=41 generatedAt=2026-06-02 buildId=5123D8634CC2
```

## Pine-Style EMA Formula Update

Date: 2026-06-02

The RRG calculation now mirrors the provided TradingView Pine script. The app builds relative strength versus `SPY` from `asset close / SPY close`, uses a fixed base EMA length of `14`, calculates `RS-Ratio = EMA(relative strength / EMA(relative strength, 14), smooth) * 100`, then calculates `RS-Momentum = RS-Ratio / EMA(RS-Ratio, smooth) * 100`. The user can choose smoothing periods `10`, `20`, `50`, `100`, `150`, and `200`; `20` is the default.

Formula audit:

```powershell
python .\scripts\rrg-formula-audit.py
```

Result:

```text
RRG formula audit passed: points=377040 smooth10XLK=103.69/100.65 smooth20XLK=103.24/100.64 smooth200XLK=100.89/100.68 smooth20XLE=98.11/99.49
```

Deploy package:

```text
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=394319 sha256=6D6CFC48DDDF4F89ABA433844EAFE109AB0393CF6F6C46749C9DDC3FC52D12C9 symbols=41 generatedAt=2026-06-02 buildId=F477A330C633
```

Fresh checks after the Pine-style formula update:

```text
Static verification passed.
Performance audit passed: navigationMs=8457 appLoadMs=3812 modelBuildMs=318 svgRenderMs=187 totalBytes=2036255 dataBytes=1960333 resources=5
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=F477A330C633 offlineCircles=11 offlineTailDots=187 offlineTails=11
Install preflight passed: base=http://127.0.0.1:4183 urls=6 display=standalone generatedAt=2026-06-02 symbols=41 spyLatest=2026-06-01 buildId=F477A330C633
Interaction smoke passed: date Jun 1, 2026 -> Mar 20, 2025, ema=20->150, weeklyMax=259 monthlyMax=60, playback=1245->1246, industryMarkers=29 tailDots=493, selected=XTL
```

## Previous JdK-Style EMA Formula Update

Date: 2026-05-31

The RRG calculation now uses a JdK-style EMA-smoothed approximation. The app builds relative strength versus `SPY` from `asset close / SPY close`, compares it with an EMA baseline selected by the user, normalizes the deviation, and maps it to `RS-Ratio` centered at `100`. `RS-Momentum` compares `RS-Ratio` with its own EMA baseline, normalizes that deviation, and maps it around `100`. The user can choose EMA periods `10`, `20`, `50`, `100`, `150`, and `200`; `50` is the default.

Formula audit:

```powershell
python .\scripts\rrg-formula-audit.py
```

Result:

```text
RRG formula audit passed: points=371040 ema10XLK=118.01/111.33 ema50XLK=117.58/94.34 ema200XLK=135.34/122.65 ema50XLE=89.06/103.80
```

Deploy package:

```text
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=394531 sha256=D136B3E88569EDE95EC63FFB11D8A116E96E40444956E0318DBC8CA5CEDA824F symbols=41 generatedAt=2026-05-30 buildId=3C8AC6DD24C1
```

Fresh checks after the EMA selector update:

```text
Static verification passed.
Performance audit passed: navigationMs=8357 appLoadMs=3870 modelBuildMs=463 svgRenderMs=191 totalBytes=2037904 dataBytes=1960395 resources=5
Interaction smoke passed: date May 29, 2026 -> Mar 19, 2025, ema=50->150, weeklyMax=251 monthlyMax=51, playback=1237->1238, industryMarkers=29 tailDots=493, selected=XSD
Chart controls audit passed: extent 50->45->50 plot=862x560 markers 11->10->11
Zoom lock audit passed: viewport='width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover' touchAction=manipulation secondTapPrevented=True gesturePrevented=True
iPad touch audit passed: sliderDate=Jul 5, 2022 chartDate=Jun 13, 2022 industryMarkers=29 tailDots=493 markerSelected=IHF rankSelected=IGV touchPoints=5
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=3C8AC6DD24C1 offlineCircles=11 offlineTailDots=187 offlineTails=11
PWA audit passed: display=standalone icons=3 installabilityErrors=0 serviceWorkerReady=True caches=1 launchMode=browser
Offline audit passed: cacheCount=1 offlineCircles=11 offlineTailDots=187 offlineTails=11
Layout audit passed: portrait: overflow=-15 sliderY=240 chartY=434, landscape: overflow=-15 sliderY=184 chartY=347
Accessibility audit passed: buttons=33 sliders=2 chartNamed=True dateSliderNamed=True
Pointer smoke passed: sliderDate=May 25, 2022 chartDate=May 9, 2022 industryMarkers=29 tailDots=493
Install preflight passed: base=http://127.0.0.1:4183 urls=6 display=standalone generatedAt=2026-05-30 symbols=41 spyLatest=2026-05-29 buildId=3C8AC6DD24C1
Visual audit passed: portrait: unique=7535 chartPixels=240162 colored=82608, landscape: unique=6393 chartPixels=155238 colored=42883
```

## Previous Return-Relative Formula Update

Date: 2026-05-31

The RRG calculation now uses return-relative price performance instead of Wilder RSI. The app compares each asset's price change with `SPY` over the timeframe lookback as `(1 + asset return) / (1 + SPY return) - 1`, maps that value to a 0-100 `RS-Ratio` centered at `50`, then maps the change in that relative performance versus an earlier observation to 0-100 `RS-Momentum`.

Formula audit:

```powershell
python .\scripts\rrg-formula-audit.py
```

Result:

```text
RRG formula audit passed: points=57400 dailyXLE=39.84/12.08 dailyXLK=89.97/80.77 weeklyXLE=70.24/16.71 monthlyXLE=62.22/56.92
```

Full local verification suite:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-all-checks.ps1
```

Result:

```text
All checks passed.
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=393748 sha256=BD6C9B4FDE3CA53E52A72166AF74C4BD1554BBF89645FEA2B9C90614CC947E8C symbols=41 generatedAt=2026-05-30 buildId=BBB0E7858937
```

## Previous Formula Update

Date: 2026-05-31

The RRG calculation now uses a common Wilder RSI normalization instead of the earlier calibrated blend. The app builds relative strength versus `SPY` from `asset close / SPY close`, converts it to a 0-100 `RS-Ratio` with 14-period Wilder RSI, then derives 0-100 `RS-Momentum` with 7-period Wilder RSI of the `RS-Ratio` line. The chart is centered at `50`.

Formula audit:

```powershell
python .\scripts\rrg-formula-audit.py
```

Result:

```text
RRG formula audit passed: verifies Wilder RSI behavior and 0-100 output ranges
```

Rebuilt deployment artifact:

```text
Deploy audit passed: files=12 bytes=2030416 source=Yahoo Finance daily adjusted chart data generatedAt=2026-05-30 buildId=06B6C76ADB94
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=392901 sha256=8F037D2A2DBE078C81D461DEED2E96D3D67BF12979246329E282A56B7B677323 symbols=41 generatedAt=2026-05-30 buildId=06B6C76ADB94
```

Fresh checks after formula update:

```text
Static verification passed.
Browser smoke passed: circles=11 tailDots=187 tails=12 domBytes=49481
Interaction smoke passed: date May 29, 2026 -> Apr 2, 2024, weeklyMax=211 monthlyMax=30, playback=1077->1078, industryMarkers=29 tailDots=493, selected=XTL
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=06B6C76ADB94 offlineCircles=11 offlineTailDots=187 offlineTails=11
Accessibility audit passed: buttons=20 sliders=2 chartNamed=True dateSliderNamed=True
Layout audit passed: portrait: overflow=-15 sliderY=218 chartY=412, landscape: overflow=-15 sliderY=156 chartY=319
PWA audit passed: display=standalone icons=3 installabilityErrors=0 serviceWorkerReady=True caches=1 launchMode=browser
Visual audit passed: portrait: unique=3586 chartPixels=250356 colored=84107, landscape: unique=3270 chartPixels=173287 colored=50308
Pointer smoke passed: sliderDate=Nov 29, 2022 chartDate=Nov 10, 2022 industryMarkers=29 tailDots=493
iPad touch audit passed: sliderDate=Jan 3, 2023 chartDate=Dec 12, 2022 industryMarkers=29 tailDots=493 markerSelected=XTL rankSelected=SOXX touchPoints=5
Performance audit passed: renderMs=495 totalBytes=2030416 dataBytes=1960395 resources=7
```

## Proved Locally

Static verifier:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
```

Result:

```text
Static verification passed.
```

Full local verification suite:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-all-checks.ps1
```

Result:

```text
All checks passed.
```

Local HTTP smoke test:

```text
app=200 data=200 dataBytes=786700
```

Bundled market data:

```text
source: Yahoo Finance daily chart data
generatedAt: 2026-05-30
symbols: 41
SPY first row: 2023-07-18 close 454.19
SPY latest row: 2026-05-29 close 756.48
```

Data freshness audit:

```powershell
python .\scripts\data-freshness-audit.py
```

Result:

```text
Data freshness audit passed: source=Yahoo Finance daily chart data generatedAt=2026-05-30 symbols=41 spyLatest=2026-05-29
```

Universe coverage audit:

```powershell
python .\scripts\universe-audit.py
```

Result:

```text
Universe audit passed: sectors=11 industries=29 dataSymbols=41
```

GitHub workflow audit:

```powershell
python .\scripts\workflow-audit.py
```

Result:

```text
Workflow audit passed: updateSchedule=30 23 weekdays deploySchedule=45 23 weekdays deploysDist=true
```

Target device evidence:

```text
A2993 maps to iPad mini (A17 Pro) in Apple's iPad model identifier list.
iPad mini (A17 Pro) tech specs list an 8.3-inch Liquid Retina display with 2266-by-1488 resolution at 326 ppi.
Local audits use 744 x 1133 and 1133 x 744 CSS-pixel viewport proxies for iPad mini portrait and landscape.
```

Deployment artifact audit:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-audit.ps1
```

Result:

```text
Deploy audit passed: files=12 bytes=1133399 source=Yahoo Finance daily chart data generatedAt=2026-05-30 buildId=73892FFAD0CE
```

Deployment package audit:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package-dist.ps1
```

Result:

```text
Deploy package passed: zip=C:\Users\lawre\Documents\RGG\deploy\rgg-rotation-ipad-pwa.zip bytes=190952 sha256=9384B7B57C9BD3B59B0105AFD11BBAC117BBF2B7D772EF957F44A98127571CF2 symbols=41 generatedAt=2026-05-30 buildId=73892FFAD0CE
```

The package hash was verified deterministic by running `scripts/package-dist.ps1` twice against the same app/data state and comparing SHA256 output.

Install URL preflight:

```powershell
python .\scripts\install-preflight-local.py
```

Result:

```text
Install preflight passed: base=http://127.0.0.1:4183 urls=6 display=standalone generatedAt=2026-05-30 symbols=41 spyLatest=2026-05-29 buildId=73892FFAD0CE
```

iPad QR handoff audit:

```powershell
python .\scripts\qr-handoff-audit.py
```

Result:

```text
QR handoff audit passed: bytes=19352 rects=339 sha256=84E895C132181177D11CA81B886EE8C24D064F47B910CBD98990C8D9EBCA9BCA
```

Performance and payload audit:

```powershell
python .\scripts\performance-audit.py
```

Result:

```text
Performance audit passed: renderMs=428 totalBytes=1133399 dataBytes=1074215 resources=7
```

Deployment artifact runtime audit:

```powershell
python .\scripts\dist-runtime-audit.py
```

Result:

```text
Dist runtime audit passed: installabilityErrors=0 cacheCount=1 buildId=73892FFAD0CE offlineCircles=11 offlineTailDots=187 offlineTails=11
```

App shell update audit:

```powershell
python .\scripts\app-shell-update-audit.py
```

Result:

```text
App shell update audit passed: cachedStyles app-shell-audit-initial -> app-shell-audit-updated
```

Daily data update audit:

```powershell
python .\scripts\data-update-audit.py
```

Result:

```text
Data update audit passed: cachedGeneratedAt 2026-05-30 -> 2099-01-01
```

JavaScript execution/render simulation:

```text
Rendered with generated RRG data: svgChildren=272, status=RRG data loaded
```

Headless browser DOM smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\browser-smoke.ps1
```

Result:

```text
Browser smoke passed: circles=11 tailDots=187 tails=11 domBytes=41703
```

iPad-mini viewport screenshot capture:

```powershell
python .\scripts\browser-capture.py --width 744 --height 1133 --scale 1 --out rgg-ipad-mini-portrait.png
python .\scripts\browser-capture.py --width 1133 --height 744 --scale 1 --out rgg-ipad-mini-landscape.png
```

Result:

```text
Portrait screenshot captured: bytes=80643 markers=11 tails=11 tailDots=187
Landscape screenshot captured: bytes=69781 markers=11 tails=11 tailDots=187
```

iPad screenshot visual audit:

```powershell
python .\scripts\visual-audit.py
```

Result:

```text
Visual audit passed: portrait: unique=7905 chartPixels=243725 colored=89516, landscape: unique=7623 chartPixels=162438 colored=47992
```

Browser interaction smoke test:

```powershell
python .\scripts\browser-interaction.py
```

Result:

```text
Interaction smoke passed: date May 29, 2026 -> Apr 16, 2025, playback=555->556, industryMarkers=29 tailDots=493, selected=XTL
```

Browser pointer smoke test:

```powershell
python .\scripts\browser-pointer.py
```

Result:

```text
Pointer smoke passed: sliderDate=Aug 7, 2024 chartDate=Jul 22, 2024 industryMarkers=29 tailDots=493
```

iPad touch emulation audit:

```powershell
python .\scripts\ipad-touch-audit.py
```

Result:

```text
iPad touch audit passed: sliderDate=Aug 23, 2024 chartDate=Aug 5, 2024 industryMarkers=29 tailDots=493 markerSelected=XTL rankSelected=XSW touchPoints=5
```

iPad viewport layout audit:

```powershell
python .\scripts\layout-audit.py
```

Result:

```text
Layout audit passed: portrait: overflow=-15 sliderY=186 chartY=300, landscape: overflow=-15 sliderY=193 chartY=307
```

Accessibility audit:

```powershell
python .\scripts\accessibility-audit.py
```

Result:

```text
Accessibility audit passed: buttons=17 sliders=2 chartNamed=True dateSliderNamed=True
```

PWA readiness audit:

```powershell
python .\scripts\pwa-audit.py
```

Result:

```text
PWA audit passed: display=standalone icons=3 installabilityErrors=0 serviceWorkerReady=True caches=1 launchMode=browser
```

Offline reload audit:

```powershell
python .\scripts\offline-audit.py
```

Result:

```text
Offline audit passed: cacheCount=1 offlineCircles=11 offlineTailDots=187 offlineTails=11
```

## Requirement Mapping

- Interactive RGG chart: verified by `index.html`, `src/app.js`, and render simulation creating SVG chart children.
- Target iPad model: documented in `TARGET_DEVICE.md` with Apple references showing A2993 is iPad mini (A17 Pro) and the display class/resolution used to choose the local viewport proxies.
- Rendered browser output: verified by `scripts/browser-smoke.ps1` finding 11 sector markers, 187 tail history dots, 11 tails, quadrant labels, and the daily-data status in the post-JavaScript DOM.
- iPad-mini viewport screenshots: verified by `scripts/browser-capture.py` capturing portrait and landscape PNGs through Chrome DevTools and confirming 11 sector markers plus 11 RGG tails and 187 fading tail history dots.
- iPad-mini screenshot visual quality: verified by `scripts/visual-audit.py` checking the captured PNG dimensions, color diversity, light chart area, dark app chrome, and all four RRG quadrant fill colors.
- GICS sector rotation: verified by sector ETF universe in `src/app.js` and `scripts/universe-audit.py` requiring all 11 sector proxies, each labeled `GICS Sector` in the user-facing detail panel.
- Industry rotation: verified by industry ETF universe in `src/app.js` and `scripts/universe-audit.py` requiring at least 29 unique industry proxies, all 11 parent GICS-sector group labels, and matching updater and bundled-data symbols.
- Date slider: verified by `dateSlider` markup, previous/play/next timeline controls, input event wiring, and render simulation with `sliderMax=559`.
- Date slider interaction: verified by `scripts/browser-interaction.py` changing the selected date from May 29, 2026 to Apr 16, 2025 and playback from slider index 555 to 556 in a real browser.
- Pointer interaction: verified by `scripts/browser-pointer.py` using browser-level mouse drag/tap events to change the date slider, scrub dates inside the chart, and switch to industries.
- Fixed chart scale and visibility toggles: verified by `scripts/chart-controls-audit.py` checking that date changes do not auto-scale, pinch gestures adjust chart extent, previous chart scaling geometry is restored, individual rows can be hidden/restored, Hide All and Show All work, and the Indices universe renders SPX, NDX, IWM, and DJI.
- iPad touch interaction: verified by `scripts/ipad-touch-audit.py` running Chrome mobile/touch emulation, dispatching touch drag events on the date slider and chart, tapping Industries, tapping an SVG marker, and tapping a ranking row.
- iPad viewport ergonomics: verified by `scripts/layout-audit.py` checking portrait and landscape widths for no horizontal overflow, visible date slider before the chart, chart visibility in the first viewport, and reasonable button target sizes.
- iPad performance budget: verified by `scripts/performance-audit.py` checking the `dist` payload size, market-data payload size, resource count, and browser render time on the iPad mini viewport proxy.
- iPad Safari touch polish: verified by `scripts/verify.ps1` and `scripts/zoom-lock-audit.py` checking fixed text-size adjustment, transparent tap highlights, touch-oriented range controls, double-tap zoom prevention, and momentum scrolling in the ranking list.
- Accessibility basics: verified by `scripts/accessibility-audit.py` checking named controls, two accessible sliders, and a named RGG chart in Chrome's accessibility tree.
- Industry interaction: verified by `scripts/browser-interaction.py` switching from 11 sector markers to 29 industry markers and selecting XTL from the ranking list.
- StockCharts RRG reference behavior: documented in `REFERENCE_ALIGNMENT.md` and implemented with RS-Ratio on the horizontal axis, RS-Momentum on the vertical axis, four 50-centered quadrants, fading tail history dots, tails, a tail-length slider, a horizontal date slider, previous/next stepping, and timeline playback.
- RRG tail direction readability: verified by `scripts/browser-smoke.ps1`, `scripts/browser-capture.py`, and pointer/interaction audits checking endpoint markers separately from fading tail history dots.
- Free daily updated data: verified by `scripts/update_rrg_data.py`, current `public/data/rrg.json`, and `.github/workflows/update-data.yml`.
- Hosted daily data deployment: verified by `.github/workflows/deploy-pages.yml` preparing `dist` and deploying that artifact to GitHub Pages; `scripts/workflow-audit.py` checks this explicitly.
- Fresh non-synthetic daily data bundle: verified by `scripts/data-freshness-audit.py` checking generation date, SPY latest row, symbol count, minimum history length, and symbol-date alignment.
- Daily data freshness after install: verified by `scripts/verify.ps1` checking that `service-worker.js` uses a network-first strategy for `data/rrg.json`, with cached fallback for offline use.
- Daily data cache refresh: verified by `scripts/data-update-audit.py` simulating a newly deployed `rrg.json` and confirming the controlled browser page updates the Cache Storage copy to `2099-01-01`.
- Installed app shell freshness after deployment: verified by `service-worker.js` using network-first caching for same-origin app files and `scripts/app-shell-update-audit.py` simulating an updated deployed CSS file and confirming the Cache Storage copy changes from `app-shell-audit-initial` to `app-shell-audit-updated`.
- Installable iPad app path: verified by PWA manifest, iPad standalone meta tags, PNG touch icons, service worker, clean `dist` artifact from `scripts/prepare-dist.ps1`, deterministic verified static-host ZIP from `scripts/package-dist.ps1`, build identity metadata, `.nojekyll` marker for direct GitHub Pages static hosting, GitHub Pages deployment workflow, `scripts/pwa-audit.py` confirming standalone manifest parsing, zero Chrome installability errors, service-worker readiness, Cache Storage setup, and the runtime `data-launch-mode` marker, and `scripts/dist-runtime-audit.py` proving the hosted artifact itself renders and reloads offline.
- Hosted install URL readiness: verified by `scripts/install-preflight.ps1` checking the iPad install URLs, standalone manifest, icons, service-worker update strategy, and fresh non-synthetic daily market data before the URL is opened on the iPad.
- iPad handoff: supported by `scripts/ipad-qr-handoff.py`, which creates a local QR handoff page for opening the hosted app URL in iPad Safari.
- Offline Home Screen resilience: verified by `scripts/offline-audit.py` loading the app once, emulating offline network conditions, reloading, and confirming the chart still renders 11 markers, 187 tail history dots, and 11 tails from the service-worker cache.

## Environment Note

Chrome emitted iPad-mini viewport screenshots in this desktop environment. The updated objective does not require a physical iPad report; installability is verified by the PWA, package, local preflight, runtime, offline, iPad viewport, and touch-emulation audits above.
