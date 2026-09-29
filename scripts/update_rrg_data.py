import argparse
import csv
import hashlib
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
MARKER_PATH = ROOT / "public" / "data" / "update-state.json"

BENCHMARK = {"symbol": "SPY", "name": "S&P 500 ETF"}
DEFAULT_LENGTH = 14
DEFAULT_SMOOTH = 20
HISTORY_LIMIT = 1260
DEFAULT_HISTORY_YEARS = 5
# Incremental updates re-download this many days before the newest cached row so
# revised adjusted closes (splits, dividends) replace the cached overlap rows.
OVERLAP_DAYS = 21
# Sanity floor for a real downloaded history; short genuine ETF histories are valid.
MIN_SYMBOL_ROWS = 5
MIN_BENCHMARK_ROWS = 252
# Maximum allowed gap between a symbol's newest real row and the benchmark's.
STALE_TOLERANCE_DAYS = 10
# Tiingo Starter allows 50 requests/hour; batches stay safely below that.
MAX_BATCH_SIZE = 48
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
    ("OIH", "Oil Services", "#d6ae3d", "Energy"),
    ("XES", "Oil Equipment & Services", "#b76d2c", "Energy"),
    ("XOP", "Oil & Gas Exploration", "#d9843d", "Energy"),
    ("ENFR", "Energy Infrastructure", "#d984ac", "Energy"),
    ("CRAK", "Oil Refiners", "#a67852", "Energy"),
    ("XME", "Metals & Mining", "#b38bdb", "Materials"),
    ("WOOD", "Timber & Forestry", "#62c370", "Materials"),
    ("ITA", "Aerospace & Defense", "#9aa7ba", "Industrials"),
    ("XAR", "Aerospace & Defense Equal Weight", "#ad8f42", "Industrials"),
    ("JETS", "Airlines", "#4fb6d8", "Industrials"),
    ("BOAT", "Global Shipping", "#37b9ba", "Industrials"),
    ("IYT", "Transportation", "#c96ea2", "Industrials"),
    ("ITB", "Home Construction", "#8fb35c", "Consumer Discretionary"),
    ("PEJ", "Leisure & Entertainment", "#f38b5b", "Consumer Discretionary"),
    ("XRT", "Retail", "#6cbf5a", "Consumer Discretionary"),
    ("IHI", "Medical Devices", "#82b1ff", "Health Care"),
    ("XHE", "Health Care Equipment", "#5d99d6", "Health Care"),
    ("IHF", "Health Care Providers", "#c76792", "Health Care"),
    ("XHS", "Health Care Services", "#8c74d6", "Health Care"),
    ("IBB", "Biotech Majors", "#b38bdb", "Health Care"),
    ("XBI", "Biotechnology", "#e05f6f", "Health Care"),
    ("PPH", "Pharmaceuticals Equal Weight", "#b64e75", "Health Care"),
    ("XPH", "Pharmaceuticals", "#d6ae3d", "Health Care"),
    ("KBWB", "KBW Banks", "#4e9a78", "Financials"),
    ("KRE", "Regional Banks", "#4fb6d8", "Financials"),
    ("IYG", "Financial Services", "#58d5d1", "Financials"),
    ("IAI", "Broker-Dealers & Exchanges", "#7c83fd", "Financials"),
    ("REM", "Mortgage Real Estate", "#36c07e", "Real Estate"),
    ("IAK", "U.S. Insurance", "#62c370", "Financials"),
    ("KIE", "Insurance", "#4fb6d8", "Financials"),
    ("IGV", "Software", "#7c83fd", "Information Technology"),
    ("XSW", "Software & Services", "#6b68d8", "Information Technology"),
    ("XTL", "Telecom", "#37b9ba", "Communication Services"),
    ("SMH", "Semiconductors", "#55a7ff", "Information Technology"),
    ("XSD", "Semiconductors Equal Weight", "#3c7dd9", "Information Technology"),
    ("INDS", "Industrial Real Estate", "#9aa7ba", "Real Estate"),
    ("DESK", "Office & Commercial REITs", "#ad8f42", "Real Estate"),
    ("HAUS", "Residential REITs", "#c96ea2", "Real Estate"),
]

THEMES = [
    ("AIQ", "AI & Technology", "#7c83fd", "Artificial Intelligence"),
    ("CHAT", "Generative AI", "#e05f6f", "Artificial Intelligence"),
    ("AIS", "AI Supercycle", "#55a7ff", "Artificial Intelligence"),
    ("AIPO", "AI & Power", "#d6ae3d", "Artificial Intelligence"),
    ("BOTZ", "Robotics & AI", "#8fb35c", "Artificial Intelligence"),
    ("DRAM", "Memory Chips", "#b38bdb", "Semiconductors"),
    ("EUV", "Lithography & Photonics", "#58d5d1", "Semiconductors"),
    ("SKYY", "Cloud Computing", "#4fb6d8", "Cloud & Software"),
    ("WCLD", "Cloud Equal Weight", "#6b68d8", "Cloud & Software"),
    ("CIBR", "Cybersecurity", "#f38b5b", "Cybersecurity & Quantum"),
    ("QTUM", "Quantum Computing", "#37b9ba", "Cybersecurity & Quantum"),
    ("DTCR", "Data Centers", "#3c7dd9", "Digital Infrastructure"),
    ("IDGT", "Digital Infrastructure", "#82b1ff", "Digital Infrastructure"),
    ("WGMI", "Bitcoin Miners", "#d6ae3d", "Digital Infrastructure"),
    ("FINX", "FinTech", "#62c370", "FinTech & Blockchain"),
    ("BLOK", "Blockchain", "#4e9a78", "FinTech & Blockchain"),
    ("UFO", "Space", "#9aa7ba", "Space & Defense"),
    ("SHLD", "Defense Tech", "#ad8f42", "Space & Defense"),
    ("DRNZ", "Drones", "#c96ea2", "Mobility"),
    ("DRIV", "Autonomous & EV", "#d9843d", "Mobility"),
    ("TAN", "Solar", "#f38b5b", "Clean Energy"),
    ("FAN", "Wind Energy", "#58d5d1", "Clean Energy"),
    ("ICLN", "Clean Energy", "#62c370", "Clean Energy"),
    ("PBW", "WilderHill Clean Energy", "#6cbf5a", "Clean Energy"),
    ("NUKZ", "Nuclear", "#b38bdb", "Clean Energy"),
    ("URA", "Uranium", "#d9843d", "Clean Energy"),
    ("HYDR", "Hydrogen", "#36c07e", "Clean Energy"),
    ("LNGX", "U.S. Natural Gas", "#b76d2c", "Natural Gas"),
    ("GRID", "Smart Grid", "#7c83fd", "Grid & Utilities"),
    ("PAVE", "U.S. Infrastructure", "#8fb35c", "Infrastructure"),
    ("AIRR", "Industrial Renaissance", "#c76792", "Infrastructure"),
    ("LIT", "Lithium", "#55a7ff", "Batteries & Materials"),
    ("BATT", "Lithium & Battery", "#5d99d6", "Batteries & Materials"),
    ("COPX", "Copper Miners", "#a67852", "Mining & Materials"),
    ("REMX", "Rare Earth & Metals", "#d984ac", "Mining & Materials"),
    ("GDX", "Gold Miners", "#d6ae3d", "Precious Metals"),
    ("GDXJ", "Junior Gold Miners", "#ad8f42", "Precious Metals"),
    ("SIL", "Silver Miners", "#58d5d1", "Precious Metals"),
    ("SILJ", "Junior Silver Miners", "#8c74d6", "Precious Metals"),
    ("MOO", "Agribusiness", "#6cbf5a", "Agriculture & Water"),
    ("PHO", "Water Resources", "#4fb6d8", "Agriculture & Water"),
    ("ARKG", "Genomic Revolution", "#e05f6f", "Biotechnology"),
]

INDICES = [
    ("QQQ", "Nasdaq-100 ETF Proxy", "#7c83fd", "Market Index"),
    ("IWM", "Russell 2000 ETF", "#f38b5b", "Market Index"),
    ("DIA", "Dow 30 ETF Proxy", "#d6ae3d", "Market Index"),
]

# Deterministic, order-preserving deduplication: a shared ticker downloads once.
SYMBOLS = list(
    dict.fromkeys(
        [
            BENCHMARK["symbol"],
            *[row[0] for row in SECTORS],
            *[row[0] for row in INDUSTRIES],
            *[row[0] for row in THEMES],
            *[row[0] for row in INDICES],
        ]
    )
)
REQUIRED_SYMBOLS = frozenset(SYMBOLS)
TIINGO_SECRET_HELP = (
    "TIINGO_API_KEY is missing. Add it in GitHub at "
    "Settings -> Secrets and variables -> Actions -> New repository secret, "
    "then name the secret TIINGO_API_KEY."
)


class StooqProvider:
    """Manual-only real-data fallback provider; never used by scheduled production runs."""

    name = "Stooq daily CSV"
    price_field = "close"

    def fetch(self, symbol, start_date, end_date):
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
                parsed = datetime.fromisoformat(date_value).date()
                close = float(close_value)
            except ValueError:
                continue
            if close > 0 and start_date <= parsed <= end_date:
                rows.append({"date": date_value, "close": round(close, 4)})
        return rows


class TiingoProvider:
    name = "Tiingo EOD API"
    price_field = "adjClose"

    def __init__(self):
        self.api_key = os.getenv("TIINGO_API_KEY")

    def fetch(self, symbol, start_date, end_date):
        if not self.api_key:
            raise RuntimeError(TIINGO_SECRET_HELP)
        params = urllib.parse.urlencode(
            {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "resampleFreq": "daily",
            }
        )
        url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices?{params}"
        print(f"Tiingo request {symbol}: {start_date.isoformat()}..{end_date.isoformat()}")
        request = urllib.request.Request(url, headers={"Authorization": f"Token {self.api_key}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.getcode()
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            text = exc.read().decode("utf-8", errors="replace")
            print(f"Tiingo response {symbol}: httpStatus={status} rowsRaw=0 rowsKept=0 firstDate= lastDate=")
            print(f"Tiingo error {symbol}: {summarize_json_or_text(text)}")
            raise RuntimeError(f"{symbol}: Tiingo HTTP {status}") from exc

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            print(f"Tiingo response {symbol}: httpStatus={status} rowsRaw=0 rowsKept=0 firstDate= lastDate=")
            print(f"Tiingo error {symbol}: response was not JSON: {summarize_text(text)}")
            raise RuntimeError(f"{symbol}: Tiingo returned non-JSON response") from exc

        if not isinstance(payload, list):
            print(f"Tiingo response {symbol}: httpStatus={status} rowsRaw=0 rowsKept=0 firstDate= lastDate=")
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
            f"rowsKept={len(rows)} firstDate={first_date} lastDate={last_date}"
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


def parse_date(value):
    return date.fromisoformat(value)


def load_cache():
    """Load previously downloaded real rows. Synthetic/legacy substitutes are never accepted."""
    if not OUT.exists():
        return {}
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    source = payload.get("source", "")
    if "sample" in source.lower() or "synthetic" in source.lower() or "existing local" in source.lower():
        raise SystemExit(
            f"{OUT}: cached data source '{source}' is not real provider data; "
            "refusing to build on fabricated rows"
        )
    cache = {}
    for symbol, rows in payload.get("symbols", {}).items():
        normalized = normalize_existing_price_rows(rows)
        if normalized:
            cache[symbol] = normalized
    return cache


def normalize_existing_price_rows(rows):
    normalized = []
    for row in rows:
        try:
            close = float(row.get("close"))
            parse_date(row.get("date", ""))
        except (TypeError, ValueError):
            continue
        if close > 0:
            normalized.append({"date": row["date"], "close": round(close, 4)})
    return normalized


def merge_history(cached_rows, fetched_rows):
    """Deterministic date merge: fetched rows win inside their downloaded range."""
    merged = {row["date"]: row["close"] for row in cached_rows}
    for row in fetched_rows:
        merged[row["date"]] = row["close"]
    return [{"date": day, "close": merged[day]} for day in sorted(merged)]


def update_symbol(symbol, cached_rows, provider, full_refresh):
    today = date.today()
    if cached_rows and not full_refresh:
        newest = parse_date(cached_rows[-1]["date"])
        start_date = newest - timedelta(days=OVERLAP_DAYS)
        mode = f"incremental overlap from {start_date.isoformat()}"
    else:
        start_date = today - timedelta(days=DEFAULT_HISTORY_YEARS * 366)
        mode = f"bootstrap from {start_date.isoformat()}"
    print(f"{symbol}: {mode}")
    fetched = provider.fetch(symbol, start_date, today)
    rows = merge_history(cached_rows, fetched)
    if symbol == BENCHMARK["symbol"] and len(rows) < MIN_BENCHMARK_ROWS:
        raise RuntimeError(f"{BENCHMARK['symbol']}: benchmark needs {MIN_BENCHMARK_ROWS} real rows, got {len(rows)}")
    if len(rows) < MIN_SYMBOL_ROWS:
        raise RuntimeError(
            f"{symbol}: only {len(rows)} real rows returned; refusing to publish without usable real history"
        )
    return rows[-HISTORY_LIMIT:]


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def load_marker():
    if not MARKER_PATH.exists():
        return None
    return json.loads(MARKER_PATH.read_text(encoding="utf-8"))


def write_marker(phase, cycle, batch_symbols, data_as_of, source):
    marker = {
        "schemaVersion": 1,
        "phase": phase,
        "cycle": cycle.isoformat(),
        "batch": phase,
        "batchSize": len(batch_symbols),
        "symbols": list(batch_symbols),
        "dataAsOf": data_as_of,
        "source": source,
        "completedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "cacheSha256": sha256_file(OUT),
    }
    MARKER_PATH.write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    print(
        f"Update marker written: phase={phase} cycle={marker['cycle']} "
        f"symbols={len(batch_symbols)} cacheSha256={marker['cacheSha256'][:12]}"
    )
    return marker


def require_batch_a_marker(cycle, batch_size, ignore_stale_cycle):
    """Batch B gate: prove the checked-out cache carries today's completed Batch A.

    Accepts a phase-A marker (normal flow, cache untouched since A) or a phase-B
    marker for the same cycle (idempotent re-run of B). Anything else fails
    closed before a single Tiingo request is issued.
    """
    marker = load_marker()
    if marker is None:
        raise SystemExit(
            f"{MARKER_PATH}: no Batch A completion marker found; "
            "Batch B must not run without a matching Batch A for this update cycle"
        )
    phase = marker.get("phase")
    if phase not in {"A", "B"}:
        raise SystemExit(f"{MARKER_PATH}: unexpected marker phase {phase!r}; refusing to run Batch B")
    if marker.get("cycle") != cycle.isoformat():
        message = (
            f"{MARKER_PATH}: Batch A marker is for cycle {marker.get('cycle')}, "
            f"not the intended cycle {cycle.isoformat()}"
        )
        if not ignore_stale_cycle:
            raise SystemExit(message + "; failing closed (maintenance override: --ignore-stale-cycle)")
        print(f"WARNING: {message}; continuing via documented --ignore-stale-cycle maintenance override")
    expected_symbols = build_batch(SYMBOLS, batch_size)[0 if phase == "A" else 1]
    if sorted(marker.get("symbols", [])) != sorted(expected_symbols):
        difference = sorted(set(expected_symbols) ^ set(marker.get("symbols", [])))
        raise SystemExit(
            f"{MARKER_PATH}: marker symbols do not match the expected {phase}-batch membership "
            f"(first differences: {difference[:6]}...)"
        )
    current_sha = sha256_file(OUT)
    if marker.get("cacheSha256") != current_sha:
        raise SystemExit(
            f"{MARKER_PATH}: cached data changed since the Batch A marker "
            f"(marker sha {str(marker.get('cacheSha256'))[:12]}..., current sha {current_sha[:12]}...); "
            "re-run Batch A for this cycle before Batch B"
        )
    print(
        f"Batch A marker verified: phase={phase} cycle={marker.get('cycle')} "
        f"symbols={len(marker.get('symbols', []))} cacheSha256={current_sha[:12]}"
    )


def require_phase_b_for_deploy():
    """Deployment gate: publish only complete, finalized (phase-B) data."""
    marker = load_marker()
    if marker is None:
        raise SystemExit(
            f"{MARKER_PATH}: no update marker found; deployment requires a completed Batch B (phase B) state"
        )
    if marker.get("phase") != "B":
        raise SystemExit(
            f"{MARKER_PATH}: marker phase is {marker.get('phase')!r}; "
            "only a completed Batch B (phase B) state may be deployed - refusing to publish a partially updated universe"
        )
    print(f"Deploy gate: marker phase B cycle={marker.get('cycle')} accepted")


def build_batch(symbol_list, batch_size):
    if batch_size < 1 or batch_size > MAX_BATCH_SIZE:
        raise SystemExit(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}")
    return [symbol_list[index : index + batch_size] for index in range(0, len(symbol_list), batch_size)]


def validate_required(rows_by_symbol):
    """Deployment gate: every required symbol must exist with real, fresh history."""
    problems = []
    benchmark_rows = rows_by_symbol.get(BENCHMARK["symbol"])
    if not benchmark_rows:
        problems.append(f"{BENCHMARK['symbol']}: benchmark history missing")
        benchmark_latest = None
    else:
        if len(benchmark_rows) < MIN_BENCHMARK_ROWS:
            problems.append(f"{BENCHMARK['symbol']}: {len(benchmark_rows)} rows is below {MIN_BENCHMARK_ROWS}")
        benchmark_latest = parse_date(benchmark_rows[-1]["date"])

    for symbol in sorted(REQUIRED_SYMBOLS):
        rows = rows_by_symbol.get(symbol)
        if not rows:
            problems.append(f"{symbol}: no real history available")
            continue
        if len(rows) < MIN_SYMBOL_ROWS:
            problems.append(f"{symbol}: {len(rows)} rows is below the {MIN_SYMBOL_ROWS}-row minimum")
        if benchmark_latest:
            latest = parse_date(rows[-1]["date"])
            gap = abs((benchmark_latest - latest).days)
            if gap > STALE_TOLERANCE_DAYS:
                problems.append(f"{symbol}: newest row {latest} is {gap} days from benchmark {benchmark_latest}")

    if problems:
        raise SystemExit(
            "RRG data validation failed; deployment must not proceed.\n  - " + "\n  - ".join(problems)
        )
    print(
        f"RRG data validation passed: symbols={len(rows_by_symbol)} "
        f"required={len(REQUIRED_SYMBOLS)} benchmarkLatest={benchmark_latest}"
    )


def main():
    parser = argparse.ArgumentParser(description="Update generated RRG data for the static dashboard.")
    parser.add_argument("--provider", choices=["stooq", "tiingo"], default="tiingo")
    parser.add_argument(
        "--batch",
        metavar="A|B|...",
        help="process only this hourly request window (chunks of --batch-size symbols)",
    )
    parser.add_argument("--batch-size", type=int, default=MAX_BATCH_SIZE)
    parser.add_argument(
        "--finalize",
        action="store_true",
        help="enforce the complete-universe deployment gate after writing",
    )
    parser.add_argument("--full-refresh", action="store_true", help="re-download full history for every symbol")
    parser.add_argument("--validate-only", action="store_true", help="validate the existing data file without fetching")
    parser.add_argument(
        "--deploy-gate",
        action="store_true",
        help="validate the data file and require a completed Batch B (phase B) marker",
    )
    parser.add_argument(
        "--require-batch-a",
        action="store_true",
        help="fail closed unless a matching Batch A completion marker exists (pass alone for a gate-only check)",
    )
    parser.add_argument(
        "--ignore-stale-cycle",
        action="store_true",
        help="documented maintenance override: accept an older-cycle Batch A marker (completeness is still enforced)",
    )
    parser.add_argument(
        "--write-phase",
        choices=["A", "B"],
        help="after a successful run, persist an update marker for this batch phase",
    )
    parser.add_argument(
        "--cycle",
        metavar="YYYY-MM-DD",
        type=str,
        default=None,
        help="update cycle date used by the Batch A marker gate (default: current UTC date)",
    )
    args = parser.parse_args()

    cycle = date.fromisoformat(args.cycle) if args.cycle else datetime.now(timezone.utc).date()

    cache = load_cache()
    if args.validate_only:
        validate_required(cache)
        return
    if args.deploy_gate:
        validate_required(cache)
        require_phase_b_for_deploy()
        return

    batches = build_batch(SYMBOLS, args.batch_size)
    if args.require_batch_a and not args.batch:
        # Gate-only invocation: prove matching Batch A state without fetching.
        require_batch_a_marker(cycle, args.batch_size, args.ignore_stale_cycle)
        validate_required(cache)
        return
    if args.require_batch_a:
        # Fail closed before issuing any Tiingo requests.
        require_batch_a_marker(cycle, args.batch_size, args.ignore_stale_cycle)

    if args.batch:
        batch = args.batch.upper()
        index = ord(batch) - ord("A")
        if index < 0 or index >= len(batches):
            raise SystemExit(f"--batch {batch} is outside the {len(batches)} computed batches")
        batch_symbols = batches[index]
    else:
        if args.provider == "tiingo" and len(SYMBOLS) > MAX_BATCH_SIZE:
            raise SystemExit(
                f"{len(SYMBOLS)} symbols exceed the {MAX_BATCH_SIZE}-request hourly window; "
                "pass --batch A / --batch B"
            )
        batch_symbols = SYMBOLS

    provider = TiingoProvider() if args.provider == "tiingo" else StooqProvider()
    if args.provider == "tiingo" and not provider.api_key:
        raise SystemExit(TIINGO_SECRET_HELP)

    rows_by_symbol = {symbol: list(rows) for symbol, rows in cache.items()}
    for index, symbol in enumerate(batch_symbols, start=1):
        rows_by_symbol[symbol] = update_symbol(symbol, rows_by_symbol.get(symbol, []), provider, args.full_refresh)
        print(f"{index:02d}/{len(batch_symbols)} {symbol} rows={len(rows_by_symbol[symbol])}")
        time.sleep(0.25)

    write_payload(rows_by_symbol, provider)

    if args.write_phase:
        write_marker(args.write_phase, cycle, batch_symbols, latest_common_date(rows_by_symbol), provider.name)

    if args.finalize:
        validate_required(rows_by_symbol)
    else:
        missing = sorted(REQUIRED_SYMBOLS - set(rows_by_symbol))
        if missing:
            print(f"Intermediate batch state: missing real history for {', '.join(missing)}")


def write_payload(rows_by_symbol, provider):
    trimmed = {symbol: rows[-HISTORY_LIMIT:] for symbol, rows in rows_by_symbol.items() if rows}
    generated_at = date.today().isoformat()
    data_as_of = latest_common_date(trimmed) or generated_at
    payload = {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "generatedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dataAsOf": data_as_of,
        "source": provider.name,
        "priceField": provider.price_field,
        "benchmark": BENCHMARK,
        "defaultPeriods": {"length": DEFAULT_LENGTH, "smooth": DEFAULT_SMOOTH},
        "timeframes": TIMEFRAMES,
        "warnings": [],
        "symbols": trimmed,
        "rrg": build_precomputed_rrg(trimmed),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    benchmark_rows = trimmed.get(BENCHMARK["symbol"], [])
    print(f"RRG data source: {provider.name}")
    print(f"RRG dataAsOf: {data_as_of}")
    print(f"RRG output file: {OUT}")
    print(f"RRG deployed path: data/rrg.json")
    print(
        f"Wrote {OUT} symbols={len(trimmed)} generatedAt={generated_at} "
        f"source={provider.name} benchmarkLatest={benchmark_rows[-1]['date'] if benchmark_rows else 'n/a'}"
    )


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
    """Align a real history to benchmark dates; dates before the first row stay None (no back-fill)."""
    by_date = {row["date"]: row["close"] for row in history}
    sorted_rows = sorted(history, key=lambda row: row["date"])
    pointer = 0
    last_close = None
    aligned = []
    for day in dates:
        if day in by_date:
            last_close = by_date[day]
            aligned.append(last_close)
            continue
        while pointer < len(sorted_rows) and sorted_rows[pointer]["date"] <= day:
            last_close = sorted_rows[pointer]["close"]
            pointer += 1
        aligned.append(last_close if sorted_rows and sorted_rows[0]["date"] <= day else None)
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
