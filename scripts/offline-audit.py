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
            ws.call("Network.enable")
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            browser_capture.wait_for_render(ws)
            wait_for_service_worker_and_cache(ws)
            online_state = read_state(ws)

            ws.call(
                "Network.emulateNetworkConditions",
                {
                    "offline": True,
                    "latency": 0,
                    "downloadThroughput": 0,
                    "uploadThroughput": 0,
                },
            )
            ws.call("Page.reload", {"ignoreCache": False})
            browser_capture.wait_for_render(ws)
            offline_state = read_state(ws)

            assert_true(online_state["cacheCount"] >= 1, "Expected app cache before offline reload")
            assert_true(offline_state["loaded"], f"Offline reload did not show loaded status: {offline_state}")
            assert_true(offline_state["circles"] >= 11, f"Offline reload lost chart markers: {offline_state}")
            assert_true(offline_state["tailDots"] >= 11, f"Offline reload lost chart tail dots: {offline_state}")
            assert_true(offline_state["tails"] >= 11, f"Offline reload lost chart tails: {offline_state}")

            print(
                "Offline audit passed: "
                f"cacheCount={online_state['cacheCount']} "
                f"offlineCircles={offline_state['circles']} "
                f"offlineTailDots={offline_state['tailDots']} "
                f"offlineTails={offline_state['tails']}"
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


def wait_for_service_worker_and_cache(ws):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if last_state["serviceWorkerReady"] and last_state["cacheCount"] >= 1:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for service worker cache. Last state: {last_state}")


def read_state(ws):
    expression = """
    (async () => {
      const ready = 'serviceWorker' in navigator
        ? await navigator.serviceWorker.ready.then(() => true).catch(() => false)
        : false;
      const keys = 'caches' in window ? await caches.keys() : [];
      return JSON.stringify({
        loaded: document.querySelector('#dataStatus')?.textContent.includes('RRG data loaded') || false,
        circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
        tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
        tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
        serviceWorkerReady: ready,
        controlled: Boolean(navigator.serviceWorker?.controller),
        cacheCount: keys.length,
        selectedDate: document.querySelector('#selectedDate')?.textContent || ''
      });
    })()
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
