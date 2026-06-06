import base64
import argparse
import json
import os
import pathlib
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 4173
CDP_PORT = 9223
DEFAULT_OUT = ROOT / "rgg-ipad-mini.png"


def main():
    parser = argparse.ArgumentParser(description="Capture the RGG app through headless Chrome DevTools.")
    parser.add_argument("--width", type=int, default=744)
    parser.add_argument("--height", type=int, default=1133)
    parser.add_argument("--scale", type=float, default=2)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument("--mobile", action="store_true")
    args = parser.parse_args()

    width = args.width
    height = args.height
    scale = args.scale
    mobile = args.mobile
    out = args.out if args.out.is_absolute() else ROOT / args.out
    browser = find_browser()
    server = QuietHTTPServer(("127.0.0.1", PORT), QuietHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    profile = tempfile.mkdtemp(prefix=".browser-profile-", dir=ROOT)
    process = subprocess.Popen(
        [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"http://127.0.0.1:{PORT}/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        page = wait_for_page()
        ws = WebSocket(page["webSocketDebuggerUrl"])
        try:
            ws.call("Page.enable")
            if mobile:
                ws.call(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": width,
                        "height": height,
                        "deviceScaleFactor": scale,
                        "mobile": True,
                        "screenWidth": width,
                        "screenHeight": height,
                    },
                )
            ws.call("Page.navigate", {"url": f"http://127.0.0.1:{PORT}/"})
            wait_for_render(ws)
            result = ws.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
            out.write_bytes(base64.b64decode(result["data"]))

            counts = evaluate_counts(ws)
            if counts["markers"] < 11 or counts["tails"] < 11 or counts["tailDots"] < 11 or not counts["loaded"]:
                raise RuntimeError(f"Rendered app did not pass screenshot smoke checks: {counts}")

            print(
                f"Screenshot captured: {out} bytes={out.stat().st_size} "
                f"markers={counts['markers']} tails={counts['tails']} tailDots={counts['tailDots']}"
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


class QuietHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, *_):
        pass


class QuietHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


def find_browser():
    candidates = [
        pathlib.Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        pathlib.Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return pathlib.Path(found)
    raise RuntimeError("No Chrome or Edge executable found.")


def wait_for_page():
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=1) as response:
                pages = json.loads(response.read().decode("utf-8"))
            for page in pages:
                if page.get("type") == "page":
                    return page
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("Timed out waiting for Chrome DevTools page.")


def wait_for_render(ws):
    deadline = time.time() + 20
    while time.time() < deadline:
        counts = evaluate_counts(ws)
        if counts["loaded"] and counts["markers"] >= 11 and counts["tails"] >= 11 and counts["tailDots"] >= 11:
            return
        time.sleep(0.25)
    raise RuntimeError("Timed out waiting for rendered RGG chart.")


def evaluate_counts(ws):
    expression = """
    JSON.stringify({
      loaded: document.querySelector('#dataStatus')?.textContent.includes('RRG data loaded') || false,
      markers: document.querySelectorAll('#rrgChart circle[data-symbol]').length,
      tailDots: document.querySelectorAll('#rrgChart circle[data-tail-dot]').length,
      tails: document.querySelectorAll('#rrgChart path[data-tail-path]').length,
      quadrants: ['Leading', 'Weakening', 'Lagging', 'Improving'].every((label) => document.body.innerText.includes(label))
    })
    """
    result = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
    value = result.get("result", {}).get("value")
    if not value:
        return {"loaded": False, "markers": 0, "tailDots": 0, "tails": 0, "quadrants": False}
    return json.loads(value)


class WebSocket:
    def __init__(self, url):
        if not url.startswith("ws://"):
            raise ValueError("Only local ws:// URLs are supported.")
        rest = url.removeprefix("ws://")
        host_port, path = rest.split("/", 1)
        host, port = host_port.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=10)
        self.next_id = 1
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET /{path} HTTP/1.1\r\n"
            f"Host: {host_port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError(f"WebSocket handshake failed: {response[:200]!r}")

    def call(self, method, params=None):
        message_id = self.next_id
        self.next_id += 1
        self.send({"id": message_id, "method": method, "params": params or {}})
        while True:
            message = self.recv()
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})

    def send(self, payload):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = bytearray([0x81])
        if len(data) < 126:
            header.append(0x80 | len(data))
        elif len(data) < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", len(data)))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", len(data)))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(header + masked)

    def recv(self):
        chunks = []
        while True:
            first, second = self._read_exact(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            masked = second & 0x80
            mask = self._read_exact(4) if masked else b""
            data = self._read_exact(length)
            if masked:
                data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
            if opcode == 0x8:
                raise RuntimeError("WebSocket closed.")
            if opcode in (0x1, 0x0):
                chunks.append(data)
                if first & 0x80:
                    return json.loads(b"".join(chunks).decode("utf-8"))

    def _read_exact(self, count):
        data = b""
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise RuntimeError("Socket closed.")
            data += chunk
        return data

    def close(self):
        self.sock.close()


if __name__ == "__main__":
    main()
