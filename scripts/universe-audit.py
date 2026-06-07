import ast
import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "src" / "app.js"
UPDATER_PATH = ROOT / "scripts" / "update_rrg_data.py"
DATA_PATH = ROOT / "public" / "data" / "rrg.json"

EXPECTED_SECTORS = {
    "XLC": "Communication Services",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLE": "Energy",
    "XLF": "Financials",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLK": "Information Technology",
    "XLU": "Utilities",
}

EXPECTED_INDUSTRY_GROUPS = {
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
}

EXPECTED_INDICES = {
    "SPX": "S&P 500 Index",
    "NDX": "Nasdaq 100 Index",
    "IWM": "Russell 2000 ETF",
    "DJI": "Dow Jones Industrial Average",
}


def main():
    app_text = APP_PATH.read_text(encoding="utf-8")
    updater_text = UPDATER_PATH.read_text(encoding="utf-8")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    sectors = extract_universe(app_text, "sectors")
    industries = extract_universe(app_text, "industries")
    indices = extract_universe(app_text, "indices")
    updater_symbols = extract_updater_symbols(updater_text)
    data_symbols = set(data.get("symbols", {}).keys())
    app_symbols = {"SPY", *sectors.keys(), *industries.keys(), *indices.keys()}

    if {symbol: item["name"] for symbol, item in sectors.items()} != EXPECTED_SECTORS:
        raise AssertionError(f"sector universe does not match expected GICS sector proxies: {sectors}")
    if {item["group"] for item in sectors.values()} != {"GICS Sector"}:
        raise AssertionError("sector universe entries must be identified as GICS Sector proxies")
    if len(industries) < 29:
        raise AssertionError(f"industry universe is too small: {len(industries)}")
    if len({item["name"] for item in industries.values()}) != len(industries):
        raise AssertionError("industry names must be unique")
    missing_groups = EXPECTED_INDUSTRY_GROUPS - {item["group"] for item in industries.values()}
    if missing_groups:
        raise AssertionError(f"industry universe is missing parent GICS sector groups: {sorted(missing_groups)}")
    if {symbol: item["name"] for symbol, item in indices.items()} != EXPECTED_INDICES:
        raise AssertionError(f"indices universe does not match expected symbols: {indices}")
    if {item["group"] for item in indices.values()} != {"Market Index"}:
        raise AssertionError("indices universe entries must be identified as Market Index proxies")

    missing_from_updater = sorted(app_symbols - updater_symbols)
    missing_from_data = sorted(app_symbols - data_symbols)
    extra_in_data = sorted(data_symbols - app_symbols)
    if missing_from_updater:
        raise AssertionError(f"symbols missing from update_rrg_data.py: {missing_from_updater}")
    if missing_from_data:
        raise AssertionError(f"symbols missing from rrg.json: {missing_from_data}")
    if extra_in_data:
        raise AssertionError(f"unused symbols in rrg.json: {extra_in_data}")

    print(
        "Universe audit passed: "
        f"sectors={len(sectors)} industries={len(industries)} indices={len(indices)} dataSymbols={len(data_symbols)}"
    )


def extract_universe(text, key):
    match = re.search(rf"{key}:\s*\[(.*?)\]\.map\(toAsset\)", text, re.S)
    if not match:
        raise AssertionError(f"could not find {key} universe in src/app.js")

    entries = re.findall(
        r'\["([A-Z]+)",\s*"([^"]+)",\s*"#[0-9a-fA-F]{6}",\s*"([^"]+)"\]',
        match.group(1),
    )
    if not entries:
        raise AssertionError(f"could not parse {key} universe entries")

    return {symbol: {"name": name, "group": group} for symbol, name, group in entries}


def extract_updater_symbols(text):
    sectors = re.search(r"SECTORS\s*=\s*(\[[^\]]+\])", text, re.S)
    industries = re.search(r"INDUSTRIES\s*=\s*(\[[^\]]+\])", text, re.S)
    indices = re.search(r"INDICES\s*=\s*(\[[^\]]+\])", text, re.S)
    if not sectors or not industries or not indices:
        raise AssertionError("could not find SECTORS, INDUSTRIES, and INDICES in update_rrg_data.py")

    return {
        "SPY",
        *[row[0] for row in ast.literal_eval(sectors.group(1))],
        *[row[0] for row in ast.literal_eval(industries.group(1))],
        *[row[0] for row in ast.literal_eval(indices.group(1))],
    }


if __name__ == "__main__":
    main()
