import pathlib
import struct
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCREENSHOTS = [
    ("portrait", ROOT / "rgg-ipad-mini-portrait.png", "portrait", 700, 900),
    ("landscape", ROOT / "rgg-ipad-mini-landscape.png", "landscape", 1000, 560),
]

QUADRANT_COLORS = {
    "improving": (0xE8, 0xF1, 0xFF),
    "leading": (0xE8, 0xF7, 0xEE),
    "lagging": (0xFF, 0xF0, 0xF0),
    "weakening": (0xFF, 0xF7, 0xDA),
}


def main():
    summaries = []
    for name, path, orientation, min_width, min_height in SCREENSHOTS:
        image = read_png(path)
        assert_dimensions(name, image, orientation, min_width, min_height)

        metrics = collect_metrics(image["pixels"])
        assert_visual_quality(name, metrics)
        summaries.append(
            f"{name}: unique={metrics['unique']} "
            f"chartPixels={metrics['chartPixels']} colored={metrics['coloredPixels']}"
        )

    print("Visual audit passed: " + ", ".join(summaries))


def assert_dimensions(name, image, orientation, min_width, min_height):
    width = image["width"]
    height = image["height"]

    if width < min_width or height < min_height:
        raise AssertionError(f"{name}: screenshot is too small: {width}x{height}")
    if orientation == "portrait" and width >= height:
        raise AssertionError(f"{name}: expected portrait screenshot, got {width}x{height}")
    if orientation == "landscape" and width <= height:
        raise AssertionError(f"{name}: expected landscape screenshot, got {width}x{height}")


def read_png(path):
    if not path.exists():
        raise AssertionError(f"missing screenshot: {path}")

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"not a PNG file: {path}")

    offset = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()

    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            if bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
                raise AssertionError(
                    f"unsupported PNG format: bitDepth={bit_depth} colorType={color_type} interlace={interlace}"
                )
            if compression != 0 or filter_method != 0:
                raise AssertionError("unsupported PNG compression/filter method")
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break

    channels = 3 if color_type == 2 else 4
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    pixels = []
    previous = bytearray(stride)
    cursor = 0

    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        row = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        unfilter(row, previous, channels, filter_type)
        for index in range(0, stride, channels):
            pixels.append(tuple(row[index : index + 3]))
        previous = row

    return {"width": width, "height": height, "pixels": pixels}


def unfilter(row, previous, bpp, filter_type):
    for index, value in enumerate(row):
        left = row[index - bpp] if index >= bpp else 0
        up = previous[index]
        up_left = previous[index - bpp] if index >= bpp else 0

        if filter_type == 0:
            predictor = 0
        elif filter_type == 1:
            predictor = left
        elif filter_type == 2:
            predictor = up
        elif filter_type == 3:
            predictor = (left + up) // 2
        elif filter_type == 4:
            predictor = paeth(left, up, up_left)
        else:
            raise AssertionError(f"unsupported PNG filter: {filter_type}")

        row[index] = (value + predictor) & 0xFF


def paeth(left, up, up_left):
    estimate = left + up - up_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    up_left_distance = abs(estimate - up_left)
    if left_distance <= up_distance and left_distance <= up_left_distance:
        return left
    if up_distance <= up_left_distance:
        return up
    return up_left


def collect_metrics(pixels):
    unique = set()
    dark = 0
    light = 0
    colored = 0
    chart_pixels = 0
    quadrant_hits = {name: 0 for name in QUADRANT_COLORS}

    for red, green, blue in pixels:
        unique.add((red, green, blue))
        total = red + green + blue
        spread = max(red, green, blue) - min(red, green, blue)

        if total < 150:
            dark += 1
        if total > 690:
            light += 1
        if spread > 35:
            colored += 1
        if is_near((red, green, blue), (0xF4, 0xF7, 0xFB), tolerance=18):
            chart_pixels += 1

        for name, color in QUADRANT_COLORS.items():
            if is_near((red, green, blue), color, tolerance=7):
                quadrant_hits[name] += 1

    return {
        "unique": len(unique),
        "darkPixels": dark,
        "lightPixels": light,
        "coloredPixels": colored,
        "chartPixels": chart_pixels,
        "quadrantHits": quadrant_hits,
    }


def assert_visual_quality(name, metrics):
    total_quadrant_pixels = sum(metrics["quadrantHits"].values())

    if metrics["unique"] < 600:
        raise AssertionError(f"{name}: screenshot looks too flat: {metrics}")
    if metrics["darkPixels"] < 20_000:
        raise AssertionError(f"{name}: missing dark app chrome pixels: {metrics}")
    if metrics["lightPixels"] < 80_000:
        raise AssertionError(f"{name}: missing bright chart area pixels: {metrics}")
    if metrics["coloredPixels"] < 40_000:
        raise AssertionError(f"{name}: missing colored chart/label pixels: {metrics}")
    if metrics["chartPixels"] < 20_000:
        raise AssertionError(f"{name}: missing chart background pixels: {metrics}")
    if total_quadrant_pixels < 60_000:
        raise AssertionError(f"{name}: missing RRG quadrant fill pixels: {metrics}")
    if any(count < 5_000 for count in metrics["quadrantHits"].values()):
        raise AssertionError(f"{name}: not all four quadrant colors are visible: {metrics}")


def is_near(actual, expected, tolerance):
    return all(abs(channel - target) <= tolerance for channel, target in zip(actual, expected))


if __name__ == "__main__":
    main()
