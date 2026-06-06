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

DATA_VERSION = {"generatedAt": "2099-01-01"}


def main():
    if not DIST.exists():
        raise RuntimeError("dist does not exist. Run scripts/deploy-audit.ps1 first.")

    source_payload = json.loads((DIST / "data" / "rrg.json").read_text(encoding="utf-8"))
    first_version = source_payload["generatedAt"]
    updated_version = DATA_VERSION["generatedAt"]
    if first_version == updated_version:
        raise RuntimeError("Test update version matches current data version.")

    server = browser_capture.QuietHTTPServer(
        ("127.0.0.1", browser_capture.PORT),
        DynamicDataHandler,
    )
    DynamicDataHandler.payload = source_payload
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    browser = browser_capture.find_browser()
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
            wait_for_cached_version(ws, first_version)

            updated_payload = dict(source_payload)
            updated_payload["generatedAt"] = updated_version
            DynamicDataHandler.payload = updated_payload

            fetched_version = fetch_market_data_version(ws)
            if fetched_version != updated_version:
                raise RuntimeError(f"Expected fetched data version {updated_version}, got {fetched_version}")
            wait_for_cached_version(ws, updated_version)

            print(
                "RRG data update audit passed: "
                f"cachedGeneratedAt {first_version} -> {updated_version}"
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


class DynamicDataHandler(SimpleHTTPRequestHandler):
    payload = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/data/rrg.json":
            body = json.dumps(self.payload, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, *_):
        pass


def wait_for_cached_version(ws, expected):
    deadline = time.time() + 20
    last = None
    while time.time() < deadline:
        last = read_cached_data_state(ws)
        if last["generatedAt"] == expected and last["circles"] >= 11 and last["tailDots"] >= 11:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for cached generatedAt={expected}. Last state: {last}")


def fetch_market_data_version(ws):
    expression = """
    (async () => {
      const response = await fetch(`./data/rrg.json?audit=${Date.now()}`, { cache: 'reload' });
      const json = await response.json();
      return JSON.stringify({ generatedAt: json.generatedAt || '' });
    })()
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)["generatedAt"]


def read_cached_data_state(ws):
    expression = """
    (async () => {
      const ready = 'serviceWorker' in navigator
        ? await navigator.serviceWorker.ready.then(() => true).catch(() => false)
        : false;
      const keys = 'caches' in window ? await caches.keys() : [];
      let generatedAt = '';
      for (const key of keys) {
        const cache = await caches.open(key);
        const response = await cache.match('./data/rrg.json');
        if (response) {
          const json = await response.clone().json();
          generatedAt = json.generatedAt || '';
          break;
        }
      }
      return JSON.stringify({
        ready,
        cacheCount: keys.length,
        generatedAt,
        circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
        tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
        tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length
      });
    })()
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)


if __name__ == "__main__":
    main()
