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

spec = importlib.util.spec_from_file_location("browser_capture", CAPTURE_PATH)
browser_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_capture)


def main():
    if not DIST.exists():
        raise RuntimeError("dist does not exist. Run scripts/deploy-audit.ps1 first.")

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

            manifest_result = ws.call("Page.getAppManifest")
            installability_result = ws.call("Page.getInstallabilityErrors")
            manifest = json.loads(manifest_result["data"])
            online_state = wait_for_online_state(ws)

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

            errors = installability_result.get("installabilityErrors", [])
            assert_true(manifest["display"] == "standalone", "dist manifest is not standalone")
            assert_true(not errors, f"dist installability errors: {errors}")
            assert_true(online_state["cacheCount"] >= 1, "dist did not create a service-worker cache")
            assert_true(online_state["buildId"], f"dist build identity did not load: {online_state}")
            assert_true(
                online_state["circles"] >= 11 and online_state["tails"] >= 11 and online_state["tailDots"] >= 11,
                f"dist chart did not render: {online_state}",
            )
            assert_true(
                offline_state["circles"] >= 11 and offline_state["tails"] >= 11 and offline_state["tailDots"] >= 11,
                f"dist offline reload did not render chart: {offline_state}",
            )

            print(
                "Dist runtime audit passed: "
                f"installabilityErrors={len(errors)} "
                f"cacheCount={online_state['cacheCount']} "
                f"buildId={online_state['buildId']} "
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


class DistHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *_):
        pass


def wait_for_cache(ws):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if last_state["serviceWorkerReady"] and last_state["cacheCount"] >= 1:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for dist cache. Last state: {last_state}")


def wait_for_online_state(ws):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if (
            last_state["serviceWorkerReady"]
            and last_state["cacheCount"] >= 1
            and last_state["buildId"]
            and last_state["circles"] >= 11
        ):
            return last_state
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for dist runtime state. Last state: {last_state}")


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
        cacheCount: keys.length,
        buildId: document.documentElement.dataset.buildId || '',
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
