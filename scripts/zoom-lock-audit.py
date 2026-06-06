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

            state = read_zoom_lock_state(ws)
            assert_true("maximum-scale=1" in state["viewport"], f"viewport does not cap scale: {state}")
            assert_true("user-scalable=no" in state["viewport"], f"viewport does not disable user scaling: {state}")
            assert_true(state["htmlTouchAction"] == "manipulation", f"html touch-action not locked: {state}")
            assert_true(state["bodyTouchAction"] == "manipulation", f"body touch-action not locked: {state}")
            assert_true(not state["firstTapPrevented"], f"first tap should remain usable: {state}")
            assert_true(state["secondTapPrevented"], f"second tap did not prevent default zoom: {state}")
            assert_true(state["gesturePrevented"], f"gesture zoom was not prevented: {state}")

            print(
                "Zoom lock audit passed: "
                f"viewport='{state['viewport']}' "
                f"touchAction={state['bodyTouchAction']} "
                f"secondTapPrevented={state['secondTapPrevented']} "
                f"gesturePrevented={state['gesturePrevented']}"
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


def read_zoom_lock_state(ws):
    return evaluate_json(
        ws,
        """
        (() => {
          const firstTap = new Event('touchend', { bubbles: true, cancelable: true });
          document.dispatchEvent(firstTap);
          const secondTap = new Event('touchend', { bubbles: true, cancelable: true });
          document.dispatchEvent(secondTap);
          const gesture = new Event('gesturestart', { bubbles: true, cancelable: true });
          document.dispatchEvent(gesture);

          return JSON.stringify({
            viewport: document.querySelector('meta[name="viewport"]')?.content || '',
            htmlTouchAction: getComputedStyle(document.documentElement).touchAction,
            bodyTouchAction: getComputedStyle(document.body).touchAction,
            firstTapPrevented: firstTap.defaultPrevented,
            secondTapPrevented: secondTap.defaultPrevented,
            gesturePrevented: gesture.defaultPrevented
          });
        })()
        """,
    )


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
