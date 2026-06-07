import argparse
import csv
import json
import math
import os
import pathlib
import time
import urllib.error
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
DEFAULT_HISTORY_YEARS = 5
MIN_HISTORY_ROWS = 400
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

INDICES = [
    ("SPX", "S&P 500 Index", "#55a7ff", "Market Index"),
    ("NDX", "Nasdaq 100 Index", "#7c83fd", "Market Index"),
    ("IWM", "Russell 2000 ETF", "#f38b5b", "Market Index"),
    ("DJI", "Dow Jones Industrial Average", "#d6ae3d", "Market Index"),
]

SYMBOLS = [
    BENCHMARK["symbol"],
    *[row[0] for row in SECTORS],
    *[row[0] for row in INDUSTRIES],
    *[row[0] for row in INDICES],
]
TIINGO_SECRET_HELP = (
    "TIINGO_API_KEY is missing. Add it in GitHub at "
    "Settings -> Secrets and variables -> Actions -> New repository secret, "
    "then name the secret TIINGO_API_KEY."
)


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
        reader = csv.DictReader(text.splitlines())
        available_columns = [field for field in reader.fieldnames or [] if field is not None]
        normalized_columns = [normalize_csv_key(field) for field in available_columns]
        missing_columns = [column for column in ("date", "close") if column not in normalized_columns]
        if missing_columns:
            print(
                f"{symbol}: Stooq CSV missing required columns: {', '.join(missing_columns)}. "
                f"Available columns: {', '.join(available_columns) if available_columns else '(none)'}"
            )
            raise RuntimeError(f"{symbol}: Stooq CSV missing required columns")

        for raw_row in reader:
            row = normalize_csv_row(raw_row)
            if not any(value for value in row.values()):
                continue
            date_value = row.get("date", "")
            close_value = row.get("close", "")
            if not date_value or not close_value:
                continue
            try:
                datetime.fromisoformat(date_value)
                close = float(close_value)
            except ValueError:
                continue
            if close > 0:
                rows.append({"date": date_value, "close": round(close, 4)})
        if len(rows) < 180:
            raise RuntimeError(f"{symbol}: not enough Stooq rows")
        return rows


class TiingoProvider:
    name = "Tiingo EOD API"
    price_field = "adjClose"

    def __init__(self):
        self.api_key = os.getenv("TIINGO_API_KEY")

    def fetch(self, symbol):
        if not self.api_key:
            raise RuntimeError(TIINGO_SECRET_HELP)
        end_date = date.today()
        start_date = end_date - timedelta(days=DEFAULT_HISTORY_YEARS * 366)
        params = urllib.parse.urlencode(
            {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "resampleFreq": "daily",
            }
        )
        url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices?{params}"
        print(f"Tiingo request {symbol}: url={url}")
        request = urllib.request.Request(url, headers={"Authorization": f"Token {self.api_key}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.getcode()
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            text = exc.read().decode("utf-8", errors="replace")
            print(f"Tiingo response {symbol}: httpStatus={status} rowsRaw=0 rowsFiltered=0 firstDate= lastDate=")
            print(f"Tiingo error {symbol}: {summarize_json_or_text(text)}")
            raise RuntimeError(f"{symbol}: Tiingo HTTP {status}") from exc

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"Tiingo response {symbol}: httpStatus={status} rowsRaw=0 rowsFiltered=0 firstDate= lastDate=")
            print(f"Tiingo error {symbol}: response was not JSON: {summarize_text(text)}")
            raise RuntimeError(f"{symbol}: Tiingo returned non-JSON response") from exc

        if not isinstance(payload, list):
            print(f"Tiingo response {symbol}: httpStatus={status} rowsRaw=0 rowsFiltered=0 firstDate= lastDate=")
            print(f"Tiingo error {symbol}: expected a JSON list, got {type(payload).__name__}: {summarize_payload(payload)}")
            raise RuntimeError(f"{symbol}: Tiingo returned error response")

        rows = []
        for raw_row in payload:
            if not isinstance(raw_row, dict):
                continue
            row = normalize_json_row(raw_row)
            date_value = str(row.get("date", ""))[:10]
            close_value = row.get("adjclose", row.get("close"))
            if not date_value or close_value in (None, ""):
                continue
            try:
                datetime.fromisoformat(date_value)
                close = float(close_value)
            except (TypeError, ValueError):
                continue
            if close > 0:
                rows.append({"date": date_value, "close": round(close, 4)})

        first_date = rows[0]["date"] if rows else ""
        last_date = rows[-1]["date"] if rows else ""
        print(
            f"Tiingo response {symbol}: httpStatus={status} rowsRaw={len(payload)} "
            f"rowsFiltered={len(rows)} firstDate={first_date} lastDate={last_date}"
        )
        if len(rows) < MIN_HISTORY_ROWS:
            raise RuntimeError(
                f"{symbol}: not enough Tiingo rows after filtering "
                f"({len(rows)} < {MIN_HISTORY_ROWS}); firstDate={first_date or 'n/a'} lastDate={last_date or 'n/a'}"
            )
        return rows


def normalize_csv_key(key):
    return str(key or "").lstrip("\ufeff").strip().lower()


def normalize_csv_row(row):
    normalized = {}
    for key, value in row.items():
        normalized[normalize_csv_key(key)] = str(value or "").strip()
    return normalized


def normalize_json_row(row):
    return {normalize_csv_key(key): value for key, value in row.items()}


def summarize_payload(payload):
    if isinstance(payload, dict):
        pairs = []
        for key, value in payload.items():
            pairs.append(f"{key}={summarize_text(str(value))}")
        return "; ".join(pairs) if pairs else "{}"
    return summarize_text(str(payload))


def summarize_json_or_text(text):
    try:
        return summarize_payload(json.loads(text))
    except json.JSONDecodeError:
        return summarize_text(text)


def summarize_text(text, limit=300):
    compact = " ".join(str(text or "").split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def main():
    parser = argparse.ArgumentParser(description="Update generated RRG data for the static dashboard.")
    parser.add_argument("--provider", choices=["stooq", "tiingo"], default="tiingo")
    parser.add_argument("--existing-only", action="store_true", help="Use existing local market-data.json for offline testing.")
    parser.add_argument("--use-existing-on-fail", action="store_true")
    args = parser.parse_args()

    provider = TiingoProvider() if args.provider == "tiingo" else StooqProvider()
    if args.provider == "tiingo" and not provider.api_key and not args.existing_only and not args.use_existing_on_fail:
        raise SystemExit(TIINGO_SECRET_HELP)
    warnings = []
    if args.existing_only:
        rows_by_symbol = load_existing_rows()
        source = "Existing local market-data.json"
        price_field = "close"
    else:
        try:
            rows_by_symbol, warnings = fetch_all(provider)
            source = provider.name
            price_field = provider.price_field
        except Exception:
            if not args.use_existing_on_fail:
                raise
            rows_by_symbol = load_existing_rows()
            source = "Existing local market-data.json"
            price_field = "close"
            warnings = [f"{provider.name} failed; used existing local data fallback"]

    fill_missing_symbols(rows_by_symbol, warnings)
    rows_by_symbol = {symbol: rows[-HISTORY_LIMIT:] for symbol, rows in rows_by_symbol.items()}
    generated_at = date.today().isoformat()
    data_as_of = latest_common_date(rows_by_symbol) or generated_at
    timeline_dates = [row["date"] for row in rows_by_symbol[BENCHMARK["symbol"]][-TIMEFRAMES["daily"]["history"] :]]
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
        "warnings": warnings,
        "symbols": rows_by_symbol,
        "rrg": build_precomputed_rrg(rows_by_symbol),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"RRG data source: {source}")
    print(f"RRG dataAsOf: {data_as_of}")
    print(f"RRG first timeline date: {timeline_dates[0] if timeline_dates else ''}")
    print(f"RRG last timeline date: {timeline_dates[-1] if timeline_dates else ''}")
    print(f"RRG timeline dates: {len(timeline_dates)}")
    print(f"RRG output file: {OUT}")
    print("RRG deployed path: data/rrg.json")
    print(f"Wrote {OUT} symbols={len(rows_by_symbol)} warnings={len(warnings)} generatedAt={generated_at} source={source}")


def fetch_all(provider):
    rows_by_symbol = {}
    warnings = []
    for index, symbol in enumerate(SYMBOLS, start=1):
        try:
            rows = provider.fetch(symbol)
        except Exception as exc:
            if symbol == BENCHMARK["symbol"]:
                raise RuntimeError(f"{symbol}: benchmark fetch failed; cannot calculate RRG without SPY. {exc}") from exc
            warning = f"{symbol}: skipped, {exc}"
            warnings.append(warning)
            print(f"WARNING: {warning}")
            time.sleep(0.25)
            continue

        rows_by_symbol[symbol] = rows
        if symbol == BENCHMARK["symbol"]:
            print(
                f"Benchmark {BENCHMARK['symbol']} confirmed: rows={len(rows)} "
                f"firstDate={rows[0]['date']} lastDate={rows[-1]['date']}"
            )
        print(f"{index:02d}/{len(SYMBOLS)} {symbol} rows={len(rows_by_symbol[symbol])}")
        time.sleep(0.25)
    return rows_by_symbol, warnings


def load_existing_rows():
    if not LEGACY_DATA.exists():
        raise FileNotFoundError(f"Missing {LEGACY_DATA}")
    payload = json.loads(LEGACY_DATA.read_text(encoding="utf-8"))
    source_symbols = payload.get("symbols", {})
    rows_by_symbol = {}
    for symbol in SYMBOLS:
        rows = source_symbols.get(symbol)
        if rows:
            rows_by_symbol[symbol] = normalize_existing_price_rows(rows)
            continue
        if symbol == BENCHMARK["symbol"]:
            raise KeyError(f"{symbol}: missing benchmark rows in {LEGACY_DATA}")
        print(f"WARNING: {symbol}: missing from existing local data; generating offline sample rows")

    benchmark_rows = rows_by_symbol.get(BENCHMARK["symbol"])
    if not benchmark_rows:
        raise RuntimeError(f"{BENCHMARK['symbol']}: missing benchmark rows in {LEGACY_DATA}")

    for symbol in SYMBOLS:
        if symbol not in rows_by_symbol and symbol != BENCHMARK["symbol"]:
            rows_by_symbol[symbol] = generate_sample_rows(symbol, benchmark_rows)
    return rows_by_symbol


def fill_missing_symbols(rows_by_symbol, warnings):
    benchmark_rows = rows_by_symbol.get(BENCHMARK["symbol"])
    if not benchmark_rows:
        return
    for symbol in SYMBOLS:
        if symbol == BENCHMARK["symbol"] or symbol in rows_by_symbol:
            continue
        warning = f"{symbol}: generated offline sample rows because provider data was unavailable"
        warnings.append(warning)
        print(f"WARNING: {warning}")
        rows_by_symbol[symbol] = generate_sample_rows(symbol, benchmark_rows)


def normalize_existing_price_rows(rows):
    normalized = []
    for row in rows:
        try:
            close = float(row.get("close"))
        except (TypeError, ValueError):
            continue
        if row.get("date") and close > 0:
            normalized.append({"date": row["date"], "close": round(close, 4)})
    return normalized


def generate_sample_rows(symbol, benchmark_rows):
    seed = hash_symbol(symbol)
    price = 70 + (seed % 90)
    phase = (seed % 360) * (math.pi / 180)
    drift = 0.00014 + ((seed % 11) - 5) * 0.000015
    beta = 0.78 + (seed % 50) / 100
    rows = []
    for index, benchmark_row in enumerate(benchmark_rows):
        if index:
            previous = benchmark_rows[index - 1]["close"]
            current = benchmark_row["close"]
            market_return = current / previous - 1 if previous else 0
        else:
            market_return = 0
        cycle = math.sin(index / (34 + (seed % 28)) + phase) * 0.006
        noise = math.sin(index * (0.67 + (seed % 9) / 30) + phase * 2) * 0.004
        price *= 1 + market_return * beta + drift + cycle + noise
        rows.append({"date": benchmark_row["date"], "close": round(price, 4)})
    return rows


def hash_symbol(symbol):
    value = 17
    for char in symbol:
        value = value * 31 + ord(char)
    return value


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
            if symbol == BENCHMARK["symbol"] or symbol not in rows_by_symbol:
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
