# Author: 晨星
"""PyInstaller sidecar 入口（作者：晨星）。

桌面模式下由 Tauri 以 sidecar 方式启动本文件编译出的单一可执行文件；
开发模式下无需此文件，直接 `python -m uvicorn app.main:app` 即可。
"""
from __future__ import annotations

import os

import uvicorn

from app.main import app


def main() -> None:
    host = os.environ.get("STELLAR_HOST", "127.0.0.1")
    port = int(os.environ.get("STELLAR_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
