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

EXPECTED_INDUSTRIES = {
    "OIH": "Oil Services",
    "XES": "Oil Equipment & Services",
    "XOP": "Oil & Gas Exploration",
    "ENFR": "Energy Infrastructure",
    "CRAK": "Oil Refiners",
    "XME": "Metals & Mining",
    "WOOD": "Timber & Forestry",
    "ITA": "Aerospace & Defense",
    "XAR": "Aerospace & Defense Equal Weight",
    "JETS": "Airlines",
    "BOAT": "Global Shipping",
    "IYT": "Transportation",
    "ITB": "Home Construction",
    "PEJ": "Leisure & Entertainment",
    "XRT": "Retail",
    "IHI": "Medical Devices",
    "XHE": "Health Care Equipment",
    "IHF": "Health Care Providers",
    "XHS": "Health Care Services",
    "IBB": "Biotech Majors",
    "XBI": "Biotechnology",
    "PPH": "Pharmaceuticals Equal Weight",
    "XPH": "Pharmaceuticals",
    "KBWB": "KBW Banks",
    "KRE": "Regional Banks",
    "IYG": "Financial Services",
    "IAI": "Broker-Dealers & Exchanges",
    "REM": "Mortgage Real Estate",
    "IAK": "U.S. Insurance",
    "KIE": "Insurance",
    "IGV": "Software",
    "XSW": "Software & Services",
    "XTL": "Telecom",
    "SMH": "Semiconductors",
    "XSD": "Semiconductors Equal Weight",
    "INDS": "Industrial Real Estate",
    "DESK": "Office & Commercial REITs",
    "HAUS": "Residential REITs",
}

EXPECTED_THEMES = {
    "AIQ": "AI & Technology",
    "CHAT": "Generative AI",
    "AIS": "AI Supercycle",
    "AIPO": "AI & Power",
    "BOTZ": "Robotics & AI",
    "DRAM": "Memory Chips",
    "EUV": "Lithography & Photonics",
    "SKYY": "Cloud Computing",
    "WCLD": "Cloud Equal Weight",
    "CIBR": "Cybersecurity",
    "QTUM": "Quantum Computing",
    "DTCR": "Data Centers",
    "IDGT": "Digital Infrastructure",
    "WGMI": "Bitcoin Miners",
    "FINX": "FinTech",
    "BLOK": "Blockchain",
    "UFO": "Space",
    "SHLD": "Defense Tech",
    "DRNZ": "Drones",
    "DRIV": "Autonomous & EV",
    "TAN": "Solar",
    "FAN": "Wind Energy",
    "ICLN": "Clean Energy",
    "PBW": "WilderHill Clean Energy",
    "NUKZ": "Nuclear",
    "URA": "Uranium",
    "HYDR": "Hydrogen",
    "LNGX": "U.S. Natural Gas",
    "GRID": "Smart Grid",
    "PAVE": "U.S. Infrastructure",
    "AIRR": "Industrial Renaissance",
    "LIT": "Lithium",
    "BATT": "Lithium & Battery",
    "COPX": "Copper Miners",
    "REMX": "Rare Earth & Metals",
    "GDX": "Gold Miners",
    "GDXJ": "Junior Gold Miners",
    "SIL": "Silver Miners",
    "SILJ": "Junior Silver Miners",
    "MOO": "Agribusiness",
    "PHO": "Water Resources",
    "ARKG": "Genomic Revolution",
}

EXPECTED_INDICES = {
    "QQQ": "Nasdaq-100 ETF Proxy",
    "IWM": "Russell 2000 ETF",
    "DIA": "Dow 30 ETF Proxy",
}


def main():
    app_text = APP_PATH.read_text(encoding="utf-8")
    updater_text = UPDATER_PATH.read_text(encoding="utf-8")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

    sectors = extract_universe(app_text, "sectors")
    industries = extract_universe(app_text, "industries")
    themes = extract_universe(app_text, "themes")
    indices = extract_universe(app_text, "indices")
    updater_symbols = extract_updater_symbols(updater_text)
    data_symbols = set(data.get("symbols", {}).keys())
    app_symbols = {"SPY", *sectors.keys(), *industries.keys(), *themes.keys(), *indices.keys()}

    if {symbol: item["name"] for symbol, item in sectors.items()} != EXPECTED_SECTORS:
        raise AssertionError(f"sector universe does not match expected GICS sector proxies: {sectors}")
    if {item["group"] for item in sectors.values()} != {"GICS Sector"}:
        raise AssertionError("sector universe entries must be identified as GICS Sector proxies")
    if {symbol: item["name"] for symbol, item in industries.items()} != EXPECTED_INDUSTRIES:
        raise AssertionError(
            "industry universe must exactly match the requested 38-symbol replacement; "
            f"difference: missing={sorted(EXPECTED_INDUSTRIES.keys() - industries.keys())} "
            f"unexpected={sorted(industries.keys() - EXPECTED_INDUSTRIES.keys())} "
            f"renamed={sorted(symbol for symbol in EXPECTED_INDUSTRIES.keys() & industries.keys() if EXPECTED_INDUSTRIES[symbol] != industries[symbol]['name'])}"
        )
    if {symbol: item["name"] for symbol, item in themes.items()} != EXPECTED_THEMES:
        raise AssertionError(
            "themes universe must exactly match the requested 42-symbol list; "
            f"difference: missing={sorted(EXPECTED_THEMES.keys() - themes.keys())} "
            f"unexpected={sorted(themes.keys() - EXPECTED_THEMES.keys())} "
            f"renamed={sorted(symbol for symbol in EXPECTED_THEMES.keys() & themes.keys() if EXPECTED_THEMES[symbol] != themes[symbol]['name'])}"
        )
    if {symbol: item["name"] for symbol, item in indices.items()} != EXPECTED_INDICES:
        raise AssertionError(f"indices universe does not match expected symbols: {indices}")
    if {item["group"] for item in indices.values()} != {"Market Index"}:
        raise AssertionError("indices universe entries must be identified as Market Index proxies")

    counts = {"sectors": len(sectors), "industries": len(industries), "themes": len(themes), "indices": len(indices)}
    if counts != {"sectors": 11, "industries": 38, "themes": 42, "indices": 3}:
        raise AssertionError(f"universe counts are wrong: {counts}")
    if len(app_symbols) != 95:
        raise AssertionError(f"expected 95 unique market-data symbols, found {len(app_symbols)}")
    if len(updater_symbols) != len(app_symbols) or updater_symbols != app_symbols:
        raise AssertionError(
            "updater symbols must be the deduplicated union of every frontend universe: "
            f"appOnly={sorted(app_symbols - updater_symbols)} updaterOnly={sorted(updater_symbols - app_symbols)}"
        )
    if not is_deduplicated(updater_text):
        raise AssertionError("updater SYMBOLS must be built with deterministic order-preserving deduplication")

    missing_from_data = sorted(app_symbols - data_symbols)
    extra_in_data = sorted(data_symbols - app_symbols)
    if missing_from_data:
        raise AssertionError(
            "symbols missing real history in rrg.json (deployment stays blocked until resolved): "
            f"{missing_from_data}"
        )
    if extra_in_data:
        raise AssertionError(f"unused symbols in rrg.json: {extra_in_data}")
    if data.get("warnings"):
        raise AssertionError(f"generated RRG data must carry no synthetic-data warnings: {data['warnings']}")

    print(
        "Universe audit passed: "
        f"sectors={counts['sectors']} industries={counts['industries']} themes={counts['themes']} "
        f"indices={counts['indices']} uniqueSymbols={len(app_symbols)} dataSymbols={len(data_symbols)}"
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
    names = ("SECTORS", "INDUSTRIES", "THEMES", "INDICES")
    blocks = {name: re.search(rf"{name}\s*=\s*(\[[^\]]+\])", text, re.S) for name in names}
    if any(block is None for block in blocks.values()):
        raise AssertionError(f"could not find {', '.join(names)} in update_rrg_data.py")

    return {
        "SPY",
        *[row[0] for name in names for row in ast.literal_eval(blocks[name].group(1))],
    }


def is_deduplicated(updater_text):
    match = re.search(r"SYMBOLS\s*=\s*list\(\s*dict\.fromkeys\(", updater_text, re.S)
    return bool(match)


if __name__ == "__main__":
    main()
