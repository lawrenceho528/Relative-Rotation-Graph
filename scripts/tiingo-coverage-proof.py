"""Read-only, rate-limited Tiingo EOD coverage proof for the requested upgrade."""

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path


INDUSTRIES = "OIH ENFR CRAK WOOD JETS BOAT PEJ PPH KBWB IYG IAI REM IAK SMH INDS DESK HAUS".split()
THEMES = (
    "AIQ CHAT AIS AIPO DRAM EUV SKYY WCLD CIBR QTUM BOTZ DTCR IDGT FINX BLOK WGMI UFO DRNZ SHLD DRIV "
    "TAN FAN ICLN PBW NUKZ URA LNGX GRID LIT BATT HYDR PAVE AIRR COPX REMX GDX GDXJ SIL SILJ MOO PHO ARKG"
).split()
INDICES = ["SPX", "NDX", "DJI"]
# Metadata probes only: never infer an index mapping from a similar-looking ETF.
INDEX_CANDIDATES = ["^GSPC", "^SPX", "^NDX", "^DJI", "DJIA", ".SPX", ".NDX"]
BATCH_SIZE = 48
WINDOW_SECONDS = 3660
START = (date.today() - timedelta(days=5 * 366)).isoformat()
END = date.today().isoformat()
KEY = os.environ.get("TIINGO_API_KEY")


def request(symbol, prices=True):
    encoded = urllib.parse.quote(symbol, safe="")
    endpoint = f"https://api.tiingo.com/tiingo/daily/{encoded}"
    if prices:
        endpoint += "/prices?" + urllib.parse.urlencode({"startDate": START, "endDate": END, "resampleFreq": "daily"})
    req = urllib.request.Request(endpoint, headers={"Authorization": f"Token {KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, None


def inspect_prices(symbol):
    status, payload = request(symbol)
    result = {"symbol": symbol, "http": status, "recognized": status == 200 and isinstance(payload, list),
              "first": None, "last": None, "rows": 0, "adjustedClose": False}
    rows = []
    if result["recognized"]:
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            day = str(raw.get("date", ""))[:10]
            close = raw.get("adjClose")
            try:
                valid = date.fromisoformat(day) and math.isfinite(float(close)) and float(close) > 0
            except (TypeError, ValueError):
                valid = False
            if valid:
                rows.append({"date": day, "close": round(float(close), 4)})
        rows.sort(key=lambda row: row["date"])
        result.update(first=rows[0]["date"] if rows else None, last=rows[-1]["date"] if rows else None,
                      rows=len(rows), adjustedClose=bool(rows))
    print(json.dumps(result), flush=True)
    return result, rows


def main():
    if not KEY:
        raise SystemExit("TIINGO_API_KEY is unavailable; no requests made")
    symbols = INDUSTRIES + THEMES + INDICES
    assert len(INDUSTRIES) == 17 and len(THEMES) == 42 and len(set(symbols)) == len(symbols)
    results, histories = [], {}
    start = time.monotonic()
    for index, symbol in enumerate(symbols):
        if index == BATCH_SIZE:
            seconds = max(0, WINDOW_SECONDS - (time.monotonic() - start))
            print(f"First window complete: {BATCH_SIZE} requests; waiting {seconds:.0f}s before second", flush=True)
            time.sleep(seconds)
        result, rows = inspect_prices(symbol)
        results.append(result)
        if rows:
            histories[symbol] = rows
    # Only query metadata for unresolved original indices and plausible native index aliases.
    # Second window begins with 14 price requests, leaving at least 34 requests of headroom.
    unresolved = [row["symbol"] for row in results if row["symbol"] in INDICES and not row["adjustedClose"]]
    for symbol in unresolved + INDEX_CANDIDATES:
        status, payload = request(symbol, prices=False)
        metadata = payload if isinstance(payload, dict) else {}
        record = {"symbol": symbol, "metadataHttp": status, "ticker": metadata.get("ticker"),
                  "name": metadata.get("name"), "startDate": metadata.get("startDate"),
                  "endDate": metadata.get("endDate")}
        print(json.dumps(record), flush=True)
        results.append(record)
    Path("tiingo-proof.json").write_text(json.dumps(results, indent=2))
    Path("tiingo-prices.json").write_text(json.dumps(histories, separators=(",", ":")))
    print(f"ETF proof complete: {sum(row.get('adjustedClose', False) for row in results[:59])}/59 with adjusted rows", flush=True)


if __name__ == "__main__":
    main()
