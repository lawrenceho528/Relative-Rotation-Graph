import datetime as dt
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "public" / "data" / "rrg.json"


def parse_date(value):
    return dt.date.fromisoformat(value)


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    source = data.get("source", "")
    generated_at = parse_date(data["generatedAt"])
    symbols = data.get("symbols", {})
    today = dt.date.today()

    if not symbols:
        raise AssertionError("generated RRG data has no symbols")
    if "synthetic" in source.lower() or "sample" in source.lower():
        raise AssertionError(f"generated RRG data is not live daily data: {source}")
    if generated_at > today:
        raise AssertionError(f"generatedAt is in the future: {generated_at}")
    if (today - generated_at).days > 2:
        raise AssertionError(f"generated RRG data was generated too long ago: {generated_at}")

    spy_rows = symbols.get("SPY", [])
    if len(spy_rows) < 252:
        raise AssertionError(f"SPY history is too short: {len(spy_rows)} rows")

    spy_latest = parse_date(spy_rows[-1]["date"])
    if (today - spy_latest).days > 5:
        raise AssertionError(f"SPY latest trading row is stale: {spy_latest}")

    stale_symbols = []
    short_symbols = []
    for symbol, rows in symbols.items():
        if len(rows) < 252:
            short_symbols.append(f"{symbol}:{len(rows)}")
            continue
        latest = parse_date(rows[-1]["date"])
        if abs((spy_latest - latest).days) > 5:
            stale_symbols.append(f"{symbol}:{latest}")

    if short_symbols:
        raise AssertionError(f"symbols with short histories: {', '.join(short_symbols)}")
    if stale_symbols:
        raise AssertionError(f"symbols not aligned with SPY latest row: {', '.join(stale_symbols)}")

    print(
        "RRG data freshness audit passed: "
        f"source={source} generatedAt={generated_at} "
        f"symbols={len(symbols)} spyLatest={spy_latest}"
    )


if __name__ == "__main__":
    main()
