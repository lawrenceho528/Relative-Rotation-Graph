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
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            browser_capture.wait_for_render(ws)

            initial = read_state(ws)
            drag_date_slider(ws, direction=-1)
            after_slider = read_state(ws)
            drag_chart(ws, direction=-1)
            after_chart = read_state(ws)
            tap_industries(ws)
            after_industries = read_state(ws)

            assert_true(initial["sliderMax"] > 100, "Date slider has insufficient history")
            assert_true(
                after_slider["selectedDate"] != initial["selectedDate"],
                f"Pointer drag on date slider did not change date: {initial} -> {after_slider}",
            )
            assert_true(
                after_chart["selectedDate"] != after_slider["selectedDate"],
                f"Pointer drag on chart did not scrub date: {after_slider} -> {after_chart}",
            )
            assert_true(
                after_industries["circles"] >= 18 and after_industries["tailDots"] >= 18,
                f"Pointer tap on industries did not switch universe: {after_industries}",
            )

            print(
                "Pointer smoke passed: "
                f"sliderDate={after_slider['selectedDate']} "
                f"chartDate={after_chart['selectedDate']} "
                f"industryMarkers={after_industries['circles']} tailDots={after_industries['tailDots']}"
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
          circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
          tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
          tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
          activeUniverse: document.querySelector('[data-universe].active')?.dataset.universe || ''
        })
        """,
    )


def drag_date_slider(ws, direction):
    rect = element_rect(ws, "#dateSlider")
    y = rect["y"] + rect["height"] / 2
    start_x = rect["x"] + (rect["width"] * (0.9 if direction < 0 else 0.1))
    end_x = rect["x"] + (rect["width"] * (0.2 if direction < 0 else 0.8))
    drag_mouse(ws, start_x, y, end_x, y, steps=10)
    time.sleep(0.2)


def drag_chart(ws, direction):
    rect = element_rect(ws, "#rrgChart")
    y = rect["y"] + rect["height"] * 0.45
    start_x = rect["x"] + rect["width"] * 0.65
    end_x = start_x + direction * rect["width"] * 0.25
    drag_mouse(ws, start_x, y, end_x, y, steps=12)
    time.sleep(0.2)


def tap_industries(ws):
    rect = element_rect(ws, '[data-universe="industries"]')
    x = rect["x"] + rect["width"] / 2
    y = rect["y"] + rect["height"] / 2
    ws.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    ws.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    wait_until(ws, lambda state: state["activeUniverse"] == "industries" and state["circles"] >= 18 and state["tailDots"] >= 18)


def drag_mouse(ws, start_x, start_y, end_x, end_y, steps):
    ws.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": start_x, "y": start_y, "button": "none"})
    ws.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": start_x, "y": start_y, "button": "left", "clickCount": 1})
    for index in range(1, steps + 1):
        x = start_x + (end_x - start_x) * index / steps
        y = start_y + (end_y - start_y) * index / steps
        ws.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "left"})
        time.sleep(0.02)
    ws.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": end_x, "y": end_y, "button": "left", "clickCount": 1})


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
    raise RuntimeError(f"Timed out waiting for pointer state. Last state: {last_state}")


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
