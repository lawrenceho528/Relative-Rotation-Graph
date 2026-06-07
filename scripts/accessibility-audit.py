import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import threading


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
            ws.call("Accessibility.enable")
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            browser_capture.wait_for_render(ws)

            dom_state = read_dom_state(ws)
            ax_tree = ws.call("Accessibility.getFullAXTree")
            ax_state = summarize_ax_tree(ax_tree.get("nodes", []))

            assert_true(dom_state["dateSliderLabel"] == "Selected chart date", "Date slider label is missing")
            assert_true(dom_state["chartRole"] == "img", "RRG chart role is not img")
            assert_true(dom_state["chartLabel"] == "Relative Rotation Graph chart", "RRG chart accessible label is missing")
            assert_true(dom_state["sparklineRole"] == "img", "SPY sparkline role is not img")
            assert_true(dom_state["sparklineLabel"] == "SPY price line", "SPY sparkline accessible label is missing")
            assert_true(dom_state["refreshLabel"] == "Refresh market data", "Refresh button label is missing")
            assert_true(dom_state["universeButtons"] == ["Sectors", "Industries", "Indices"], "Universe button text changed")
            assert_true(dom_state["timeframeButtons"] == ["Daily", "Weekly", "Monthly"], "Timeframe button text changed")
            assert_true(dom_state["benchmarkBar"].startswith("SPY $"), f"SPY benchmark bar missing price: {dom_state}")
            assert_true(ax_state["buttons"] >= 7, f"Expected at least 7 accessible buttons: {ax_state}")
            assert_true(ax_state["sliders"] >= 2, f"Expected at least 2 accessible sliders: {ax_state}")
            assert_true(ax_state["chartNamed"], "Accessible tree did not include named RGG chart")
            assert_true(ax_state["dateSliderNamed"], "Accessible tree did not include named date slider")

            print(
                "Accessibility audit passed: "
                f"buttons={ax_state['buttons']} sliders={ax_state['sliders']} "
                f"chartNamed={ax_state['chartNamed']} dateSliderNamed={ax_state['dateSliderNamed']}"
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


def read_dom_state(ws):
    expression = """
    JSON.stringify({
      dateSliderLabel: document.querySelector('#dateSlider')?.getAttribute('aria-label') || '',
      chartRole: document.querySelector('#rrgChart')?.getAttribute('role') || '',
      chartLabel: document.querySelector('#rrgChart')?.getAttribute('aria-label') || '',
      sparklineRole: document.querySelector('#spySparkline')?.getAttribute('role') || '',
      sparklineLabel: document.querySelector('#spySparkline')?.getAttribute('aria-label') || '',
      refreshLabel: document.querySelector('#refreshButton')?.getAttribute('aria-label') || '',
      universeButtons: [...document.querySelectorAll('[data-universe]')].map((button) => button.textContent.trim()),
      timeframeButtons: [...document.querySelectorAll('[data-timeframe]')].map((button) => button.textContent.trim()),
      benchmarkBar: document.querySelector('#benchmarkBar')?.textContent.replace(/\\s+/g, ' ').trim() || ''
    })
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)


def summarize_ax_tree(nodes):
    buttons = 0
    sliders = 0
    chart_named = False
    date_slider_named = False

    for node in nodes:
        role = node.get("role", {}).get("value", "")
        name = node.get("name", {}).get("value", "")
        if role == "button" and name:
            buttons += 1
        if role == "slider" and name:
            sliders += 1
        if name == "Relative Rotation Graph chart":
            chart_named = True
        if name == "Selected chart date":
            date_slider_named = True

    return {
        "buttons": buttons,
        "sliders": sliders,
        "chartNamed": chart_named,
        "dateSliderNamed": date_slider_named,
    }


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
