import importlib.util
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
                after_industries["circles"] >= 18,
                f"Expected at least 18 industry markers, got {after_industries['circles']}",
            )
            assert_true(
                after_industries["selectedSymbol"] == "XBI",
                f"Industry toggle did not select first industry symbol, got {after_industries['selectedSymbol']}",
            )
            assert_true(
                after_selection["selectedSymbol"] != after_industries["selectedSymbol"],
                "Selecting a rank row did not update the detail panel",
            )

            print(
                "Interaction smoke passed: "
                f"date {initial['selectedDate']} -> {after_slider['selectedDate']}, "
                f"length={initial['lengthPeriod']}->{after_length['lengthPeriod']} "
                f"smooth={initial['smoothPeriod']}->{after_smooth['smoothPeriod']}, "
                f"weeklyMax={after_weekly['sliderMax']} monthlyMax={after_monthly['sliderMax']}, "
                f"playback={before_playback['sliderValue']}->{after_playback['sliderValue']}, "
                f"industryMarkers={after_industries['circles']} tailDots={after_industries['tailDots']}, "
                f"selected={after_selection['selectedSymbol']}"
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
    wait_until(ws, lambda state: state["circles"] >= 18 and state["selectedSymbol"] == "XBI")


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
