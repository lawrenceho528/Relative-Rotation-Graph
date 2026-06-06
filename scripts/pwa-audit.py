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

            manifest_result = ws.call("Page.getAppManifest")
            installability_result = ws.call("Page.getInstallabilityErrors")
            manifest = json.loads(manifest_result["data"])
            pwa_state = wait_for_service_worker(ws)
            installability_errors = installability_result.get("installabilityErrors", [])

            assert_true(manifest["display"] == "standalone", "Manifest display is not standalone")
            assert_true(manifest["start_url"] == "./index.html", "Manifest start_url changed")
            assert_true(len(manifest.get("icons", [])) >= 2, "Manifest has insufficient icons")
            assert_true(not installability_errors, f"Chrome installability errors: {installability_errors}")
            assert_true(pwa_state["secureContext"], "Local app is not in a secure browser context")
            assert_true(pwa_state["controller"] or pwa_state["ready"], "Service worker did not register")
            assert_true(pwa_state["cacheCount"] >= 1, "No Cache Storage entries were created")
            assert_true(pwa_state["installTarget"] == "ipad-pwa", f"Install target marker missing: {pwa_state}")
            assert_true(
                pwa_state["launchMode"] in {"browser", "standalone", "fullscreen"},
                f"Unexpected launch mode marker: {pwa_state}",
            )

            print(
                "PWA audit passed: "
                f"display={manifest['display']} icons={len(manifest.get('icons', []))} "
                f"installabilityErrors={len(installability_errors)} "
                f"serviceWorkerReady={pwa_state['ready']} caches={pwa_state['cacheCount']} "
                f"launchMode={pwa_state['launchMode']}"
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


def wait_for_service_worker(ws):
    deadline = time.time() + 20
    last_state = None
    while time.time() < deadline:
        last_state = evaluate_state(ws)
        if last_state["ready"] and last_state["cacheCount"] >= 1:
            return last_state
        time.sleep(0.25)
    return last_state or {
        "ready": False,
        "controller": False,
        "cacheCount": 0,
        "secureContext": False,
        "installTarget": "",
        "launchMode": "",
    }


def evaluate_state(ws):
    expression = """
    (async () => {
      const registration = 'serviceWorker' in navigator
        ? await navigator.serviceWorker.ready.then(() => true).catch(() => false)
        : false;
      const keys = 'caches' in window ? await caches.keys() : [];
      return JSON.stringify({
        ready: registration,
        controller: Boolean(navigator.serviceWorker?.controller),
        cacheCount: keys.length,
        secureContext: window.isSecureContext,
        installTarget: document.documentElement.dataset.installTarget || '',
        launchMode: document.documentElement.dataset.launchMode || ''
      });
    })()
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "awaitPromise": True, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
      return {"ready": False, "controller": False, "cacheCount": 0, "secureContext": False, "installTarget": "", "launchMode": ""}
    return json.loads(value)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
