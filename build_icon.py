"""Generate resources/icon.ico for the PyInstaller build."""
import struct
import zlib
from pathlib import Path


def _make_png(w: int, h: int) -> bytes:
    """Create a minimal RGBA PNG of a green rounded-square with a download arrow."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            cx, cy = w // 2, h // 2
            margin = max(1, w // 20)
            radius = w // 5
            def _dist(px, py, rx, ry):
                return max(abs(px - rx) - radius, 0) ** 2 + max(abs(py - ry) - radius, 0) ** 2
            inside = False
            for rx in (margin + radius, w - margin - radius):
                for ry in (margin + radius, h - margin - radius):
                    if _dist(x, y, rx, ry) <= radius * radius:
                        inside = True
            if margin <= x < w - margin and margin <= y < h - margin and inside:
                r, g, b, a = 45, 125, 70, 255
                if cx - w // 10 < x < cx + w // 10 and h // 4 < y < h * 3 // 5:
                    r, g, b, a = 255, 255, 255, 255
                arrow_head = y >= h * 3 // 5
                dx = abs(x - cx)
                line_y = y - (h * 3 // 5)
                if arrow_head and dx <= line_y:
                    r, g, b, a = 255, 255, 255, 255
            else:
                r, g, b, a = 0, 0, 0, 0
            raw.extend([r, g, b, a])

    def _chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr) + _chunk(b'IDAT', zlib.compress(bytes(raw))) + _chunk(b'IEND', b'')


def _make_ico() -> bytes:
    sizes = [256, 64, 48, 32]
    pngs = {s: _make_png(s, s) for s in sizes}
    count = len(sizes)
    header = struct.pack('<HHH', 0, 1, count)
    entries = bytearray()
    offset = 6 + 16 * count
    for s in sizes:
        data = pngs[s]
        w = 0 if s == 256 else s
        h = 0 if s == 256 else s
        entries.extend(struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    result = header + bytes(entries)
    for s in sizes:
        result += pngs[s]
    return result


def main():
    out = Path(__file__).parent / 'resources' / 'icon.ico'
    out.write_bytes(_make_ico())
    print(f'Icon generated: {out}')


if __name__ == '__main__':
    main()
