#!/usr/bin/env python3
"""生成桌面壳图标（作者：晨星）。

纯标准库实现，无第三方依赖：输出 Tauri 三平台打包所需的全部图标
（PNG / ICO / ICNS），配色沿用 design-tokens.json（画布 #0B0C0E + 信号青 #22D3C5）。

用法：python tools/gen_icons.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

BG = (11, 12, 14)       # --bg
ACCENT = (34, 211, 197)  # --accent


def render_rgba(width: int, height: int) -> bytes:
    """渲染菱形标记（与「精密仪器」设计语言一致的单色符号），返回 RGBA 像素。"""
    cx, cy = width / 2.0, height / 2.0
    radius = min(width, height) * 0.30
    raw = bytearray()
    for y in range(height):
        for x in range(width):
            if abs(x - cx) + abs(y - cy) <= radius:
                r, g, b = ACCENT
            else:
                r, g, b = BG
            raw += bytes((r, g, b, 255))
    return bytes(raw)


def png_bytes(width: int, height: int) -> bytes:
    raw = bytearray()
    px = render_rgba(width, height)
    stride = width * 4
    for y in range(height):
        raw.append(0)  # filter type 0
        raw += px[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def write_png(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png_bytes(width, height))


def write_ico(path: Path, sizes: list[int]) -> None:
    """ICO 打包：每个条目内嵌一张 PNG（Vista+ 支持 PNG 压缩条目）。"""
    entries = []
    for size in sizes:
        entries.append((size, png_bytes(size, size)))
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    body = bytearray()
    dirents = bytearray()
    for size, data in entries:
        w = 0 if size >= 256 else size
        dirents += struct.pack(
            "<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset
        )
        body += data
        offset += len(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + bytes(dirents) + bytes(body))


def write_icns(path: Path, variants: list[tuple[str, int]]) -> None:
    """ICNS 打包：现代 OSType（ic07..ic14）直接内嵌 PNG 数据（macOS 10.7+）。"""
    body = bytearray()
    for ostype, size in variants:
        data = png_bytes(size, size)
        body += ostype.encode("ascii") + struct.pack(">I", len(data) + 8) + data
    payload = b"icns" + struct.pack(">I", len(body) + 8) + bytes(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    icon_dir = repo_root / "src-tauri" / "icons"

    png_targets = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
        "icon.png": 1024,
        "StoreLogo.png": 64,
    }
    for name, size in png_targets.items():
        write_png(icon_dir / name, size, size)
        print(f"generated src-tauri/icons/{name} ({size}x{size})")

    write_ico(icon_dir / "icon.ico", [16, 32, 48, 64, 128, 256])
    print("generated src-tauri/icons/icon.ico (16/32/48/64/128/256)")

    icns_variants = [
        ("ic07", 128), ("ic08", 256), ("ic09", 512), ("ic10", 1024),
        ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512),
    ]
    write_icns(icon_dir / "icon.icns", icns_variants)
    print("generated src-tauri/icons/icon.icns (ic07..ic14)")


if __name__ == "__main__":
    main()
