import datetime
import json
import math
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "public" / "data" / "rrg.json").read_text())["symbols"]
APP_JS = (ROOT / "src" / "app.js").read_text(encoding="utf-8")

TIMEFRAMES = {
    "daily": {"history": 1250},
    "weekly": {"history": 260},
    "monthly": {"history": 120},
}
RRG_PERIODS = [10, 14, 20, 50, 100, 150, 200]
DEFAULT_LENGTH_PERIOD = 14
DEFAULT_SMOOTH_PERIOD = 20


def main():
    assert_condition("RRG_PERIODS = [10, 14, 20, 50, 100, 150, 200]" in APP_JS, "RRG period list missing")
    assert_condition("DEFAULT_LENGTH_PERIOD = 14" in APP_JS, "Pine Length default should be 14")
    assert_condition("DEFAULT_SMOOTH_PERIOD = 20" in APP_JS, "Pine Smooth default should be 20")
    assert_condition("CHART_CENTER = 100" in APP_JS, "Pine-style graph should use 100 as the quadrant center")
    assert_condition("function ema" in APP_JS, "EMA helper missing")
    assert_condition("relativeStrengthRatio" in APP_JS, "RS / EMA(RS) ratio step missing")
    assert_condition("ratioValue / smoothedRatioValue" in APP_JS, "RS momentum ratio step missing")
    assert_condition('document.querySelector("#lengthPeriod")' in APP_JS, "Length selector is not wired")
    assert_condition('document.querySelector("#smoothPeriod")' in APP_JS, "Smooth selector is not wired")

    removed_terms = [
        "function normalizeSeries",
        "function toJdkValue",
        "RRG_BASE_LENGTH",
        "NORMALIZATION_SCALE",
        "MIN_NORMALIZATION_SAMPLES",
        "EPSILON",
        "function wilderRsi",
        "function rsiFromAverages",
        "calculateRelativePerformance",
        "stockReturn",
        "benchmarkReturn",
        "ratioPeriod",
        "momentumPeriod",
        "trendWeight",
        "performanceWeight",
        "logRelativeStrength",
    ]
    for term in removed_terms:
        assert_condition(term not in APP_JS, f"retired formula term still present: {term}")

    sample_points = compute_rrg_points(
        [200, 200, 200, 200, 200],
        [100, 100, 100, 100, 100],
        DEFAULT_LENGTH_PERIOD,
        DEFAULT_SMOOTH_PERIOD,
    )
    assert_condition(all(point is not None for point in sample_points), "flat sample should produce points")
    assert_close(sample_points[-1][0], 100, "flat RS-Ratio")
    assert_close(sample_points[-1][1], 100, "flat RS-Momentum")

    expected_points = compute_rrg_points([100, 110, 121], [100, 100, 100], DEFAULT_LENGTH_PERIOD, DEFAULT_SMOOTH_PERIOD)
    assert_close(expected_points[-1][0], 102.2984753257, "sample Pine RS-Ratio")
    assert_close(expected_points[-1][1], 102.0035939348, "sample Pine RS-Momentum")

    latest = {}
    point_count = 0
    for length_period in RRG_PERIODS:
        for timeframe in TIMEFRAMES:
            symbols = [symbol for symbol in DATA.keys() if symbol != "SPY"]
            values = []

            for symbol in symbols:
                points = build_points(symbol, timeframe, length_period, DEFAULT_SMOOTH_PERIOD)
                assert_condition(
                    points,
                    f"length {length_period} smooth {DEFAULT_SMOOTH_PERIOD} {timeframe} {symbol} produced no points",
                )
                point_count += len(points)

                for date, point in points.items():
                    assert_finite(
                        point["ratio"],
                        f"length {length_period} smooth {DEFAULT_SMOOTH_PERIOD} {timeframe} {symbol} {date} ratio",
                    )
                    assert_finite(
                        point["momentum"],
                        f"length {length_period} smooth {DEFAULT_SMOOTH_PERIOD} {timeframe} {symbol} {date} momentum",
                    )

                current = list(points.values())[-1]
                values.append((current["ratio"], current["momentum"]))
                if length_period in {10, 14, 200} and timeframe == "daily" and symbol in {"XLE", "XLK"}:
                    latest[f"length{length_period}{symbol}"] = current

            ratio_span = max(value[0] for value in values) - min(value[0] for value in values)
            momentum_span = max(value[1] for value in values) - min(value[1] for value in values)
            assert_condition(ratio_span > 2, f"length {length_period} {timeframe} RS-Ratio span is too compressed")
            assert_condition(
                momentum_span > 0.5,
                f"length {length_period} {timeframe} RS-Momentum span is too compressed",
            )

    for smooth_period in RRG_PERIODS:
        for timeframe in TIMEFRAMES:
            symbols = [symbol for symbol in DATA.keys() if symbol != "SPY"]
            values = []

            for symbol in symbols:
                points = build_points(symbol, timeframe, DEFAULT_LENGTH_PERIOD, smooth_period)
                assert_condition(
                    points,
                    f"length {DEFAULT_LENGTH_PERIOD} smooth {smooth_period} {timeframe} {symbol} produced no points",
                )
                point_count += len(points)

                for date, point in points.items():
                    assert_finite(
                        point["ratio"],
                        f"length {DEFAULT_LENGTH_PERIOD} smooth {smooth_period} {timeframe} {symbol} {date} ratio",
                    )
                    assert_finite(
                        point["momentum"],
                        f"length {DEFAULT_LENGTH_PERIOD} smooth {smooth_period} {timeframe} {symbol} {date} momentum",
                    )

                current = list(points.values())[-1]
                values.append((current["ratio"], current["momentum"]))
                if smooth_period in {10, 20, 200} and timeframe == "daily" and symbol in {"XLE", "XLK"}:
                    latest[f"smooth{smooth_period}{symbol}"] = current

            ratio_span = max(value[0] for value in values) - min(value[0] for value in values)
            momentum_span = max(value[1] for value in values) - min(value[1] for value in values)
            assert_condition(ratio_span > 2, f"smooth {smooth_period} {timeframe} RS-Ratio span is too compressed")
            assert_condition(momentum_span > 0.5, f"smooth {smooth_period} {timeframe} RS-Momentum span is too compressed")

    assert_condition(
        abs(latest["length10XLK"]["ratio"] - latest["length200XLK"]["ratio"]) > 2,
        "Length selector should materially change RS-Ratio",
    )
    assert_condition(
        abs(latest["length10XLE"]["momentum"] - latest["length200XLE"]["momentum"]) > 0.5,
        "Length selector should materially change RS-Momentum",
    )
    assert_condition(
        abs(latest["smooth10XLK"]["ratio"] - latest["smooth200XLK"]["ratio"]) > 2,
        "Smooth selector should materially change RS-Ratio",
    )
    assert_condition(
        abs(latest["smooth10XLE"]["momentum"] - latest["smooth200XLE"]["momentum"]) > 0.5,
        "Smooth selector should materially change RS-Momentum",
    )

    print(
        "RRG formula audit passed: "
        f"points={point_count} "
        f"length10XLK={format_point(latest['length10XLK'])} "
        f"length14XLK={format_point(latest['length14XLK'])} "
        f"length200XLK={format_point(latest['length200XLK'])} "
        f"smooth10XLK={format_point(latest['smooth10XLK'])} "
        f"smooth20XLK={format_point(latest['smooth20XLK'])} "
        f"smooth200XLK={format_point(latest['smooth200XLK'])} "
        f"smooth20XLE={format_point(latest['smooth20XLE'])}"
    )


def build_points(symbol, timeframe, length_period, smooth_period):
    config = TIMEFRAMES[timeframe]
    benchmark_history = sample_history(DATA["SPY"], timeframe)[-config["history"] :]
    dates = [row["date"] for row in benchmark_history]
    benchmark = align_to_dates(benchmark_history, dates)
    closes = align_to_dates(sample_history(DATA[symbol], timeframe), dates)
    points = compute_rrg_points(closes, benchmark, length_period, smooth_period)

    return {
        date: {"ratio": point[0], "momentum": point[1]}
        for date, point in zip(dates, points)
        if point is not None
    }


def sample_history(history, timeframe):
    if timeframe == "daily":
        return list(history)

    periods = {}
    for row in history:
        key = week_key(row["date"]) if timeframe == "weekly" else row["date"][:7]
        periods[key] = row

    return sorted(periods.values(), key=lambda row: row["date"])


def week_key(date):
    value = datetime.date.fromisoformat(date)
    iso = value.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def align_to_dates(history, dates):
    by_date = {row["date"]: row["close"] for row in history}
    sorted_history = sorted(history, key=lambda row: row["date"])
    pointer = 0
    last_close = sorted_history[0]["close"] if sorted_history else 1
    aligned = []

    for date in dates:
        if date in by_date:
            last_close = by_date[date]
            aligned.append(last_close)
            continue

        while pointer < len(sorted_history) and sorted_history[pointer]["date"] <= date:
            last_close = sorted_history[pointer]["close"]
            pointer += 1

        aligned.append(last_close)

    return aligned


def compute_rrg_points(closes, benchmark, length_period, smooth_period):
    relative_strength = [
        close / benchmark[index]
        if is_positive_number(close) and is_positive_number(benchmark[index])
        else None
        for index, close in enumerate(closes)
    ]
    smoothed_relative_strength = ema(relative_strength, length_period)
    relative_strength_ratio = [
        value / smoothed_relative_strength[index]
        if value is not None and smoothed_relative_strength[index] is not None
        else None
        for index, value in enumerate(relative_strength)
    ]
    ratio = [value * 100 if value is not None else None for value in ema(relative_strength_ratio, smooth_period)]
    smoothed_ratio = ema(ratio, smooth_period)

    points = []
    for index, ratio_value in enumerate(ratio):
        smoothed_ratio_value = smoothed_ratio[index]
        momentum_value = (
            ratio_value / smoothed_ratio_value * 100
            if ratio_value is not None and smoothed_ratio_value is not None
            else None
        )
        points.append(None if ratio_value is None or momentum_value is None else (ratio_value, momentum_value))

    return points


def ema(values, period):
    multiplier = 2 / (period + 1)
    output = []
    previous = None

    for value in values:
        if value is None or not math.isfinite(value):
            output.append(None)
            continue

        previous = value if previous is None else value * multiplier + previous * (1 - multiplier)
        output.append(previous)

    return output


def is_positive_number(value):
    return math.isfinite(value) and value > 0


def format_point(point):
    return f"{point['ratio']:.2f}/{point['momentum']:.2f}"


def assert_finite(value, label):
    if not math.isfinite(value):
        raise AssertionError(f"{label}: expected finite value, got {value}")


def assert_close(actual, expected, label, tolerance=0.000001):
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"{label}: expected {expected:.8f}, got {actual:.8f}")


def assert_condition(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
