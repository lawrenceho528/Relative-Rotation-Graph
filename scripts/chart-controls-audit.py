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
            move_date_slider(ws)
            wait_until(ws, lambda state: state["rankRows"] == initial["rankRows"] and state["circles"] == initial["circles"])
            after_slider = read_state(ws)
            click_zoom_in(ws)
            after_zoom_in = read_state(ws)
            click_zoom_out(ws)
            after_zoom_out = read_state(ws)
            pinch_zoom_in(ws)
            after_pinch_zoom_in = read_state(ws)
            pinch_zoom_out(ws)
            after_pinch_zoom_out = read_state(ws)
            single_finger_pan(ws)
            after_pan = read_state(ws)
            two_finger_pan_and_zoom(ws)
            after_two_finger = read_state(ws)
            toggle_first_symbol(ws)
            after_hide = read_state(ws)
            toggle_first_symbol(ws)
            after_show = read_state(ws)

            assert_true(initial["chartExtent"] == 10, f"Expected default fixed extent 10, got {initial}")
            assert_true(
                initial["chartMin"] == 90 and initial["chartMax"] == 110,
                f"Expected default chart range 90-110: {initial}",
            )
            assert_true(
                initial["plotWidth"] == 862 and initial["plotHeight"] == 560,
                f"Expected previous chart scaling geometry: {initial}",
            )
            assert_true(
                after_slider["chartExtent"] == initial["chartExtent"],
                f"Date changes should not auto-scale the chart: {after_slider}",
            )
            assert_true(after_zoom_in["chartExtent"] == 9, f"Zoom in did not reduce extent: {after_zoom_in}")
            assert_true(
                after_zoom_in["chartMin"] == 91 and after_zoom_in["chartMax"] == 109,
                f"Zoom in did not narrow to 91-109: {after_zoom_in}",
            )
            assert_true(after_zoom_out["chartExtent"] == 10, f"Zoom out did not restore extent: {after_zoom_out}")
            assert_true(
                after_zoom_out["chartMin"] == 90 and after_zoom_out["chartMax"] == 110,
                f"Zoom out did not restore 90-110: {after_zoom_out}",
            )
            assert_true(
                after_pinch_zoom_in["chartExtent"] < after_zoom_out["chartExtent"],
                f"Pinch out did not zoom in: {after_pinch_zoom_in}",
            )
            assert_true(
                after_pinch_zoom_in["chartMin"] > 90 and after_pinch_zoom_in["chartMax"] < 110,
                f"Pinch out did not narrow the chart range: {after_pinch_zoom_in}",
            )
            assert_true(
                after_pinch_zoom_out["chartExtent"] > after_pinch_zoom_in["chartExtent"],
                f"Pinch in did not zoom out: {after_pinch_zoom_out}",
            )
            assert_true(
                after_pan["chartExtent"] == after_pinch_zoom_out["chartExtent"],
                f"Single-finger pan should move the center without changing scale: {after_pan}",
            )
            assert_true(
                after_pan["chartCenterX"] < after_pinch_zoom_out["chartCenterX"],
                f"Single-finger pan right should shift X center lower: {after_pinch_zoom_out} -> {after_pan}",
            )
            assert_true(
                after_pan["chartCenterY"] > after_pinch_zoom_out["chartCenterY"],
                f"Single-finger pan down should shift Y center higher: {after_pinch_zoom_out} -> {after_pan}",
            )
            assert_true(
                after_pan["sliderValue"] == after_pinch_zoom_out["sliderValue"],
                f"Chart pan should not change the date slider: {after_pinch_zoom_out} -> {after_pan}",
            )
            assert_true(
                after_two_finger["chartExtent"] < after_pan["chartExtent"],
                f"Two-finger gesture should zoom in continuously: {after_pan} -> {after_two_finger}",
            )
            assert_true(
                after_two_finger["chartCenterX"] < after_pan["chartCenterX"],
                f"Two-finger drag should pan X while zooming: {after_pan} -> {after_two_finger}",
            )
            assert_true(after_hide["circles"] == initial["circles"] - 1, f"Hide did not remove one marker: {after_hide}")
            assert_true(after_hide["rankRows"] == initial["rankRows"], "Hidden symbol disappeared from the list")
            assert_true(after_hide["hiddenRows"] == 1, f"Expected one hidden row, got {after_hide}")
            assert_true(after_show["circles"] == initial["circles"], f"Show did not restore marker count: {after_show}")
            assert_true(after_show["hiddenRows"] == 0, f"Expected no hidden rows after restore: {after_show}")

            print(
                "Chart controls audit passed: "
                f"extent {initial['chartExtent']}->{after_zoom_in['chartExtent']}->{after_zoom_out['chartExtent']} "
                f"pinch {after_pinch_zoom_in['chartExtent']}->{after_pinch_zoom_out['chartExtent']} "
                f"pan {after_pinch_zoom_out['chartCenterX']}/{after_pinch_zoom_out['chartCenterY']}->"
                f"{after_pan['chartCenterX']}/{after_pan['chartCenterY']} "
                f"twoFinger {after_pan['chartExtent']}->{after_two_finger['chartExtent']} "
                f"plot={initial['plotWidth']}x{initial['plotHeight']} "
                f"markers {initial['circles']}->{after_hide['circles']}->{after_show['circles']}"
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
          chartExtent: Number(document.documentElement.dataset.chartExtent || 0),
          chartCenterX: Number(document.documentElement.dataset.chartCenterX || 0),
          chartCenterY: Number(document.documentElement.dataset.chartCenterY || 0),
          chartMin: Number(document.querySelector('#rrgChart')?.dataset.chartMin || 0),
          chartMax: Number(document.querySelector('#rrgChart')?.dataset.chartMax || 0),
          chartMinY: Number(document.querySelector('#rrgChart')?.dataset.chartMinY || 0),
          chartMaxY: Number(document.querySelector('#rrgChart')?.dataset.chartMaxY || 0),
          zoomValue: document.querySelector('#zoomValue')?.value || '',
          plotWidth: Number(document.querySelector('#rrgChart')?.dataset.plotWidth || 0),
          plotHeight: Number(document.querySelector('#rrgChart')?.dataset.plotHeight || 0),
          circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
          rankRows: document.querySelectorAll('.rank-row').length,
          hiddenRows: document.querySelectorAll('.rank-row.hidden-symbol').length,
          sliderValue: Number(document.querySelector('#dateSlider')?.value || 0),
          sliderMax: Number(document.querySelector('#dateSlider')?.max || 0)
        })
        """,
    )


def move_date_slider(ws):
    evaluate_json(
        ws,
        """
        (() => {
          const slider = document.querySelector('#dateSlider');
          slider.value = Math.max(0, Number(slider.max) - 30);
          slider.dispatchEvent(new Event('input', { bubbles: true }));
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.2)


def click_zoom_in(ws):
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('#zoomInButton').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def click_zoom_out(ws):
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('#zoomOutButton').click();
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def pinch_zoom_in(ws):
    run_pinch(ws, 100, 220)


def pinch_zoom_out(ws):
    run_pinch(ws, 220, 110)


def run_pinch(ws, start_distance, end_distance):
    evaluate_json(
        ws,
        f"""
        (() => {{
          const chart = document.querySelector('#rrgChart');
          const rect = chart.getBoundingClientRect();
          const cx = rect.left + rect.width / 2;
          const cy = rect.top + rect.height / 2;
          const start = {start_distance} / 2;
          const end = {end_distance} / 2;
          const eventInit = (pointerId, x, type) => ({{
            bubbles: true,
            cancelable: true,
            pointerId,
            pointerType: 'touch',
            isPrimary: pointerId === 31,
            clientX: x,
            clientY: cy,
            buttons: type === 'pointerup' ? 0 : 1
          }});
          chart.dispatchEvent(new PointerEvent('pointerdown', eventInit(31, cx - start, 'pointerdown')));
          chart.dispatchEvent(new PointerEvent('pointerdown', eventInit(32, cx + start, 'pointerdown')));
          chart.dispatchEvent(new PointerEvent('pointermove', eventInit(31, cx - end, 'pointermove')));
          chart.dispatchEvent(new PointerEvent('pointermove', eventInit(32, cx + end, 'pointermove')));
          chart.dispatchEvent(new PointerEvent('pointerup', eventInit(31, cx - end, 'pointerup')));
          chart.dispatchEvent(new PointerEvent('pointerup', eventInit(32, cx + end, 'pointerup')));
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    time.sleep(0.1)


def single_finger_pan(ws):
    evaluate_json(
        ws,
        """
        (() => {
          const chart = document.querySelector('#rrgChart');
          const rect = chart.getBoundingClientRect();
          const startX = rect.left + rect.width / 2;
          const startY = rect.top + rect.height / 2;
          const endX = startX + 120;
          const endY = startY + 70;
          const pointer = {
            bubbles: true,
            cancelable: true,
            pointerId: 51,
            pointerType: 'touch',
            isPrimary: true,
            buttons: 1
          };
          chart.dispatchEvent(new PointerEvent('pointerdown', { ...pointer, clientX: startX, clientY: startY }));
          chart.dispatchEvent(new PointerEvent('pointermove', { ...pointer, clientX: endX, clientY: endY }));
          chart.dispatchEvent(new PointerEvent('pointerup', { ...pointer, clientX: endX, clientY: endY, buttons: 0 }));
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def two_finger_pan_and_zoom(ws):
    evaluate_json(
        ws,
        """
        (() => {
          const chart = document.querySelector('#rrgChart');
          const rect = chart.getBoundingClientRect();
          const cx = rect.left + rect.width / 2;
          const cy = rect.top + rect.height / 2;
          const start = 70;
          const end = 130;
          const moveX = 90;
          const moveY = 45;
          const eventInit = (pointerId, x, y, type) => ({
            bubbles: true,
            cancelable: true,
            pointerId,
            pointerType: 'touch',
            isPrimary: pointerId === 61,
            clientX: x,
            clientY: y,
            buttons: type === 'pointerup' ? 0 : 1
          });
          chart.dispatchEvent(new PointerEvent('pointerdown', eventInit(61, cx - start, cy, 'pointerdown')));
          chart.dispatchEvent(new PointerEvent('pointerdown', eventInit(62, cx + start, cy, 'pointerdown')));
          chart.dispatchEvent(new PointerEvent('pointermove', eventInit(61, cx + moveX - end, cy + moveY, 'pointermove')));
          chart.dispatchEvent(new PointerEvent('pointermove', eventInit(62, cx + moveX + end, cy + moveY, 'pointermove')));
          chart.dispatchEvent(new PointerEvent('pointerup', eventInit(61, cx + moveX - end, cy + moveY, 'pointerup')));
          chart.dispatchEvent(new PointerEvent('pointerup', eventInit(62, cx + moveX + end, cy + moveY, 'pointerup')));
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.1)


def toggle_first_symbol(ws):
    wait_until(ws, lambda state: state["rankRows"] > 0)
    evaluate_json(
        ws,
        """
        (() => {
          document.querySelector('.rank-row .visibility-toggle').dispatchEvent(
            new MouseEvent('click', { bubbles: true })
          );
          return JSON.stringify({ ok: true });
        })()
        """,
    )
    time.sleep(0.15)


def wait_until(ws, predicate):
    deadline = time.time() + 10
    last_state = None
    while time.time() < deadline:
        last_state = read_state(ws)
        if predicate(last_state):
            return
        time.sleep(0.15)
    raise RuntimeError(f"Timed out waiting for chart control state. Last state: {last_state}")


def evaluate_json(ws, expression):
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")

    return json.loads(value)


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
