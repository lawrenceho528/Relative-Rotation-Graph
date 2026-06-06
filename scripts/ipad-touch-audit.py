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
            ws.call(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 744,
                    "height": 1133,
                    "deviceScaleFactor": 2,
                    "mobile": True,
                    "screenWidth": 744,
                    "screenHeight": 1133,
                },
            )
            ws.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            browser_capture.wait_for_render(ws)

            initial = read_state(ws)
            touch_drag_date_slider(ws, direction=-1)
            after_slider = read_state(ws)
            touch_drag_chart(ws, direction=-1)
            after_chart = read_state(ws)
            touch_tap_industries(ws)
            after_industries = read_state(ws)
            marker_symbol = choose_marker_symbol(ws)
            touch_tap_marker(ws, marker_symbol)
            after_marker = read_state(ws)
            rank_symbol = choose_rank_row_symbol(ws)
            touch_tap_rank_row(ws, rank_symbol)
            after_rank = read_state(ws)

            assert_true(initial["touchPoints"] >= 1, f"Touch emulation did not activate: {initial}")
            assert_true(initial["circles"] == 11, f"Expected 11 sector markers: {initial}")
            assert_true(
                after_slider["selectedDate"] != initial["selectedDate"],
                f"Touch drag on date slider did not change date: {initial} -> {after_slider}",
            )
            assert_true(
                after_chart["selectedDate"] == after_slider["selectedDate"]
                and after_chart["sliderValue"] == after_slider["sliderValue"],
                f"Touch drag on chart should not scrub date: {after_slider} -> {after_chart}",
            )
            assert_true(
                after_chart["chartCenterX"] != after_slider["chartCenterX"]
                or after_chart["chartCenterY"] != after_slider["chartCenterY"],
                f"Touch drag on chart did not pan graph center: {after_slider} -> {after_chart}",
            )
            assert_true(
                after_industries["activeUniverse"] == "industries"
                and after_industries["circles"] >= 27
                and after_industries["tailDots"] >= 27,
                f"Touch tap on Industries did not switch universe: {after_industries}",
            )
            assert_true(
                after_marker["selectedSymbol"] == marker_symbol,
                f"Touch tap on marker did not select {marker_symbol}: {after_marker}",
            )
            assert_true(
                after_rank["selectedSymbol"] == rank_symbol,
                f"Touch tap on rank row did not select {rank_symbol}: {after_rank}",
            )

            print(
                "iPad touch audit passed: "
                f"sliderDate={after_slider['selectedDate']} "
                f"chartPan={after_slider['chartCenterX']}/{after_slider['chartCenterY']}->"
                f"{after_chart['chartCenterX']}/{after_chart['chartCenterY']} "
                f"industryMarkers={after_industries['circles']} "
                f"tailDots={after_industries['tailDots']} "
                f"markerSelected={after_marker['selectedSymbol']} "
                f"rankSelected={after_rank['selectedSymbol']} "
                f"touchPoints={initial['touchPoints']}"
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
    return evaluate_json(
        ws,
        """
        JSON.stringify({
          selectedDate: document.querySelector('#selectedDate')?.textContent || '',
          sliderMax: Number(document.querySelector('#dateSlider')?.max || 0),
          sliderValue: Number(document.querySelector('#dateSlider')?.value || 0),
          chartCenterX: Number(document.documentElement.dataset.chartCenterX || 0),
          chartCenterY: Number(document.documentElement.dataset.chartCenterY || 0),
          circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
          tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
          tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
          activeUniverse: document.querySelector('[data-universe].active')?.dataset.universe || '',
          selectedSymbol: document.querySelector('#selectedCard strong')?.textContent || '',
          touchPoints: navigator.maxTouchPoints || 0
        })
        """,
    )


def touch_drag_date_slider(ws, direction):
    rect = element_rect(ws, "#dateSlider")
    y = rect["y"] + rect["height"] / 2
    start_x = rect["x"] + rect["width"] * (0.88 if direction < 0 else 0.12)
    end_x = rect["x"] + rect["width"] * (0.22 if direction < 0 else 0.78)
    drag_touch(ws, start_x, y, end_x, y, steps=12)
    time.sleep(0.25)


def touch_drag_chart(ws, direction):
    rect = element_rect(ws, "#rrgChart")
    y = rect["y"] + rect["height"] * 0.43
    start_x = rect["x"] + rect["width"] * 0.68
    end_x = start_x + direction * rect["width"] * 0.28
    drag_touch(ws, start_x, y, end_x, y, steps=14)
    time.sleep(0.25)


def touch_tap_industries(ws):
    rect = element_rect(ws, '[data-universe="industries"]')
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    dispatch_touch(ws, "touchStart", x, y)
    dispatch_touch(ws, "touchEnd", x, y, ending=True)
    wait_until(
        ws,
        lambda state: state["activeUniverse"] == "industries"
        and state["circles"] >= 27
        and state["tailDots"] >= 27,
    )


def choose_marker_symbol(ws):
    result = evaluate_json(
        ws,
        """
        (() => {
          const current = document.querySelector('#selectedCard strong')?.textContent || '';
          const markers = [...document.querySelectorAll('#rrgChart circle[data-symbol]')]
            .map((node) => {
              const rect = node.getBoundingClientRect();
              return {
                symbol: node.dataset.symbol,
                x: rect.x + rect.width / 2,
                y: rect.y + rect.height / 2,
                visible: rect.width > 0 && rect.height > 0
              };
            })
            .filter((item) => item.symbol && item.symbol !== current && item.visible);
          const scored = markers.map((item) => {
            const nearest = Math.min(
              ...markers
                .filter((other) => other.symbol !== item.symbol)
                .map((other) => Math.hypot(item.x - other.x, item.y - other.y)),
              999
            );
            return { ...item, nearest };
          }).sort((a, b) => b.nearest - a.nearest);
          return JSON.stringify({ symbol: scored[0]?.symbol || '' });
        })()
        """,
    )
    if not result["symbol"]:
        raise RuntimeError("No marker symbol available for touch selection")
    return result["symbol"]


def touch_tap_marker(ws, symbol):
    rect = element_rect(ws, f'#rrgChart circle[data-symbol="{symbol}"]')
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    tap_touch(ws, x, y)
    wait_until(ws, lambda state: state["selectedSymbol"] == symbol)


def choose_rank_row_symbol(ws):
    result = evaluate_json(
        ws,
        """
        (() => {
          const current = document.querySelector('#selectedCard strong')?.textContent || '';
          const row = [...document.querySelectorAll('.rank-row')]
            .find((node) => node.querySelector('b')?.innerText.trim() !== current);
          row?.scrollIntoView({ block: 'center', inline: 'nearest' });
          return JSON.stringify({ symbol: row?.querySelector('b')?.innerText.trim() || '' });
        })()
        """,
    )
    if not result["symbol"]:
        raise RuntimeError("No rank row symbol available for touch selection")
    return result["symbol"]


def touch_tap_rank_row(ws, symbol):
    rect = element_rect(ws, f".rank-row:nth-child({rank_row_index(ws, symbol)})")
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    tap_touch(ws, x, y)
    wait_until(ws, lambda state: state["selectedSymbol"] == symbol)


def rank_row_index(ws, symbol):
    result = evaluate_json(
        ws,
        f"""
        (() => {{
          const rows = [...document.querySelectorAll('.rank-row')];
          const index = rows.findIndex((node) => node.querySelector('b')?.innerText.trim() === {json.dumps(symbol)});
          return JSON.stringify({{ index: index + 1 }});
        }})()
        """,
    )
    if result["index"] <= 0:
        raise RuntimeError(f"Rank row not found for {symbol}")
    return result["index"]


def tap_touch(ws, x, y):
    dispatch_touch(ws, "touchStart", x, y)
    dispatch_touch(ws, "touchEnd", x, y, ending=True)
    time.sleep(0.2)


def drag_touch(ws, start_x, start_y, end_x, end_y, steps):
    dispatch_touch(ws, "touchStart", start_x, start_y)
    for index in range(1, steps + 1):
        x = start_x + (end_x - start_x) * index / steps
        y = start_y + (end_y - start_y) * index / steps
        dispatch_touch(ws, "touchMove", x, y)
        time.sleep(0.025)
    dispatch_touch(ws, "touchEnd", end_x, end_y, ending=True)


def dispatch_touch(ws, event_type, x, y, ending=False):
    points = [] if ending else [{"x": x, "y": y, "radiusX": 6, "radiusY": 6, "force": 0.8, "id": 1}]
    ws.call("Input.dispatchTouchEvent", {"type": event_type, "touchPoints": points})


def element_rect(ws, selector):
    return evaluate_json(
        ws,
        f"""
        (() => {{
          const rect = document.querySelector({json.dumps(selector)}).getBoundingClientRect();
          return JSON.stringify({{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }});
        }})()
        """,
    )


def wait_until(ws, predicate):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if predicate(last_state):
            return
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for touch state. Last state: {last_state}")


def evaluate_json(ws, expression):
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
