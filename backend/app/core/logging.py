# Author: 晨星
"""日志初始化：统一格式，按环境变量 LOG_LEVEL 调整级别。"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """配置根 logger，只执行一次。"""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(_coerce_level(level))
    _CONFIGURED = True


def _coerce_level(level: str) -> int:
    return getattr(logging, str(level).upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
