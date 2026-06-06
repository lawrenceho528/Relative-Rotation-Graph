import pathlib
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PORT = 4183


def main():
    if not DIST.exists():
        raise RuntimeError("dist does not exist. Run scripts/deploy-audit.ps1 first.")

    server = ThreadingHTTPServer(("127.0.0.1", PORT), DistHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        command = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / "install-preflight.ps1"),
            "-BaseUrl",
            f"http://127.0.0.1:{PORT}",
        ]
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise RuntimeError((result.stdout + result.stderr).strip())
        print(result.stdout.strip())
    finally:
        server.shutdown()
        server.server_close()


class DistHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    main()
