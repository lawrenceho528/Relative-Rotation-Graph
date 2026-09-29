# RRG

Interactive iPad-ready Relative Rotation Graph for U.S. equity sector, industry, theme, and index rotation.

## What It Builds

- A static Progressive Web App that can be hosted on GitHub Pages and added to the iPad Home Screen from Safari.
- RRG-style sector, industry, theme, and index rotation against `SPY`.
- Real-data-only updating: every published price row is downloaded Tiingo EOD history; the pipeline never generates or substitutes synthetic market data.
- Date control through the timeline slider and previous/play/next buttons.
- Graph panning by pressing and dragging inside the chart.
- Continuous two-finger graph zoom and pan inside the chart.
- Generated same-origin RRG data from `public/data/rrg.json`; the browser does not call market-data APIs.
- Network-first app/data caching with offline fallback after the app has been opened once.

## Local Development

The generated data file `public/data/rrg.json` is the persisted real-history cache. Refresh it from Tiingo (the key is read from `TIINGO_API_KEY`):

```powershell
$env:TIINGO_API_KEY = "your-tiingo-key"
python .\scripts\update_rrg_data.py --provider tiingo --batch A --batch-size 48
# at least one hour later (a separate Tiingo request window)
python .\scripts\update_rrg_data.py --provider tiingo --batch B --batch-size 48 --finalize
```

Validate the existing file without any network access:

```powershell
python .\scripts\update_rrg_data.py --validate-only
```

Build the static artifact:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\prepare-dist.ps1
```

Serve either the repo root for quick development or `dist` for the exact GitHub Pages artifact:

```powershell
python -m http.server 4173 --bind 127.0.0.1
```

Then open `http://127.0.0.1:4173`.

## GitHub Pages Deployment

1. Push this repo to GitHub.
2. In GitHub, open `Settings > Pages`.
3. Set `Source` to `GitHub Actions`.
4. Push to `main` or run `Deploy app` manually from the Actions tab.
5. The deploy workflow runs `scripts/prepare-dist.ps1`, uploads `dist`, and publishes it with `actions/deploy-pages`.

The app includes `.nojekyll` so GitHub Pages serves the static PWA files directly.

## Custom Domain

1. Add your domain in `Settings > Pages > Custom domain`.
2. Follow GitHub's DNS instructions:
   - Apex domain: add the required `A` records.
   - Subdomain: add a `CNAME` record pointing to `<user>.github.io`.
3. Keep `Enforce HTTPS` enabled after DNS verification completes.
4. If you want the domain committed in the repo, add a `CNAME` file at the site root with only the domain name.

## Daily Data Update Workflow

`.github/workflows/update-data.yml` runs on weekdays at `22:30 UTC`, safely after the regular U.S. market close. Tiingo Starter allows 50 requests per hour and 500 unique symbols per month, so the 96-symbol universe is updated in two separated request windows:

1. **Batch A** - `python scripts/update_rrg_data.py --provider tiingo --batch A --batch-size 48` downloads at most 48 real histories, writes `public/data/rrg.json`, and commits it. **Nothing is deployed after Batch A**; the intermediate commit only persists real rows so the second window can resume.
2. The job sleeps 61 minutes to enter a new Tiingo hourly window.
3. **Batch B** - `python scripts/update_rrg_data.py --provider tiingo --batch B --batch-size 48 --finalize` downloads the remaining symbols and runs the finalize gate: every required symbol must have real, fresh history before the run may deploy. A separate `--validate-only` step re-checks the file.
4. Only after Batch B commits does the workflow build `dist` and deploy to GitHub Pages - exactly once per day.

A `push` to `main` also triggers `Deploy app`, which runs the same `--validate-only` gate before uploading. A half-updated file therefore can never publish: the gate fails the deploy job and the previous verified data stays live.

The updater is **real-data-only**:

- New symbols are bootstrapped once from real Tiingo EOD history (up to five years, never before the fund's first real row).
- Existing symbols download only a 21-day overlap after their newest cached row; revised adjusted closes in the overlap deterministically replace cached rows, then rows merge by date and trim to the 1,260-row history cap.
- `--full-refresh` re-downloads full history for every symbol (for example after a large corporate action) and still respects the batch windows.
- Short genuine ETF histories are valid; the updater and the app never fabricate prices, never extend history before a fund's inception, and never substitute legacy files. If real data is unavailable, the update fails closed and the last verified data remains deployed.
- Batching is generic: pass `--batch C` (and so on) to extend beyond 96 symbols without redesigning the updater. Each batch stays at or below 48 requests per hourly window.

GitHub Actions uses Tiingo by default because Stooq may return browser-verification HTML in cloud runners instead of CSV data. Stooq support remains in `scripts/update_rrg_data.py` for manual fallback with `--provider stooq`, but it is not used by the scheduled workflow.

To add the Tiingo key:

1. Open the GitHub repository.
2. Go to `Settings > Secrets and variables > Actions`.
3. Click `New repository secret`.
4. Name the secret `TIINGO_API_KEY`.
5. Paste the Tiingo API token as the value and save.

API keys must stay in GitHub Secrets and must not be added to frontend code.

## Data Notes

The frontend reads generated JSON from `data/rrg.json` when deployed. During root-folder local development it can also read `public/data/rrg.json`.

`public/data/rrg.json` contains:

- `generatedAt` and `generatedAtUtc` for the visible Last updated timestamp.
- `source` and `priceField` (always `Tiingo EOD API` / `adjClose` for production data).
- daily close history under `symbols` - every row is real downloaded Tiingo data.
- precomputed default RRG values under `rrg`.

The app still recalculates the displayed RRG from the included close history when the user changes Length, Smooth, or timeframe. The formula is:

`RS = asset close / SPY close`

`RS-Ratio = EMA(RS / EMA(RS, Length), Smooth) * 100`

`RS-Momentum = RS-Ratio / EMA(RS-Ratio, Smooth) * 100`

Length and Smooth are selectable from `10`, `14`, `20`, `50`, `100`, `150`, and `200`, with defaults of `14` and `20`.

### Universes

The app has four universes, selected with the tabs `Sectors | Industries | Themes | Indices`:

- **Sectors** - 11 GICS sector ETFs (unchanged).
- **Industries** - 38 industry and sub-industry ETFs.
- **Themes** - 42 thematic ETFs (AI, cloud, energy transition, miners, and more).
- **Indices** - SPX, NDX, IWM, DJI.

A ticker shared between universes downloads once: `SYMBOLS` in the updater is a deterministic, order-preserving deduplicated union of every universe plus the `SPY` benchmark (96 unique symbols).

### Short ETF histories

Young ETFs (for example `DRAM`, `EUV`, `DRNZ`, `LNGX`, `AIPO`) contribute only their real trading history. Their chart tails start at the fund's first real trading day; nothing is back-filled before inception and no minimum row count forces synthetic data. A symbol without enough real observations for a selected RRG calculation simply has no points for that part of the chart.

## Add Or Remove Tickers

Ticker lists live in two places and should be kept in sync:

- `src/app.js`: update the `UNIVERSES` sector, industry, theme, or index entries for the UI label, color, and group.
- `scripts/update_rrg_data.py`: update `SECTORS`, `INDUSTRIES`, `THEMES`, or `INDICES` so the workflow downloads and writes data for the same symbols.

After changing tickers, bootstrap/update the affected symbols and run:

```powershell
python .\scripts\update_rrg_data.py --provider tiingo --batch A --batch-size 48
python .\scripts\update_rrg_data.py --provider tiingo --batch B --batch-size 48 --finalize
python .\scripts\universe-audit.py
```

## Verify

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify.ps1
python .\scripts\workflow-audit.py
python .\scripts\chart-controls-audit.py
python .\scripts\browser-interaction.py
python .\scripts\ipad-touch-audit.py
python .\scripts\zoom-lock-audit.py
```

For the full local suite:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-all-checks.ps1
```
