# Author: 晨星
"""测试公共夹具：统一使用临时数据目录与无 key 的 Mock 配置。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def tmp_data(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def settings(tmp_data: Path):
    """无 api_key 的干净配置，数据目录指向临时目录。"""
    from app.core.config import Settings

    return Settings(
        data_dir=tmp_data,
        api_key=None,
        model="gpt-4o-mini",
        fallback_model=None,
        base_url="http://127.0.0.1:9/v1",
    )


@pytest.fixture
def mock_settings(settings):
    return settings
