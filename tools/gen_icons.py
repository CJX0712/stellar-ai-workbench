#!/usr/bin/env python3
"""生成桌面壳图标（作者：晨星）。

纯标准库实现，无第三方依赖：输出 Tauri 打包所需的 PNG 图标，
配色沿用 design-tokens.json（画布 #0B0C0E + 信号青 #22D3C5）。

用法：python tools/gen_icons.py
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

BG = (11, 12, 14)       # --bg
ACCENT = (34, 211, 197)  # --accent


def write_png(path: Path, width: int, height: int) -> None:
    cx, cy = width / 2.0, height / 2.0
    radius = min(width, height) * 0.30
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0
        for x in range(width):
            # 菱形标记：与「精密仪器」设计语言一致的单色符号
            if abs(x - cx) + abs(y - cy) <= radius:
                r, g, b = ACCENT
            else:
                r, g, b = BG
            raw += bytes((r, g, b, 255))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    payload = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    icon_dir = repo_root / "src-tauri" / "icons"
    targets = {
        "32x32.png": 32,
        "128x128.png": 128,
        "128x128@2x.png": 256,
    }
    for name, size in targets.items():
        write_png(icon_dir / name, size, size)
        print(f"generated src-tauri/icons/{name} ({size}x{size})")
    print("提示：Windows 打包还需 icons/icon.ico，可用 `npm run tauri icon` 从 PNG 生成。")


if __name__ == "__main__":
    main()
