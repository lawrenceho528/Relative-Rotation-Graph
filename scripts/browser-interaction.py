import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import threading
import time


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPTURE_PATH = ROOT / "scripts" / "browser-capture.py"

spec = importlib.util.spec_from_file_location("browser_capture", CAPTURE_PATH)
browser_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_capture)


ROOT = pathlib.Path(__file__).resolve().parents[1]

THEMES = [
    "AIQ", "CHAT", "AIS", "AIPO", "BOTZ", "DRAM", "EUV", "SKYY", "WCLD", "CIBR",
    "QTUM", "DTCR", "IDGT", "WGMI", "FINX", "BLOK", "UFO", "SHLD", "DRNZ", "DRIV",
    "TAN", "FAN", "ICLN", "PBW", "NUKZ", "URA", "HYDR", "LNGX", "GRID", "PAVE",
    "AIRR", "LIT", "BATT", "COPX", "REMX", "GDX", "GDXJ", "SIL", "SILJ", "MOO",
    "PHO", "ARKG",
]
MIN_THEME_ROWS = 5


def load_theme_history():
    """First real close date and row count per theme from the validated cache."""
    payload = json.loads((ROOT / "public" / "data" / "rrg.json").read_text(encoding="utf-8"))
    return {
        symbol: (rows[0]["date"], len(rows))
        for symbol, rows in payload["symbols"].items()
        if symbol in THEMES
    }


def expected_theme_sets(slider_index):
    """Deterministic expected sets for a slider index.

    Mirrors the frontend contract: a theme renders at a date only when the daily
    timeline reaches its first real close, and it participates at all only with
    the minimum usable row count. Everything else stays unavailable.
    """
    payload = json.loads((ROOT / "public" / "data" / "rrg.json").read_text(encoding="utf-8"))
    dates = [row["date"] for row in payload["symbols"]["SPY"]]
    iso_date = dates[slider_index]
    expected = sorted(
        symbol
        for symbol, (first_date, rows) in load_theme_history().items()
        if first_date <= iso_date and rows >= MIN_THEME_ROWS
    )
    return expected, sorted(set(THEMES) - set(expected))


def read_theme_symbols(ws):
    return set(
        json.loads(
            ws.call(
                "Runtime.evaluate",
                {
                    "expression": "JSON.stringify([...document.querySelectorAll('#rrgChart circle[data-symbol]')].map((node) => node.dataset.symbol))",
                    "returnByValue": True,
                },
            )["result"]["value"]
        )
    )


def read_theme_symbols_settled(ws, deadline_seconds=10):
    """Sample the rendered theme marker set only after it stops changing.

    The app re-renders through requestAnimationFrame-driven date animations, so a
    single DOM sample can catch a transient animation frame. The settled state is
    two consecutive identical samples of both the marker set and its size.
    """
    deadline = time.time() + deadline_seconds
    previous = None
    while time.time() < deadline:
        current = read_theme_symbols(ws)
        if previous is not None and current == previous:
            return current
        previous = current
        time.sleep(0.12)
    raise RuntimeError(f"Theme marker set never settled. Last set: {sorted(previous)}")


def set_slider_to(ws, index):
    evaluate_json(
        ws,
        f"""
        (() => {{
          const slider = document.querySelector('#dateSlider');
          slider.value = String(Math.max(0, Math.min(Number(slider.max), {index})));
          slider.dispatchEvent(new Event('input', {{ bubbles: true }}));
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    time.sleep(0.1)


def main():
    browser = browser_capture.find_browser()
    server = browser_capture.QuietHTTPServer(
        ("127.0.0.1", browser_capture.PORT),
        browser_capture.QuietHandler,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    profile = tempfile.mkdtemp(prefix=".browser-profile-", dir=ROOT)
    process = subprocess.Popen(
        [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={browser_capture.CDP_PORT}",
            f"--user-data-dir={profile}",
            "--window-size=744,1133",
            f"http://127.0.0.1:{browser_capture.PORT}/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        page = browser_capture.wait_for_page()
        ws = browser_capture.WebSocket(page["webSocketDebuggerUrl"])
        try:
            ws.call("Page.enable")
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            browser_capture.wait_for_render(ws)

            initial = read_state(ws)
            select_length_period(ws, "50")
            after_length = read_state(ws)
            select_smooth_period(ws, "150")
            after_smooth = read_state(ws)
            click_weekly(ws)
            after_weekly = read_state(ws)
            click_monthly(ws)
            after_monthly = read_state(ws)
            click_daily(ws)
            after_daily_return = read_state(ws)
            click_step_back(ws)
            after_step_back = read_state(ws)
            click_step_forward(ws)
            after_step_forward = read_state(ws)
            set_slider_near_end(ws)
            before_playback = read_state(ws)
            click_play_pause(ws)
            after_playback = wait_for_slider_advance(ws, before_playback["sliderValue"])
            click_play_pause(ws)
            set_slider_middle(ws)
            after_slider = read_state(ws)
            click_industries(ws)
            after_industries = read_state(ws)
            select_third_rank_row(ws)
            after_selection = read_state(ws)

            assert_true(initial["circles"] == 11, f"Expected 11 sector markers, got {initial['circles']}")
            assert_true(initial["tailDots"] >= 11, f"Expected sector tail history dots, got {initial['tailDots']}")
            assert_true(initial["curvedTails"] >= 11, f"Expected smooth curved RGG tails, got {initial['curvedTails']}")
            assert_true(initial["spySparkline"] == 1, f"Expected one SPY price line, got {initial['spySparkline']}")
            assert_true(initial["sliderMax"] > 100, "Date slider has insufficient history")
            assert_true(initial["benchmarkBar"].startswith("SPY $"), f"SPY benchmark bar missing price: {initial}")
            assert_true(initial["lengthPeriod"] == "14", f"Expected default Length 14, got {initial['lengthPeriod']}")
            assert_true(initial["smoothPeriod"] == "20", f"Expected default Smooth 20, got {initial['smoothPeriod']}")
            assert_true(after_length["lengthPeriod"] == "50", f"Length selector did not update: {after_length}")
            assert_true(after_smooth["smoothPeriod"] == "150", f"Smooth selector did not update: {after_smooth}")
            assert_true(
                abs(after_length["selectedRatio"] - initial["selectedRatio"]) > 0.2
                or abs(after_length["selectedMomentum"] - initial["selectedMomentum"]) > 0.2,
                f"Changing Length did not affect selected RRG values: {initial} -> {after_length}",
            )
            assert_true(
                abs(after_smooth["selectedRatio"] - after_length["selectedRatio"]) > 0.2
                or abs(after_smooth["selectedMomentum"] - after_length["selectedMomentum"]) > 0.2,
                f"Changing Smooth did not affect selected RRG values: {after_length} -> {after_smooth}",
            )
            assert_true(
                after_weekly["timeframe"] == "weekly" and after_weekly["circles"] == 11 and after_weekly["sliderMax"] > 50,
                f"Weekly timeframe did not render sector rotation: {after_weekly}",
            )
            assert_true(
                after_monthly["timeframe"] == "monthly" and after_monthly["circles"] == 11 and after_monthly["sliderMax"] > 10,
                f"Monthly timeframe did not render sector rotation: {after_monthly}",
            )
            assert_true(
                after_monthly["benchmarkBar"].startswith("SPY $") and "Monthly close" in after_monthly["benchmarkBar"],
                f"Monthly SPY benchmark bar did not update: {after_monthly}",
            )
            assert_true(
                after_daily_return["timeframe"] == "daily" and after_daily_return["sliderMax"] == initial["sliderMax"],
                f"Daily timeframe did not restore original timeline: {after_daily_return}",
            )
            assert_true(
                after_step_back["sliderValue"] == after_daily_return["sliderValue"] - 1,
                "Previous date button did not step the timeline backward",
            )
            assert_true(
                after_step_forward["sliderValue"] == after_daily_return["sliderValue"],
                "Next date button did not step the timeline forward",
            )
            assert_true(
                after_playback["sliderValue"] > before_playback["sliderValue"],
                "Timeline playback did not advance the date slider",
            )
            assert_true(
                after_slider["selectedDate"] != initial["selectedDate"],
                "Moving the date slider did not change the selected date",
            )
            assert_true(after_slider["circles"] == 11, "Sector chart lost markers after date slider move")
            assert_true(
                after_industries["circles"] == 38,
                f"Expected 38 industry markers, got {after_industries['circles']}",
            )
            assert_true(
                after_industries["selectedSymbol"] == "OIH",
                f"Industry toggle did not select first industry symbol, got {after_industries['selectedSymbol']}",
            )
            assert_true(
                after_selection["selectedSymbol"] != after_industries["selectedSymbol"],
                "Selecting a rank row did not update the detail panel",
            )
            # Themes: a universe switch resets the timeline to the latest date,
            # so first verify the complete 42-symbol universe there (contract C).
            click_themes(ws)
            after_themes = read_state(ws)
            assert_true(
                after_themes["activeUniverse"] == "themes"
                and after_themes["circles"] == 42
                and after_themes["selectedSymbol"] == "AIQ",
                f"Themes toggle did not render the complete 42-symbol universe at the latest date: {after_themes}",
            )

            # Contract A: at a historical date, only themes with genuine real
            # history on or before that date may render; pre-inception themes
            # must stay unavailable (no synthesis, no back-fill).
            set_slider_to(ws, int(after_themes["sliderMax"]) - 300)
            rendered_middle = read_theme_symbols_settled(ws)
            middle_state = read_state(ws)
            middle_index = int(middle_state["sliderValue"])
            expected_middle, unavailable_middle = expected_theme_sets(middle_index)
            assert_true(
                middle_state["activeUniverse"] == "themes" and sorted(rendered_middle) == expected_middle,
                "Themes at a historical date must render exactly the symbols with real history at that date: "
                f"date={middle_state['selectedDate']} expected={len(expected_middle)} "
                f"missing={sorted(set(expected_middle) - rendered_middle)} "
                f"unexpected={sorted(rendered_middle - set(expected_middle))}",
            )
            assert_true(
                unavailable_middle and all(symbol not in rendered_middle for symbol in unavailable_middle),
                "Pre-inception themes must stay unavailable at the historical date: "
                f"unavailable={unavailable_middle} rendered={sorted(rendered_middle)}",
            )

            # Contract B/C: at the latest date the full 42-symbol universe renders
            # and selection behavior works normally.
            set_slider_near_end(ws)
            rendered_latest = read_theme_symbols_settled(ws)
            after_latest = read_state(ws)
            expected_latest, _ = expected_theme_sets(int(after_latest["sliderValue"]))
            assert_true(
                after_latest["activeUniverse"] == "themes"
                and sorted(rendered_latest) == expected_latest == sorted(THEMES)
                and after_latest["circles"] == 42,
                f"Themes must render the complete universe at the latest date: {after_latest} "
                f"missing={sorted(set(THEMES) - rendered_latest)} unexpected={sorted(rendered_latest - set(THEMES))}",
            )
            select_third_rank_row(ws)
            after_theme_selection = read_state(ws)
            assert_true(
                after_theme_selection["selectedSymbol"] != "AIQ",
                f"Selecting a theme rank row did not update the detail panel: {after_theme_selection}",
            )

            print(
                "Interaction smoke passed: "
                f"date {initial['selectedDate']} -> {after_slider['selectedDate']}, "
                f"length={initial['lengthPeriod']}->{after_length['lengthPeriod']} "
                f"smooth={initial['smoothPeriod']}->{after_smooth['smoothPeriod']}, "
                f"weeklyMax={after_weekly['sliderMax']} monthlyMax={after_monthly['sliderMax']}, "
                f"playback={before_playback['sliderValue']}->{after_playback['sliderValue']}, "
                f"industryMarkers={after_industries['circles']} tailDots={after_industries['tailDots']}, "
                f"themeMarkersMiddle={len(rendered_middle)} unavailableMiddle={len(unavailable_middle)} "
                f"themeMarkersLatest={after_latest['circles']}, "
                f"selected={after_theme_selection['selectedSymbol']}"
            )
        finally:
            ws.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)


def read_state(ws):
    expression = """
    JSON.stringify({
      loaded: document.querySelector('#dataStatus')?.textContent.includes('RRG data loaded') || false,
      unavailableSymbols: document.documentElement.dataset.unavailableSymbols || '',
      dataGeneratedAt: document.documentElement.dataset.dataGeneratedAt || '',
      circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
      tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
      tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
      curvedTails: [...document.querySelectorAll('#rrgChart path[data-tail-path]')].filter((path) => path.getAttribute('d')?.includes(' C ')).length,
      spySparkline: document.querySelectorAll('#spySparkline path[data-spy-sparkline]').length,
      sliderMax: Number(document.querySelector('#dateSlider')?.max || 0),
      sliderValue: Number(document.querySelector('#dateSlider')?.value || 0),
      playLabel: document.querySelector('#playPauseButton')?.getAttribute('aria-label') || '',
      lengthPeriod: document.querySelector('#lengthPeriod')?.value || '',
      smoothPeriod: document.querySelector('#smoothPeriod')?.value || '',
      timeframe: document.querySelector('[data-timeframe].active')?.dataset.timeframe || '',
      activeUniverse: document.querySelector('[data-universe].active')?.dataset.universe || '',
      benchmarkBar: document.querySelector('#benchmarkBar')?.textContent.replace(/\\s+/g, ' ').trim() || '',
      selectedDate: document.querySelector('#selectedDate')?.textContent || '',
      selectedSymbol: document.querySelector('#selectedCard strong')?.textContent || '',
      selectedRatio: Number([...document.querySelectorAll('#selectedCard .metric')].find((node) => node.textContent.includes('RS-Ratio'))?.querySelector('b')?.textContent || 0),
      selectedMomentum: Number([...document.querySelectorAll('#selectedCard .metric')].find((node) => node.textContent.includes('RS-Momentum'))?.querySelector('b')?.textContent || 0),
      quadrant: document.querySelector('#selectedQuadrant')?.textContent || ''
    })
    """
    return evaluate_json(ws, expression)


def click_daily(ws):
    click_timeframe(ws, "daily")


def click_weekly(ws):
    click_timeframe(ws, "weekly")


def click_monthly(ws):
    click_timeframe(ws, "monthly")


def select_length_period(ws, period):
    evaluate_json(
        ws,
        f"""
        (() => {{
          const select = document.querySelector('#lengthPeriod');
          select.value = "{period}";
          select.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    wait_until(ws, lambda state: state["lengthPeriod"] == period and state["circles"] >= 11)


def select_smooth_period(ws, period):
    evaluate_json(
        ws,
        f"""
        (() => {{
          const select = document.querySelector('#smoothPeriod');
          select.value = "{period}";
          select.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    wait_until(ws, lambda state: state["smoothPeriod"] == period and state["circles"] >= 11)


def click_timeframe(ws, timeframe):
    evaluate_json(
        ws,
        f"""
        (() => {{
          document.querySelector('[data-timeframe="{timeframe}"]').click();
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    wait_until(ws, lambda state: state["timeframe"] == timeframe and state["circles"] >= 11)


def click_step_back(ws):
    start = read_state(ws)["sliderValue"]
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('#stepBackButton').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    wait_until(ws, lambda state: state["sliderValue"] == start - 1)


def click_step_forward(ws):
    start = read_state(ws)["sliderValue"]
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('#stepForwardButton').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    wait_until(ws, lambda state: state["sliderValue"] == start + 1)


def click_play_pause(ws):
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('#playPauseButton').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def set_slider_near_end(ws):
    evaluate_json(
        ws,
        """
        (() => {
          const slider = document.querySelector('#dateSlider');
          slider.value = Math.max(0, Number(slider.max) - 4);
          slider.dispatchEvent(new Event('input', { bubbles: true }));
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def set_slider_middle(ws):
    evaluate_json(
        ws,
        """
        (() => {
          const slider = document.querySelector('#dateSlider');
          slider.value = Math.max(0, Number(slider.max) - 300);
          slider.dispatchEvent(new Event('input', { bubbles: true }));
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    wait_until(ws, lambda state: state["circles"] == 11)


def wait_for_slider_advance(ws, start_value):
    deadline = time.time() + 4
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if last_state["sliderValue"] > start_value:
            return last_state
        time.sleep(0.15)
    raise RuntimeError(f"Timed out waiting for playback advance. Last state: {last_state}")


def click_industries(ws):
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('[data-universe="industries"]').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    wait_until(ws, lambda state: state["circles"] == 38 and state["selectedSymbol"] == "OIH")


def click_themes(ws):
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('[data-universe="themes"]').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    try:
        wait_until(ws, lambda state: state["activeUniverse"] == "themes" and state["circles"] == 42 and state["selectedSymbol"] == "AIQ")
    except RuntimeError:
        diagnostic = evaluate_json(
            ws,
            """
            JSON.stringify((function(){
              var rows = [];
              var cards = document.querySelectorAll('.rank-row b');
              cards.forEach(function(node){ rows.push(node.textContent.trim()); });
              var dbg = window.__rrgDebug || {};
              var missing = dbg.series ? dbg.series.length === 42 ? [] : null : null;
              return {
                rankSymbols: rows.slice(0, 50),
                rankCount: rows.length,
                dataGeneratedAt: document.documentElement.dataset.dataGeneratedAt || '',
                unavailableSymbols: document.documentElement.dataset.unavailableSymbols || '',
                debugUniverse: dbg.universe || null,
                debugDateIndex: dbg.dateIndex !== undefined ? dbg.dateIndex : null,
                debugDates: dbg.dates !== undefined ? dbg.dates : null,
                debugHistories: dbg.histories ? dbg.histories.length : null,
                debugSeries: dbg.series ? dbg.series.length : null,
                debugCircles: dbg.circles !== undefined ? dbg.circles : null,
                debugAnimating: dbg.animating !== undefined ? dbg.animating : null,
                debugVisualDateIndex: dbg.visualDateIndex !== undefined ? dbg.visualDateIndex : null,
                debugMissingSeries: dbg.histories && dbg.series ? null : null
              };
            })())
            """,
        )
        print("THEME DIAGNOSTIC:", json.dumps(diagnostic))
        raise


def select_third_rank_row(ws):
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelectorAll('.rank-row')[2]?.click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def wait_until(ws, predicate):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if predicate(last_state):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for interaction state. Last state: {last_state}")


def evaluate_json(ws, expression):
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    import json

    return json.loads(value)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
