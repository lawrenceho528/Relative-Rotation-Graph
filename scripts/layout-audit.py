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


VIEWPORTS = [
    # iPad mini A2993 (A17 Pro) Safari CSS viewport proxies.
    ("portrait", 744, 1133),
    ("landscape", 1133, 744),
]


def main():
    results = []
    for name, width, height in VIEWPORTS:
        results.append(run_viewport(name, width, height))

    summary = ", ".join(
        f"{item['name']}: overflow={item['horizontalOverflow']} sliderY={round(item['sliderY'])} chartY={round(item['chartY'])}"
        for item in results
    )
    print(f"Layout audit passed: {summary}")


def run_viewport(name, width, height):
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
            f"--window-size={width},{height}",
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
            metrics = collect_metrics(ws)
            assert_layout(name, metrics)
            return {"name": name, **metrics}
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


def collect_metrics(ws):
    expression = """
    JSON.stringify((() => {
      const rectFor = (selector) => {
        const rect = document.querySelector(selector).getBoundingClientRect();
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, bottom: rect.bottom, right: rect.right };
      };
      const controls = [...document.querySelectorAll('button, input[type="range"]')].map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          label: node.textContent.trim() || node.getAttribute('aria-label') || node.id || node.dataset.universe || node.tagName,
          tag: node.tagName,
          type: node.getAttribute('type') || '',
          width: rect.width,
          height: rect.height,
          visible: rect.width > 0 && rect.height > 0
        };
      });
      return {
        innerWidth,
        innerHeight,
        scrollWidth: document.documentElement.scrollWidth,
        loaded: document.querySelector('#dataStatus')?.textContent.includes('RRG data loaded') || false,
        circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
        tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
        tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
        timeline: rectFor('.timeline'),
        chart: rectFor('.chart-stage'),
        workspace: rectFor('.workspace'),
        controls
      };
    })())
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    return json.loads(result["result"]["value"])


def assert_layout(name, metrics):
    overflow = metrics["scrollWidth"] - metrics["innerWidth"]
    visible_controls = [item for item in metrics["controls"] if item["visible"]]
    too_small = [
        item for item in visible_controls
        if item["type"] != "range"
        and (item["width"] < 36 or item["height"] < 36)
    ]

    if not metrics["loaded"] or metrics["circles"] < 11 or metrics["tails"] < 11 or metrics["tailDots"] < 11:
        raise AssertionError(f"{name}: chart did not render enough content: {metrics}")
    if overflow > 1:
        raise AssertionError(f"{name}: horizontal overflow detected: {overflow}px")
    if metrics["timeline"]["bottom"] > metrics["innerHeight"]:
        raise AssertionError(f"{name}: date slider is not visible in first viewport")
    if metrics["timeline"]["y"] > metrics["chart"]["y"]:
        raise AssertionError(f"{name}: date slider appears after chart")
    if metrics["chart"]["y"] >= metrics["innerHeight"]:
        raise AssertionError(f"{name}: chart starts below first viewport")
    if too_small:
        raise AssertionError(f"{name}: small touch targets: {too_small}")

    metrics["horizontalOverflow"] = overflow
    metrics["sliderY"] = metrics["timeline"]["y"]
    metrics["chartY"] = metrics["chart"]["y"]


if __name__ == "__main__":
    main()
