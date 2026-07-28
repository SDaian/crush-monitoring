#!/usr/bin/env python3
"""Generate the Capitol Ledger icon set from one geometric definition.

Writes into ``landing/public/``:

  favicon.svg        vector source (what modern browsers use)
  favicon.ico        16 + 32 + 48 px, 32-bit BGRA — the file Google's favicon
                     crawler and old shells look for at the site root
  favicon-96.png     96 px PNG for consumers that prefer a raster hint
  apple-touch-icon.png  180 px, iOS home-screen

The mark is the "CL" monogram drawn as blocky, axis-aligned bars — no <text>,
so it never depends on a font being installed, and it survives being scaled
down to 16 px where a hairline typeface would turn to mush. Because every shape
is a rectangle the rasterizer below is *exact*: each output pixel's alpha is the
true area the shape covers, so there is no sampling noise at any size.

Run: python3 landing/scripts/make-icons.py
"""

import pathlib
import struct
import zlib

PUBLIC = pathlib.Path(__file__).resolve().parent.parent / "public"

GRID = 32                      # the SVG viewBox both coordinates live in
STAMP = (0xC8, 0x10, 0x2E)     # --color-stamp
PAPER = (0xFB, 0xFB, 0xF9)     # --color-paper

# (x, y, w, h) bars, in GRID units. C = left stem + two arms; L = stem + foot.
BARS = [
    (3, 5, 5, 22), (8, 5, 6, 5), (8, 22, 6, 5),    # C
    (17, 5, 5, 17), (17, 22, 12, 5),               # L
]


def svg() -> str:
    """The vector source. Bars are merged into two paths, one per letter."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" '
        'width="32" height="32" role="img" aria-label="Capitol Ledger">'
        f'<rect width="32" height="32" fill="#{STAMP[0]:02X}{STAMP[1]:02X}{STAMP[2]:02X}"/>'
        f'<path d="M3 5h11v5H8v12h6v5H3z" fill="#{PAPER[0]:02X}{PAPER[1]:02X}{PAPER[2]:02X}"/>'
        f'<path d="M17 5h5v17h7v5H17z" fill="#{PAPER[0]:02X}{PAPER[1]:02X}{PAPER[2]:02X}"/>'
        "</svg>\n"
    )


def _coverage(x0, x1, y0, y1) -> float:
    """Fraction of the box [x0,x1]x[y0,y1] (GRID units) covered by the bars."""
    area = 0.0
    for bx, by, bw, bh in BARS:
        ox = min(x1, bx + bw) - max(x0, bx)
        oy = min(y1, by + bh) - max(y0, by)
        if ox > 0 and oy > 0:
            area += ox * oy
    return area / ((x1 - x0) * (y1 - y0))


def render(size: int):
    """Rasterize to `size` px. Returns rows of opaque (r, g, b, 255) tuples."""
    step = GRID / size
    rows = []
    for py in range(size):
        y0, y1 = py * step, (py + 1) * step
        row = []
        for px in range(size):
            a = _coverage(px * step, (px + 1) * step, y0, y1)
            row.append(tuple(round(p * a + s * (1 - a))
                             for p, s in zip(PAPER, STAMP)) + (255,))
        rows.append(row)
    return rows


def _chunk(tag: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + tag + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))


def write_png(path, rows):
    h, w = len(rows), len(rows[0])
    raw = bytearray()
    for row in rows:
        raw.append(0)                       # filter type 0 (None)
        for px in row:
            raw += bytes(px)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


def _dib(rows) -> bytes:
    """40-byte BITMAPINFOHEADER + bottom-up BGRA pixels + an empty AND mask."""
    h, w = len(rows), len(rows[0])
    head = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, w * h * 4,
                       0, 0, 0, 0)
    px = bytearray()
    for row in reversed(rows):
        for r, g, b, a in row:
            px += bytes((b, g, r, a))
    mask_stride = ((w + 31) // 32) * 4      # 1 bpp, padded to 4 bytes
    return head + bytes(px) + bytes(mask_stride * h)


def write_ico(path, sizes):
    """Classic BMP-payload .ico (not PNG-in-ico) for maximum reader support."""
    blobs = [(n, _dib(render(n))) for n in sizes]
    offset = 6 + 16 * len(blobs)
    out = struct.pack("<HHH", 0, 1, len(blobs))
    body = b""
    for n, blob in blobs:
        out += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32,
                           len(blob), offset)
        offset += len(blob)
        body += blob
    path.write_bytes(out + body)


def main():
    (PUBLIC / "favicon.svg").write_text(svg(), encoding="utf-8")
    write_ico(PUBLIC / "favicon.ico", (16, 32, 48))
    write_png(PUBLIC / "favicon-96.png", render(96))
    write_png(PUBLIC / "apple-touch-icon.png", render(180))
    for name in ("favicon.svg", "favicon.ico", "favicon-96.png",
                 "apple-touch-icon.png"):
        print(f"{name}: {(PUBLIC / name).stat().st_size} bytes")


if __name__ == "__main__":
    main()
