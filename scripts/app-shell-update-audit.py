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

INITIAL_MARKER = "app-shell-audit-initial"
UPDATED_MARKER = "app-shell-audit-updated"


def main():
    if not DIST.exists():
        raise RuntimeError("dist does not exist. Run scripts/deploy-audit.ps1 first.")

    browser = browser_capture.find_browser()
    DynamicShellHandler.marker = INITIAL_MARKER
    server = browser_capture.QuietHTTPServer(
        ("127.0.0.1", browser_capture.PORT),
        DynamicShellHandler,
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
            wait_for_cached_styles_marker(ws, INITIAL_MARKER)

            DynamicShellHandler.marker = UPDATED_MARKER
            fetched_marker = fetch_styles_marker(ws)
            if fetched_marker != UPDATED_MARKER:
                raise RuntimeError(f"Expected fetched styles marker {UPDATED_MARKER}, got {fetched_marker}")
            wait_for_cached_styles_marker(ws, UPDATED_MARKER)

            print(
                "App shell update audit passed: "
                f"cachedStyles {INITIAL_MARKER} -> {UPDATED_MARKER}"
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


class DynamicShellHandler(SimpleHTTPRequestHandler):
    marker = INITIAL_MARKER

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/styles.css":
            body = (DIST / "styles.css").read_text(encoding="utf-8") + f"\n/* {self.marker} */\n"
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        super().do_GET()

    def log_message(self, *_):
        pass


def fetch_styles_marker(ws):
    expression = """
    (async () => {
      const response = await fetch('./styles.css', { cache: 'reload' });
      const text = await response.text();
      const match = text.match(/app-shell-audit-(initial|updated)/);
      return JSON.stringify({ marker: match ? match[0] : '' });
    })()
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)["marker"]


def wait_for_cached_styles_marker(ws, expected):
    deadline = time.time() + 20
    last = None
    while time.time() < deadline:
        last = read_cached_styles_marker(ws)
        if last["ready"] and last["marker"] == expected:
            return
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for cached styles marker={expected}. Last state: {last}")


def read_cached_styles_marker(ws):
    expression = """
    (async () => {
      const ready = 'serviceWorker' in navigator
        ? await navigator.serviceWorker.ready.then(() => true).catch(() => false)
        : false;
      const keys = 'caches' in window ? await caches.keys() : [];
      let marker = '';
      for (const key of keys) {
        const cache = await caches.open(key);
        const response = await cache.match('./styles.css');
        if (response) {
          const text = await response.clone().text();
          const match = text.match(/app-shell-audit-(initial|updated)/);
          marker = match ? match[0] : '';
          break;
        }
      }
      return JSON.stringify({ ready, cacheCount: keys.length, marker });
    })()
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return json.loads(value)


if __name__ == "__main__":
    main()
