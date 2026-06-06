import argparse
import html
import pathlib
from urllib.parse import urlparse


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "ipad-qr-handoff.html"

# QR Code Model 2, error correction level L. Versions 1-9 use an 8-bit byte
# count and keep the implementation compact while covering ordinary hosted URLs.
CAPACITY = {
    1: (19, 7, 1),
    2: (34, 10, 1),
    3: (55, 15, 1),
    4: (80, 20, 1),
    5: (108, 26, 1),
    6: (136, 18, 2),
    7: (156, 20, 2),
    8: (194, 24, 2),
    9: (232, 30, 2),
}

ALIGNMENT = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
}


def main():
    args = parse_args()
    url = args.url.strip()
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise SystemExit(f"iPad install QR handoff requires an HTTPS URL: {url}")

    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = ROOT / out

    svg = make_qr_svg(url)
    page = make_page(url, svg)
    out.write_text(page, encoding="utf-8")
    print(f"iPad QR handoff written: {out}")


def parse_args():
    parser = argparse.ArgumentParser(description="Create an offline QR handoff page for iPad Safari install testing.")
    parser.add_argument("url", help="Hosted HTTPS app URL to open on the iPad")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output HTML path")
    return parser.parse_args()


def make_page(url, svg):
    safe_url = html.escape(url, quote=True)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>RGG Rotation iPad Handoff</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #101522;
        color: #f5f7fb;
        font-family: Arial, sans-serif;
      }}
      main {{
        width: min(760px, calc(100vw - 32px));
        text-align: center;
      }}
      h1 {{
        margin: 0 0 10px;
        font-size: 32px;
      }}
      p {{
        color: #aeb8c9;
        line-height: 1.5;
      }}
      .qr {{
        display: inline-block;
        margin: 22px 0;
        padding: 18px;
        background: #fff;
        border-radius: 8px;
      }}
      .url {{
        overflow-wrap: anywhere;
        font-size: 15px;
      }}
      a {{
        color: #58d5d1;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>RGG Rotation iPad Handoff</h1>
      <p>Scan this QR code with the A2993 iPad, open the HTTPS URL in Safari, then use Share &gt; Add to Home Screen.</p>
      <div class="qr" aria-label="QR code for hosted RGG Rotation app">
{svg}
      </div>
      <p class="url"><a href="{safe_url}">{safe_url}</a></p>
    </main>
  </body>
</html>
"""


def make_qr_svg(text):
    data = text.encode("utf-8")
    version = choose_version(len(data))
    matrix, function = make_blank(version)
    draw_function_patterns(matrix, function, version)
    codewords = make_codewords(data, version)
    draw_codewords(matrix, function, codewords)
    apply_mask(matrix, function, 0)
    draw_format_bits(matrix, function, 0)
    if version >= 7:
        draw_version_bits(matrix, function, version)
    return to_svg(matrix)


def choose_version(byte_count):
    for version, (data_codewords, _ecc_codewords, _blocks) in CAPACITY.items():
        bit_count = 4 + 8 + byte_count * 8
        if bit_count <= data_codewords * 8:
            return version
    raise SystemExit("URL is too long for the built-in QR handoff generator. Use a shorter hosted URL.")


def make_blank(version):
    size = version * 4 + 17
    return [[False] * size for _ in range(size)], [[False] * size for _ in range(size)]


def set_function(matrix, function, row, col, value):
    matrix[row][col] = value
    function[row][col] = True


def draw_function_patterns(matrix, function, version):
    size = len(matrix)
    draw_finder(matrix, function, 3, 3)
    draw_finder(matrix, function, size - 4, 3)
    draw_finder(matrix, function, 3, size - 4)

    for i in range(8):
        set_if_in_bounds(matrix, function, 7, i, False)
        set_if_in_bounds(matrix, function, i, 7, False)
        set_if_in_bounds(matrix, function, size - 8, i, False)
        set_if_in_bounds(matrix, function, size - 1 - i, 7, False)
        set_if_in_bounds(matrix, function, 7, size - 1 - i, False)
        set_if_in_bounds(matrix, function, i, size - 8, False)

    for i in range(8, size - 8):
        bit = i % 2 == 0
        set_function(matrix, function, 6, i, bit)
        set_function(matrix, function, i, 6, bit)

    for row in ALIGNMENT[version]:
        for col in ALIGNMENT[version]:
            if function[row][col]:
                continue
            draw_alignment(matrix, function, row, col)

    set_function(matrix, function, size - 8, 8, True)
    for i in range(9):
        if not function[8][i]:
            set_function(matrix, function, 8, i, False)
        if not function[i][8]:
            set_function(matrix, function, i, 8, False)
    for i in range(8):
        if not function[8][size - 1 - i]:
            set_function(matrix, function, 8, size - 1 - i, False)
        if not function[size - 1 - i][8]:
            set_function(matrix, function, size - 1 - i, 8, False)


def set_if_in_bounds(matrix, function, row, col, value):
    size = len(matrix)
    if 0 <= row < size and 0 <= col < size:
        set_function(matrix, function, row, col, value)


def draw_finder(matrix, function, center_row, center_col):
    for row in range(center_row - 3, center_row + 4):
        for col in range(center_col - 3, center_col + 4):
            value = max(abs(row - center_row), abs(col - center_col)) != 2
            set_function(matrix, function, row, col, value)


def draw_alignment(matrix, function, center_row, center_col):
    for row in range(center_row - 2, center_row + 3):
        for col in range(center_col - 2, center_col + 3):
            value = max(abs(row - center_row), abs(col - center_col)) != 1
            set_function(matrix, function, row, col, value)


def make_codewords(data, version):
    data_codewords, ecc_codewords, blocks = CAPACITY[version]
    bits = [0, 1, 0, 0]
    bits.extend(int(bit) for bit in f"{len(data):08b}")
    for byte in data:
        bits.extend(int(bit) for bit in f"{byte:08b}")
    bits.extend([0] * min(4, data_codewords * 8 - len(bits)))
    while len(bits) % 8:
        bits.append(0)

    words = [bits[i] << 7 | bits[i + 1] << 6 | bits[i + 2] << 5 | bits[i + 3] << 4 |
             bits[i + 4] << 3 | bits[i + 5] << 2 | bits[i + 6] << 1 | bits[i + 7]
             for i in range(0, len(bits), 8)]
    pads = [0xEC, 0x11]
    index = 0
    while len(words) < data_codewords:
        words.append(pads[index % 2])
        index += 1

    block_len = data_codewords // blocks
    data_blocks = [words[i * block_len:(i + 1) * block_len] for i in range(blocks)]
    divisor = reed_solomon_divisor(ecc_codewords)
    ecc_blocks = [reed_solomon_remainder(block, divisor) for block in data_blocks]

    result = []
    for i in range(max(len(block) for block in data_blocks)):
        for block in data_blocks:
            if i < len(block):
                result.append(block[i])
    for i in range(ecc_codewords):
        for block in ecc_blocks:
            result.append(block[i])
    return result


def draw_codewords(matrix, function, codewords):
    bits = []
    for word in codewords:
        bits.extend((word >> shift) & 1 for shift in range(7, -1, -1))

    size = len(matrix)
    bit_index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        for vertical in range(size):
            row = size - 1 - vertical if upward else vertical
            for offset in range(2):
                c = col - offset
                if function[row][c]:
                    continue
                matrix[row][c] = bit_index < len(bits) and bits[bit_index] == 1
                bit_index += 1
        upward = not upward
        col -= 2


def apply_mask(matrix, function, mask):
    for row in range(len(matrix)):
        for col in range(len(matrix)):
            if not function[row][col] and mask_bit(mask, row, col):
                matrix[row][col] = not matrix[row][col]


def mask_bit(mask, row, col):
    if mask == 0:
        return (row + col) % 2 == 0
    raise ValueError(mask)


def draw_format_bits(matrix, function, mask):
    size = len(matrix)
    data = (1 << 3) | mask  # Error correction L = 01
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = ((data << 10) | rem) ^ 0x5412

    for i in range(15):
        bit = ((bits >> i) & 1) == 1
        if i < 6:
            set_function(matrix, function, 8, i, bit)
        elif i < 8:
            set_function(matrix, function, 8, i + 1, bit)
        else:
            set_function(matrix, function, 8, size - 15 + i, bit)

        if i < 8:
            set_function(matrix, function, size - 1 - i, 8, bit)
        else:
            set_function(matrix, function, 15 - i, 8, bit)

    set_function(matrix, function, size - 8, 8, True)


def draw_version_bits(matrix, function, version):
    size = len(matrix)
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
    bits = (version << 12) | rem
    for i in range(18):
        bit = ((bits >> i) & 1) == 1
        row = size - 11 + i % 3
        col = i // 3
        set_function(matrix, function, row, col, bit)
        set_function(matrix, function, col, row, bit)


def reed_solomon_divisor(degree):
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for i in range(degree):
            result[i] = gf_multiply(result[i], root)
            if i + 1 < degree:
                result[i] ^= result[i + 1]
        root = gf_multiply(root, 0x02)
    return result


def reed_solomon_remainder(data, divisor):
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coefficient in enumerate(divisor):
            result[i] ^= gf_multiply(coefficient, factor)
    return result


def gf_multiply(x, y):
    result = 0
    for _ in range(8):
        if y & 1:
            result ^= x
        carry = x & 0x80
        x = (x << 1) & 0xFF
        if carry:
            x ^= 0x1D
        y >>= 1
    return result


def to_svg(matrix):
    quiet = 4
    size = len(matrix)
    view = size + quiet * 2
    rects = []
    for row, cells in enumerate(matrix):
        for col, value in enumerate(cells):
            if value:
                rects.append(f'<rect x="{col + quiet}" y="{row + quiet}" width="1" height="1" />')
    body = "\n        ".join(rects)
    return f'        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view} {view}" width="360" height="360" role="img" aria-label="Hosted app URL QR code"><rect width="{view}" height="{view}" fill="#fff" /><g fill="#000">\n        {body}\n        </g></svg>'


if __name__ == "__main__":
    main()
