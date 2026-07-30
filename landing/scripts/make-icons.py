#!/usr/bin/env python3
"""Generate the Capitol Ledger marks from geometric definitions.

Writes into ``landing/public/``:

  favicon.svg        vector source (what modern browsers use)
  favicon.ico        16 + 32 + 48 px, 32-bit BGRA — the file Google's favicon
                     crawler and old shells look for at the site root
  favicon-96.png     96 px PNG for consumers that prefer a raster hint
  apple-touch-icon.png  180 px, iOS home-screen
  dome.svg           the Capitol-dome mark on its own, in currentColor
  avatar-dome.png    400 px social avatar — dome in paper on stamp red

TWO marks, on purpose:

* The **CL monogram** is the favicon. At 16 px — the only size a favicon is ever
  actually seen at — two blocky letters stay legible where a colonnade and three
  hairline rules turn to mush.
* The **dome** is the social avatar, where the smallest real size is ~28 px and
  400 px is available. It is the Capitol sitting on three ledger rules: the
  building and the record, which is the whole name in one mark.

Neither uses <text>, so neither depends on a font being installed.

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


# ── The dome mark ────────────────────────────────────────────────────────────
# A 64-unit grid. Every element sits inside a circle of radius ~30 centred on
# (32, 32): social platforms crop an avatar to a circle, so anything out near
# the corners of the square gets sliced off. (That is why the favicon's own
# edge-to-edge monogram is NOT reused here — a circle crop would clip the C.)
DOME_GRID = 64
DOME_FINIAL = (32, 7.2, 1.9)              # cx, cy, r — the statue, abstracted
DOME_ELLIPSE = (32, 32, 13, 15.5)         # cx, cy(base), rx, ry — upper half
DOME_BARS = [
    (31, 9, 2, 4),                        # spire
    (28.5, 13, 7, 3.5),                   # lantern / cupola
    (17, 32, 30, 3),                      # drum band under the dome
    (20, 36.5, 4, 6.5), (26.7, 36.5, 4, 6.5),        # colonnade
    (33.3, 36.5, 4, 6.5), (40, 36.5, 4, 6.5),
    (15, 45.5, 34, 2.6),                  # three ledger rules — the record
    (15, 50, 34, 2.6),
    (15, 54.5, 34, 2.6),
]
def _n(v: float) -> str:
    """Trim 2.0 to "2" so the path stays readable."""
    return f"{v:g}"


def dome_path() -> str:
    """SVG path, DERIVED from the shape lists above.

    Deliberately generated rather than hand-written: the rasterizer reads the
    lists and the vector file reads the path, so a hand-kept path is a second
    definition of the same mark that silently drifts the moment one is edited.
    """
    cx, cy, r = DOME_FINIAL
    parts = [
        # Full circle as two half-arcs.
        f"M{_n(cx - r)} {_n(cy)}"
        f"a{_n(r)} {_n(r)} 0 1 0 {_n(2 * r)} 0"
        f"a{_n(r)} {_n(r)} 0 1 0 {_n(-2 * r)} 0z"
    ]
    ex, ey, rx, ry = DOME_ELLIPSE
    parts.append(
        f"M{_n(ex - rx)} {_n(ey)}A{_n(rx)} {_n(ry)} 0 0 1 {_n(ex + rx)} {_n(ey)}z"
    )
    for bx, by, bw, bh in DOME_BARS:
        parts.append(f"M{_n(bx)} {_n(by)}h{_n(bw)}v{_n(bh)}h{_n(-bw)}z")
    return "".join(parts)


def dome_svg() -> str:
    """The dome alone, in currentColor so the site can reuse it inline."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        'width="64" height="64" role="img" aria-label="Capitol Ledger">'
        f'<path d="{dome_path()}" fill="currentColor"/>'
        "</svg>\n"
    )


def _dome_inside(x, y) -> bool:
    """Is the point inside the mark? Used by the supersampling rasterizer."""
    fx, fy, fr = DOME_FINIAL
    if (x - fx) ** 2 + (y - fy) ** 2 <= fr * fr:
        return True
    ex, ey, rx, ry = DOME_ELLIPSE
    if y <= ey and ((x - ex) / rx) ** 2 + ((y - ey) / ry) ** 2 <= 1:
        return True
    return any(bx <= x <= bx + bw and by <= y <= by + bh
               for bx, by, bw, bh in DOME_BARS)


def render_dome(size: int, samples: int = 4):
    """Rasterize the dome to `size` px, paper on stamp red.

    Supersampled rather than area-exact: unlike the monogram this mark contains
    a circle and a half-ellipse, and `samples`² subsamples per pixel is well
    past visually lossless at the sizes this is used (400 px and up).
    """
    step = DOME_GRID / size
    sub = step / samples
    rows = []
    for py in range(size):
        row = []
        for px in range(size):
            hits = sum(
                _dome_inside(px * step + (sx + 0.5) * sub,
                             py * step + (sy + 0.5) * sub)
                for sy in range(samples) for sx in range(samples)
            )
            a = hits / (samples * samples)
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
    (PUBLIC / "dome.svg").write_text(dome_svg(), encoding="utf-8")
    write_png(PUBLIC / "avatar-dome.png", render_dome(400))
    for name in ("favicon.svg", "favicon.ico", "favicon-96.png",
                 "apple-touch-icon.png", "dome.svg", "avatar-dome.png"):
        print(f"{name}: {(PUBLIC / name).stat().st_size} bytes")


if __name__ == "__main__":
    main()
