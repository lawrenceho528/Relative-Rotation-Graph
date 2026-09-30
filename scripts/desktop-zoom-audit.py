import base64
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
DESKTOP_WIDTH = 1500
DESKTOP_HEIGHT = 1000
THEMES_SCREENSHOT = ROOT / "rgg-desktop-themes-zoom.png"

spec = importlib.util.spec_from_file_location("browser_capture", CAPTURE_PATH)
browser_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_capture)


def main():
    results = []
    results.append(run_viewport("desktop", DESKTOP_WIDTH, DESKTOP_HEIGHT, touch=False, verify_zoom=True))
    results.append(run_viewport("desktop-narrow", 1200, DESKTOP_HEIGHT, touch=False, verify_zoom=False))
    results.append(run_viewport("desktop-touch", DESKTOP_WIDTH, DESKTOP_HEIGHT, touch=True, verify_zoom=False))
    results.append(run_viewport("ipad-portrait", 744, 1133, touch=True, verify_zoom=False))
    results.append(run_viewport("ipad-landscape", 1133, 744, touch=True, verify_zoom=False))

    summary = ", ".join(
        f"{item['name']}: sliderVisible={item['sliderVisible']} extent={item['extent']}"
        for item in results
    )
    print(f"Desktop zoom slider audit passed: {summary}")


def run_viewport(name, width, height, touch, verify_zoom):
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
            if touch:
                # Headless desktop reports (pointer: none); real touch devices
                # report (pointer: coarse). Emulating touch flips the media query
                # so the audit exercises the production pointer gate.
                ws.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 5})
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
            browser_capture.wait_for_render(ws)
            metrics = collect_state(ws)
            assert_slider_visibility(name, metrics, expect_visible=not touch and width > 1200)
            if verify_zoom:
                verify_desktop_zoom(name, ws)
                capture_themes_screenshot(ws)
            return {"name": name, "sliderVisible": metrics["slider"]["visible"], "extent": metrics["extent"]}
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


def collect_state(ws):
    expression = """
    JSON.stringify((() => {
      const slider = document.getElementById('chartZoomSlider');
      const readout = document.getElementById('chartZoomReadout');
      const stage = document.querySelector('.chart-stage');
      const sliderRect = slider ? slider.getBoundingClientRect() : null;
      const stageRect = stage ? stage.getBoundingClientRect() : null;
      const svgRect = document.querySelector('#rrgChart').getBoundingClientRect();
      const controlRect = document.querySelector('.chart-zoom').getBoundingClientRect();
      const style = slider ? getComputedStyle(slider) : null;
      return {
        loaded: document.querySelector('#dataStatus')?.textContent.includes('RRG data loaded') || false,
        extent: Number(document.documentElement.dataset.chartExtent || 0),
        chartCenterX: Number(document.documentElement.dataset.chartCenterX || 0),
        chartCenterY: Number(document.documentElement.dataset.chartCenterY || 0),
        chartMin: Number(document.querySelector('#rrgChart')?.dataset.chartMin || 0),
        chartMax: Number(document.querySelector('#rrgChart')?.dataset.chartMax || 0),
        chartMinY: Number(document.querySelector('#rrgChart')?.dataset.chartMinY || 0),
        chartMaxY: Number(document.querySelector('#rrgChart')?.dataset.chartMaxY || 0),
        circles: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
        activeUniverse: document.querySelector('[data-universe].active')?.dataset.universe || '',
        gutterWidth: stageRect.right - svgRect.right,
        controlOutsideSvg: controlRect.left >= svgRect.right && sliderRect.left >= svgRect.right,
        slider: {
          present: Boolean(slider),
          visible: Boolean(slider && style.display !== 'none' && sliderRect.width > 0 && sliderRect.height > 0),
          value: slider ? slider.value : null,
          min: slider ? Number(slider.min) : null,
          max: slider ? Number(slider.max) : null,
          vertical: Boolean(sliderRect && sliderRect.height > sliderRect.width),
          rightOfStageCenter: Boolean(sliderRect && stageRect && sliderRect.left > stageRect.left + stageRect.width / 2),
          ariaLabel: slider ? slider.getAttribute('aria-label') : null,
          readout: readout ? readout.textContent : null,
          rect: sliderRect ? { x: sliderRect.x, y: sliderRect.y, width: sliderRect.width, height: sliderRect.height } : null
        }
      };
    })())
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    return json.loads(result["result"]["value"])


def assert_slider_visibility(name, state, expect_visible):
    assert_true(state["loaded"], f"{name}: app did not finish loading: {state}")
    assert_true(state["circles"] >= 11, f"{name}: chart did not render markers: {state}")
    slider = state["slider"]
    assert_true(slider["present"], f"{name}: #chartZoomSlider is missing from the DOM")
    assert_true(slider["ariaLabel"] == "Chart axis range", f"{name}: slider aria label missing: {slider}")
    assert_true(slider["min"] == 1 and slider["max"] == 50, f"{name}: slider range must match SCALE_LIMITS: {slider}")
    if expect_visible:
        assert_true(slider["visible"], f"{name}: zoom slider should be visible: {slider}")
        assert_true(slider["vertical"], f"{name}: zoom slider must be vertical: {slider}")
        assert_true(slider["rightOfStageCenter"], f"{name}: zoom slider must sit on the right of the chart: {slider}")
        assert_true(state["controlOutsideSvg"], f"{name}: zoom control overlaps the SVG: {state}")
        assert_true(abs(state["gutterWidth"] - 48) < 0.01, f"{name}: expected a 48px chart gutter: {state}")
    else:
        assert_true(not slider["visible"], f"{name}: zoom slider must be hidden: {slider}")
        assert_true(abs(state["gutterWidth"]) < 0.01, f"{name}: hidden slider must not reserve chart width: {state}")


def verify_desktop_zoom(name, ws):
    initial = collect_state(ws)
    assert_true(initial["extent"] == 10 and initial["slider"]["value"] == "10", f"{name}: default extent must be 10: {initial}")
    assert_true(initial["slider"]["readout"] == "±10", f"{name}: default readout must be ±10: {initial['slider']}")
    assert_true(
        (initial["chartMin"], initial["chartMax"], initial["chartMinY"], initial["chartMaxY"]) == (90, 110, 90, 110),
        f"{name}: default axes must show 90-110 on both X and Y: {initial}",
    )
    marker_cx_before = first_marker_cx(ws)

    set_slider_value(ws, 20)
    zoomed_out = collect_state(ws)
    assert_true(zoomed_out["extent"] == 20 and zoomed_out["slider"]["value"] == "20", f"{name}: slider did not set extent 20: {zoomed_out}")
    assert_true(zoomed_out["slider"]["readout"] == "±20", f"{name}: readout must show ±20: {zoomed_out['slider']}")
    assert_true(
        (zoomed_out["chartMin"], zoomed_out["chartMax"]) == (80, 120),
        f"{name}: X axis must show 80-120 at extent 20: {zoomed_out}",
    )
    assert_true(
        (zoomed_out["chartMinY"], zoomed_out["chartMaxY"]) == (80, 120),
        f"{name}: Y axis must change together with X (80-120): {zoomed_out}",
    )
    assert_true(first_marker_cx(ws) != marker_cx_before, f"{name}: markers were not re-rendered after zoom")
    assert_true(zoomed_out["circles"] == initial["circles"], f"{name}: marker count changed after zoom: {zoomed_out}")

    set_slider_value(ws, 10)
    restored = collect_state(ws)
    assert_true(
        (restored["chartMin"], restored["chartMax"], restored["chartMinY"], restored["chartMaxY"]) == (90, 110, 90, 110),
        f"{name}: returning the slider to 10 must restore 90-110: {restored}",
    )

    pan_chart(ws, 150, -90)
    panned = collect_state(ws)
    assert_true(panned["extent"] == 10, f"{name}: pan must not change extent: {panned}")
    assert_true(
        panned["chartCenterX"] != 100 or panned["chartCenterY"] != 100,
        f"{name}: pan did not move the chart centre: {panned}",
    )

    set_slider_value(ws, 30)
    recentred = collect_state(ws)
    assert_true(
        recentred["chartCenterX"] == panned["chartCenterX"] and recentred["chartCenterY"] == panned["chartCenterY"],
        f"{name}: slider zoom must preserve the panned centre: {panned} -> {recentred}",
    )
    assert_true(
        abs(recentred["chartMin"] - (recentred["chartCenterX"] - 30)) < 0.01
        and abs(recentred["chartMax"] - (recentred["chartCenterX"] + 30)) < 0.01,
        f"{name}: X axis must expand around the current centre: {recentred}",
    )
    assert_true(
        abs(recentred["chartMinY"] - (recentred["chartCenterY"] - 30)) < 0.01
        and abs(recentred["chartMaxY"] - (recentred["chartCenterY"] + 30)) < 0.01,
        f"{name}: Y axis must expand around the current centre: {recentred}",
    )

    evaluate(ws, "(() => { document.getElementById('chartZoomSlider').focus(); return JSON.stringify({ ok: true }); })()")
    # Native vertical sliders map arrow keys visually: ArrowDown moves toward the
    # bottom (larger extent = zoom out), ArrowUp toward the top (zoom in).
    send_arrow_key(ws, "ArrowDown")
    after_arrow_down = collect_state(ws)
    assert_true(
        after_arrow_down["extent"] == 31 and after_arrow_down["slider"]["readout"] == "±31",
        f"{name}: ArrowDown must zoom out by one step: {after_arrow_down}",
    )
    send_arrow_key(ws, "ArrowUp")
    after_arrow_up = collect_state(ws)
    assert_true(
        after_arrow_up["extent"] == 30 and after_arrow_up["slider"]["readout"] == "±30",
        f"{name}: ArrowUp must zoom in by one step: {after_arrow_up}",
    )


def capture_themes_screenshot(ws):
    # Reload so the screenshot uses the default 100/100 chart centre.
    ws.call("Page.navigate", {"url": f"http://127.0.0.1:{browser_capture.PORT}/"})
    browser_capture.wait_for_render(ws)
    evaluate(ws, "(() => { document.querySelector('[data-universe=\"themes\"]').click(); return JSON.stringify({ ok: true }); })()")
    deadline = time.time() + 10
    themes = None
    while time.time() < deadline:
        themes = collect_state(ws)
        if themes["activeUniverse"] == "themes" and themes["circles"] >= 20 and themes["extent"] == 10:
            break
        time.sleep(0.2)
    assert_true(
        themes and themes["activeUniverse"] == "themes" and themes["circles"] >= 20,
        f"Themes universe did not render its markers: {themes}",
    )

    set_slider_value(ws, 20)
    wide = collect_state(ws)
    assert_true(
        (wide["chartMin"], wide["chartMax"], wide["chartMinY"], wide["chartMaxY"]) == (80, 120, 80, 120),
        f"Themes screenshot requires the 80-120 axis range: {wide}",
    )
    result = ws.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
    THEMES_SCREENSHOT.write_bytes(base64.b64decode(result["data"]))
    assert_true(THEMES_SCREENSHOT.stat().st_size > 0, "Themes zoom screenshot is empty")


def set_slider_value(ws, value):
    evaluate(
        ws,
        f"""
        (() => {{
          const slider = document.getElementById('chartZoomSlider');
          slider.value = '{value}';
          slider.dispatchEvent(new Event('input', {{ bubbles: true }}));
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    time.sleep(0.1)


def pan_chart(ws, delta_x, delta_y):
    evaluate(
        ws,
        f"""
        (() => {{
          const chart = document.querySelector('#rrgChart');
          const rect = chart.getBoundingClientRect();
          const startX = rect.left + rect.width / 2;
          const startY = rect.top + rect.height / 2;
          const endX = startX + {delta_x};
          const endY = startY + {delta_y};
          const pointer = (type, x, y) => new PointerEvent(type, {{
            bubbles: true,
            cancelable: true,
            pointerId: 71,
            pointerType: 'mouse',
            isPrimary: true,
            clientX: x,
            clientY: y,
            buttons: type === 'pointerup' ? 0 : 1
          }});
          chart.dispatchEvent(pointer('pointerdown', startX, startY));
          chart.dispatchEvent(pointer('pointermove', endX, endY));
          chart.dispatchEvent(pointer('pointerup', endX, endY));
          return JSON.stringify({{ ok: true }});
        }})()
        """,
    )
    time.sleep(0.1)


def send_arrow_key(ws, key):
    code = 38 if key == "ArrowUp" else 40 if key == "ArrowDown" else 0
    assert_true(code != 0, f"Unsupported key for slider audit: {key}")
    for type_ in ("keyDown", "keyUp"):
        ws.call(
            "Input.dispatchKeyEvent",
            {"type": type_, "key": key, "code": key, "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code},
        )
    time.sleep(0.1)


def first_marker_cx(ws):
    value = evaluate(
        ws,
        "String(Number(document.querySelector('#rrgChart circle[data-symbol]')?.getAttribute('cx') || 0))",
    )
    return float(value)


def evaluate(ws, expression):
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
    value = result.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"Evaluation did not return a value: {result}")
    return value


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
