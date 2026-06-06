# RGG Rotation

Interactive iPad-ready Relative Rotation Graph for U.S. equity sector and industry rotation.

## What It Builds

- A static Progressive Web App that can be hosted on GitHub Pages and added to the iPad Home Screen from Safari.
- RRG-style sector and industry rotation against `SPY`.
- Date control through the timeline slider and previous/play/next buttons.
- Graph panning by pressing and dragging inside the chart.
- Continuous two-finger graph zoom and pan inside the chart.
- Generated same-origin RRG data from `public/data/rrg.json`; the browser does not call market-data APIs.
- Network-first app/data caching with offline fallback after the app has been opened once.

## Local Development

Generate or refresh the local data file:

```powershell
$env:TIINGO_API_KEY = "your-tiingo-key"
python .\scripts\update_rrg_data.py --provider tiingo
```

For offline local checks without an API key, use the existing local data fallback:

```powershell
python .\scripts\update_rrg_data.py --provider tiingo --use-existing-on-fail
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

`.github/workflows/update-data.yml` runs on weekdays at `22:30 UTC`, safely after the regular U.S. market close. It:

1. Runs `python scripts/update_rrg_data.py --provider tiingo`.
2. Downloads daily adjusted close history from Tiingo using `TIINGO_API_KEY`.
3. Calculates default Pine-style RRG values for daily, weekly, and monthly views.
4. Writes `public/data/rrg.json`.
5. Commits only `public/data/rrg.json`.

That commit triggers the GitHub Pages deploy workflow through the normal push trigger.

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
- `source` and `priceField`.
- daily close history under `symbols`.
- precomputed default RRG values under `rrg`.

The app still recalculates the displayed RRG from the included close history when the user changes Length, Smooth, or timeframe. The formula is:

`RS = asset close / SPY close`

`RS-Ratio = EMA(RS / EMA(RS, Length), Smooth) * 100`

`RS-Momentum = RS-Ratio / EMA(RS-Ratio, Smooth) * 100`

Length and Smooth are selectable from `10`, `14`, `20`, `50`, `100`, `150`, and `200`, with defaults of `14` and `20`.

## Add Or Remove Tickers

Ticker lists live in two places and should be kept in sync:

- `src/app.js`: update the `UNIVERSES` sector or industry entries for the UI label, color, and group.
- `scripts/update_rrg_data.py`: update `SECTORS` or `INDUSTRIES` so the workflow downloads and writes data for the same symbols.

After changing tickers, run:

```powershell
python .\scripts\update_rrg_data.py --provider tiingo --use-existing-on-fail
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
