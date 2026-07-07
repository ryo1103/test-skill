from __future__ import annotations

import struct
import zlib
from pathlib import Path


def write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)


def write_png_rgba(path: Path, width: int, height: int, pixels: bytearray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(pixels[y * stride : (y + 1) * stride])
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)


def chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack("!I", len(payload)) + kind + payload + struct.pack("!I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def blank(width: int, height: int, color: tuple[int, int, int] = (0, 0, 0)) -> bytearray:
    pixels = bytearray(width * height * 3)
    r, g, b = color
    for index in range(0, len(pixels), 3):
        pixels[index] = r
        pixels[index + 1] = g
        pixels[index + 2] = b
    return pixels


def transparent(width: int, height: int) -> bytearray:
    return bytearray(width * height * 4)


def rect(pixels: bytearray, width: int, height: int, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    r, g, b = color
    x0 = max(0, min(width, x))
    y0 = max(0, min(height, y))
    x1 = max(0, min(width, x + w))
    y1 = max(0, min(height, y + h))
    for yy in range(y0, y1):
        row = yy * width * 3
        for xx in range(x0, x1):
            idx = row + xx * 3
            pixels[idx] = r
            pixels[idx + 1] = g
            pixels[idx + 2] = b


def rect_rgba(pixels: bytearray, width: int, height: int, x: int, y: int, w: int, h: int, color: tuple[int, int, int, int]) -> None:
    r, g, b, a = color
    x0 = max(0, min(width, x))
    y0 = max(0, min(height, y))
    x1 = max(0, min(width, x + w))
    y1 = max(0, min(height, y + h))
    for yy in range(y0, y1):
        row = yy * width * 4
        for xx in range(x0, x1):
            idx = row + xx * 4
            pixels[idx] = r
            pixels[idx + 1] = g
            pixels[idx + 2] = b
            pixels[idx + 3] = a
