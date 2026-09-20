#!/usr/bin/env python3
"""P0 门禁：扫描 emoji 图标违规（作者：晨星）。

用法：
    python tools/scan_emoji.py [目录或文件 ...]
默认扫描整个仓库中前端/后端源码与样式文件。
命中即打印 `文件:行号: 内容`，未命中输出 NO_EMOJI_HITS。
退出码：0 = 合规，1 = 发现 emoji。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# P0 emoji 检测正则（与 Spec 一致）
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE00-\uFE0F"
    "\u20E3"
    "]"
)

SCAN_SUFFIXES = {
    ".ts", ".tsx", ".js", ".jsx", ".vue", ".html", ".css",
    ".py", ".md", ".json", ".yaml", ".yml",
}

# 允许 emoji 的目录（UGC / 聊天消息等），MVP 阶段无豁免；
# .pylibs / dist / build 等为第三方或构建产物目录，不属于我方 UI 代码
EXEMPT_PARTS = {".venv", ".pylibs", "node_modules", "dist", "build", "target", ".git", "__pycache__"}


def iter_files(targets: list[str], repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for raw in targets:
        path = Path(raw)
        if not path.is_absolute():
            path = repo_root / path
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                if child.suffix.lower() not in SCAN_SUFFIXES:
                    continue
                if any(part in EXEMPT_PARTS for part in child.parts):
                    continue
                files.append(child)
    return files


def main(argv: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    targets = argv[1:] or ["backend", "frontend", "src-tauri", "docs", "README.md"]
    hits: list[str] = []

    for file in iter_files(targets, repo_root):
        try:
            text = file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if EMOJI_RE.search(line):
                rel = file.relative_to(repo_root).as_posix()
                hits.append(f"{rel}:{lineno}: {line.strip()[:100]}")

    if hits:
        print(f"EMOJI_VIOLATIONS={len(hits)}")
        for hit in hits:
            print(hit)
        return 1

    print("NO_EMOJI_HITS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
