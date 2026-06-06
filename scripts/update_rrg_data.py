import argparse
import csv
import json
import math
import os
import pathlib
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone


ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "data" / "rrg.json"
LEGACY_DATA = ROOT / "data" / "market-data.json"

BENCHMARK = {"symbol": "SPY", "name": "S&P 500 ETF"}
DEFAULT_LENGTH = 14
DEFAULT_SMOOTH = 20
HISTORY_LIMIT = 1260
TIMEFRAMES = {
    "daily": {"history": 1250},
    "weekly": {"history": 260},
    "monthly": {"history": 120},
}

SECTORS = [
    ("XLC", "Communication Services", "#7c83fd", "GICS Sector"),
    ("XLY", "Consumer Discretionary", "#f38b5b", "GICS Sector"),
    ("XLP", "Consumer Staples", "#62c370", "GICS Sector"),
    ("XLE", "Energy", "#d6ae3d", "GICS Sector"),
    ("XLF", "Financials", "#4fb6d8", "GICS Sector"),
    ("XLV", "Health Care", "#e05f6f", "GICS Sector"),
    ("XLI", "Industrials", "#8fb35c", "GICS Sector"),
    ("XLB", "Materials", "#b38bdb", "GICS Sector"),
    ("XLRE", "Real Estate", "#d984ac", "GICS Sector"),
    ("XLK", "Information Technology", "#55a7ff", "GICS Sector"),
    ("XLU", "Utilities", "#58d5d1", "GICS Sector"),
]

INDUSTRIES = [
    ("XBI", "Biotechnology", "#e05f6f", "Health Care"),
    ("IBB", "Biotech Majors", "#b38bdb", "Health Care"),
    ("SOXX", "Semiconductors", "#55a7ff", "Information Technology"),
    ("XSD", "Semiconductors Equal Weight", "#3c7dd9", "Information Technology"),
    ("IGV", "Software", "#7c83fd", "Information Technology"),
    ("XSW", "Software & Services", "#6b68d8", "Information Technology"),
    ("XTL", "Telecom", "#37b9ba", "Communication Services"),
    ("KRE", "Regional Banks", "#4fb6d8", "Financials"),
    ("KBE", "Banks", "#58d5d1", "Financials"),
    ("KCE", "Capital Markets", "#4e9a78", "Financials"),
    ("KIE", "Insurance", "#62c370", "Financials"),
    ("PBJ", "Food & Beverage", "#6cbf5a", "Consumer Staples"),
    ("XRT", "Retail", "#f38b5b", "Consumer Discretionary"),
    ("XHB", "Homebuilders", "#d6ae3d", "Consumer Discretionary"),
    ("ITB", "Residential Construction", "#8fb35c", "Consumer Discretionary"),
    ("XME", "Metals & Mining", "#a67852", "Materials"),
    ("XOP", "Oil & Gas Exploration", "#d9843d", "Energy"),
    ("XES", "Oil Equipment & Services", "#b76d2c", "Energy"),
    ("IYT", "Transportation", "#d984ac", "Industrials"),
    ("XTN", "Transportation Equal Weight", "#c96ea2", "Industrials"),
    ("ITA", "Aerospace & Defense", "#9aa7ba", "Industrials"),
    ("IYR", "Real Estate", "#36c07e", "Real Estate"),
    ("IDU", "Utilities", "#58d5d1", "Utilities"),
    ("XPH", "Pharmaceuticals", "#b64e75", "Health Care"),
    ("IHF", "Health Care Providers", "#c76792", "Health Care"),
    ("IHI", "Medical Devices", "#82b1ff", "Health Care"),
    ("XHE", "Health Care Equipment", "#5d99d6", "Health Care"),
    ("XHS", "Health Care Services", "#8c74d6", "Health Care"),
    ("XAR", "Aerospace & Defense Equal Weight", "#ad8f42", "Industrials"),
]

SYMBOLS = [BENCHMARK["symbol"], *[row[0] for row in SECTORS], *[row[0] for row in INDUSTRIES]]


class StooqProvider:
    name = "Stooq daily CSV"
    price_field = "close"

    def fetch(self, symbol):
        ticker = urllib.parse.quote(f"{symbol.lower()}.us")
        url = f"https://stooq.com/q/d/l/?s={ticker}&i=d"
        request = urllib.request.Request(url, headers={"User-Agent": "RGG-Rotation/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")

        rows = []
        for row in csv.DictReader(text.splitlines()):
            close = float(row["Close"])
            if close > 0:
                rows.append({"date": row["Date"], "close": round(close, 4)})
        if len(rows) < 180:
            raise RuntimeError(f"{symbol}: not enough Stooq rows")
        return rows


class TiingoProvider:
    name = "Tiingo daily adjusted close"
    price_field = "adjClose"

    def __init__(self):
        self.api_key = os.getenv("TIINGO_API_KEY")

    def fetch(self, symbol):
        if not self.api_key:
            raise RuntimeError("TIINGO_API_KEY is not set")
        url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices?resampleFreq=daily"
        request = urllib.request.Request(url, headers={"Authorization": f"Token {self.api_key}"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        rows = []
        for row in payload:
            close = row.get("adjClose")
            if close and close > 0:
                rows.append({"date": row["date"][:10], "close": round(float(close), 4)})
        if len(rows) < 180:
            raise RuntimeError(f"{symbol}: not enough Tiingo rows")
        return rows


def main():
    parser = argparse.ArgumentParser(description="Update generated RRG data for the static dashboard.")
    parser.add_argument("--provider", choices=["stooq", "tiingo"], default="stooq")
    parser.add_argument("--existing-only", action="store_true", help="Use existing local market-data.json for offline testing.")
    parser.add_argument("--use-existing-on-fail", action="store_true")
    args = parser.parse_args()

    provider = TiingoProvider() if args.provider == "tiingo" else StooqProvider()
    if args.existing_only:
        rows_by_symbol = load_existing_rows()
        source = "Existing local market-data.json"
        price_field = "close"
    else:
        try:
            rows_by_symbol = fetch_all(provider)
            source = provider.name
            price_field = provider.price_field
        except Exception:
            if not args.use_existing_on_fail:
                raise
            rows_by_symbol = load_existing_rows()
            source = "Existing local market-data.json"
            price_field = "close"

    rows_by_symbol = {symbol: rows_by_symbol[symbol][-HISTORY_LIMIT:] for symbol in SYMBOLS}
    generated_at = date.today().isoformat()
    data_as_of = latest_common_date(rows_by_symbol) or generated_at
    payload = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "generatedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataAsOf": data_as_of,
        "source": source,
        "priceField": price_field,
        "benchmark": BENCHMARK,
        "defaultPeriods": {"length": DEFAULT_LENGTH, "smooth": DEFAULT_SMOOTH},
        "timeframes": TIMEFRAMES,
        "symbols": rows_by_symbol,
        "rrg": build_precomputed_rrg(rows_by_symbol),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} symbols={len(rows_by_symbol)} generatedAt={generated_at} source={source}")


def fetch_all(provider):
    rows_by_symbol = {}
    for index, symbol in enumerate(SYMBOLS, start=1):
        rows_by_symbol[symbol] = provider.fetch(symbol)
        print(f"{index:02d}/{len(SYMBOLS)} {symbol} rows={len(rows_by_symbol[symbol])}")
        time.sleep(0.25)
    return rows_by_symbol


def load_existing_rows():
    if not LEGACY_DATA.exists():
        raise FileNotFoundError(f"Missing {LEGACY_DATA}")
    payload = json.loads(LEGACY_DATA.read_text(encoding="utf-8"))
    return {
        symbol: [
            {"date": row["date"], "close": round(float(row["close"]), 4)}
            for row in payload["symbols"][symbol]
            if row.get("date") and row.get("close")
        ]
        for symbol in SYMBOLS
    }


def latest_common_date(rows_by_symbol):
    latest = [rows[-1]["date"] for rows in rows_by_symbol.values() if rows]
    return min(latest) if latest else None


def build_precomputed_rrg(rows_by_symbol):
    output = {}
    for timeframe, config in TIMEFRAMES.items():
        benchmark = sample_history(rows_by_symbol[BENCHMARK["symbol"]], timeframe)
        dates = [row["date"] for row in benchmark[-config["history"] :]]
        benchmark_aligned = align_to_dates(benchmark, dates)
        series = {}
        for symbol in SYMBOLS:
            if symbol == BENCHMARK["symbol"]:
                continue
            closes = align_to_dates(sample_history(rows_by_symbol[symbol], timeframe), dates)
            points = compute_rrg_points(closes, benchmark_aligned, DEFAULT_LENGTH, DEFAULT_SMOOTH)
            latest_index = next((index for index in range(len(points) - 1, -1, -1) if points[index]), None)
            if latest_index is not None:
                series[symbol] = {"date": dates[latest_index], **points[latest_index]}
        output[timeframe] = {"latestDate": dates[-1] if dates else "", "series": series}
    return output


def sample_history(history, timeframe):
    if timeframe == "daily":
        return list(history)
    periods = {}
    for row in history:
        key = week_key(row["date"]) if timeframe == "weekly" else row["date"][:7]
        periods[key] = row
    return sorted(periods.values(), key=lambda row: row["date"])


def week_key(day):
    value = datetime.fromisoformat(f"{day}T12:00:00+00:00")
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def align_to_dates(history, dates):
    by_date = {row["date"]: row["close"] for row in history}
    sorted_rows = sorted(history, key=lambda row: row["date"])
    pointer = 0
    last_close = sorted_rows[0]["close"] if sorted_rows else 1
    aligned = []
    for day in dates:
        if day in by_date:
            last_close = by_date[day]
            aligned.append(last_close)
            continue
        while pointer < len(sorted_rows) and sorted_rows[pointer]["date"] <= day:
            last_close = sorted_rows[pointer]["close"]
            pointer += 1
        aligned.append(last_close)
    return aligned


def compute_rrg_points(closes, benchmark, length_period, smooth_period):
    relative_strength = []
    for close, benchmark_close in zip(closes, benchmark):
        if close and benchmark_close and close > 0 and benchmark_close > 0:
            relative_strength.append(close / benchmark_close)
        else:
            relative_strength.append(None)

    smoothed_relative_strength = ema(relative_strength, length_period)
    relative_strength_ratio = [
        None if value is None or smoothed is None else value / smoothed
        for value, smoothed in zip(relative_strength, smoothed_relative_strength)
    ]
    ratio = [None if value is None else value * 100 for value in ema(relative_strength_ratio, smooth_period)]
    smoothed_ratio = ema(ratio, smooth_period)

    points = []
    for ratio_value, smoothed_ratio_value in zip(ratio, smoothed_ratio):
        if ratio_value is None or smoothed_ratio_value is None:
            points.append(None)
        else:
            points.append(
                {
                    "ratio": round(ratio_value, 4),
                    "momentum": round((ratio_value / smoothed_ratio_value) * 100, 4),
                }
            )
    return points


def ema(values, period):
    multiplier = 2 / (period + 1)
    previous = None
    output = []
    for value in values:
        if value is None or not math.isfinite(value):
            output.append(None)
            continue
        previous = value if previous is None else value * multiplier + previous * (1 - multiplier)
        output.append(previous)
    return output


if __name__ == "__main__":
    main()
