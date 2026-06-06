import hashlib
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ipad-qr-handoff.py"
OUT_A = ROOT / "deploy" / "ipad-qr-handoff-a.html"
OUT_B = ROOT / "deploy" / "ipad-qr-handoff-b.html"
URL = "https://example.com/rgg"


def main():
    check_https_guard()
    first = generate(OUT_A)
    second = generate(OUT_B)
    if sha256(first) != sha256(second):
        raise AssertionError("QR handoff output is not deterministic for the same URL")

    text = first.read_text(encoding="utf-8")
    rects = text.count("<rect")
    view_box = re.search(r'viewBox="0 0 (\d+) \1"', text)
    if URL not in text:
        raise AssertionError("QR handoff page does not contain the hosted URL")
    if rects <= 100:
        raise AssertionError(f"QR handoff SVG has too few dark modules: {rects}")
    if not view_box or int(view_box.group(1)) < 29:
        raise AssertionError("QR handoff SVG viewBox is missing or too small")
    if 'aria-label="Hosted app URL QR code"' not in text:
        raise AssertionError("QR handoff SVG is missing its accessible label")

    OUT_B.unlink(missing_ok=True)
    print(
        "QR handoff audit passed: "
        f"bytes={first.stat().st_size} rects={rects} sha256={sha256(first)}"
    )


def check_https_guard():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "http://example.com/rgg", "--out", str(ROOT / "deploy" / "bad-qr.html")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise AssertionError("QR handoff helper accepted an HTTP URL")
    if "requires an HTTPS URL" not in (result.stderr + result.stdout):
        raise AssertionError(f"QR handoff helper rejected HTTP with unexpected output: {result.stderr}{result.stdout}")


def generate(path):
    path.parent.mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(SCRIPT), URL, "--out", str(path)], cwd=ROOT, check=True)
    if not path.exists():
        raise AssertionError(f"QR handoff helper did not write {path}")
    return path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


if __name__ == "__main__":
    main()
