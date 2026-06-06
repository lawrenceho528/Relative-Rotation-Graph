import importlib.util
import json
import pathlib
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler


ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CAPTURE_PATH = ROOT / "scripts" / "browser-capture.py"

MAX_TOTAL_BYTES = 2_250_000
MAX_DATA_BYTES = 2_050_000
MAX_NAVIGATION_MS = 12_000
MAX_APP_LOAD_MS = 4_000
MAX_MODEL_BUILD_MS = 1_500
MAX_SVG_RENDER_MS = 800

spec = importlib.util.spec_from_file_location("browser_capture", CAPTURE_PATH)
browser_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_capture)


def main():
    if not DIST.exists():
        raise RuntimeError("dist does not exist. Run scripts/deploy-audit.ps1 first.")

    size_state = read_size_state()
    assert_true(size_state["totalBytes"] <= MAX_TOTAL_BYTES, f"dist payload too large: {size_state}")
    assert_true(size_state["dataBytes"] <= MAX_DATA_BYTES, f"market data payload too large: {size_state}")

    browser = browser_capture.find_browser()
    server = browser_capture.QuietHTTPServer(
        ("127.0.0.1", browser_capture.PORT),
        DistHandler,
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
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        page = browser_capture.wait_for_page()
        ws = browser_capture.WebSocket(page["webSocketDebuggerUrl"])
        try:
            ws.call("Page.enable")
            start = time.perf_counter()
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            state = wait_for_render_state(ws)
            navigation_ms = round((time.perf_counter() - start) * 1000)
            assert_true(navigation_ms <= MAX_NAVIGATION_MS, f"navigation took too long: {navigation_ms}ms state={state}")
            assert_true(state["appLoadMs"] <= MAX_APP_LOAD_MS, f"app load took too long: {state}")
            assert_true(state["modelBuildMs"] <= MAX_MODEL_BUILD_MS, f"model build took too long: {state}")
            assert_true(state["svgRenderMs"] <= MAX_SVG_RENDER_MS, f"SVG render took too long: {state}")
            assert_true(state["resourceCount"] >= 4, f"too few resources loaded: {state}")

            print(
                "Performance audit passed: "
                f"navigationMs={navigation_ms} appLoadMs={state['appLoadMs']} "
                f"modelBuildMs={state['modelBuildMs']} svgRenderMs={state['svgRenderMs']} "
                f"totalBytes={size_state['totalBytes']} "
                f"dataBytes={size_state['dataBytes']} resources={state['resourceCount']}"
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


class DistHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *_):
        pass


def read_size_state():
    files = [path for path in DIST.rglob("*") if path.is_file()]
    data_path = DIST / "data" / "rrg.json"
    return {
        "fileCount": len(files),
        "totalBytes": sum(path.stat().st_size for path in files),
        "dataBytes": data_path.stat().st_size,
    }


def wait_for_render_state(ws):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = read_render_state(ws)
        if (
            last_state["loaded"]
            and last_state["markers"] >= 11
            and last_state["tails"] >= 11
            and last_state["tailDots"] >= 11
        ):
            return last_state
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for performance render state. Last state: {last_state}")


def read_render_state(ws):
    expression = """
    JSON.stringify({
      loaded: document.querySelector('#dataStatus')?.textContent.includes('RRG data loaded') || false,
      markers: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
      tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
      tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
      appLoadMs: Number(document.documentElement.dataset.loadMs || 0),
      modelBuildMs: Number(document.documentElement.dataset.modelBuildMs || 0),
      svgRenderMs: Number(document.documentElement.dataset.renderMs || 0),
      resourceCount: performance.getEntriesByType('resource').length
    })
    """
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
