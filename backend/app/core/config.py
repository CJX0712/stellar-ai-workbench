# Author: 晨星
"""应用配置：pydantic-settings 读取 env/.env，并提供运行期持久化更新。"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = BACKEND_ROOT / "data"
DOTENV_PATH = BACKEND_ROOT / ".env"

# Mock Provider 的模型标识：请求该模型即强制走离线链路
MOCK_MODEL = "mock"

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "tauri://localhost",
    "http://tauri.localhost",
]

# 写入 .env 的键及其对应的 Settings 字段名
PERSISTED_KEYS: dict[str, str] = {
    "BASE_URL": "base_url",
    "API_KEY": "api_key",
    "MODEL": "model",
    "FALLBACK_MODEL": "fallback_model",
    "EMBEDDING_MODEL": "embedding_model",
}


class Settings(BaseSettings):
    """运行期配置。env 变量优先级高于 .env 文件。"""

    model_config = SettingsConfigDict(
        env_file=str(DOTENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Stellar AI Workbench"
    app_version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None
    model: str = "gpt-4o-mini"
    fallback_model: str | None = None
    embedding_model: str = "text-embedding-3-small"
    request_timeout: float = 30.0
    mock_model: str = "mock"

    data_dir: Path = DEFAULT_DATA_DIR
    cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    @field_validator("api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: Any) -> Any:
        """空字符串视为未配置，避免 "" 被当成有效 key。"""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def api_key_value(self) -> str | None:
        return self.api_key.get_secret_value() if self.api_key else None

    @property
    def env_path(self) -> Path:
        """.env 落盘路径（SettingsStore 写入用）。"""
        return DOTENV_PATH

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_value)

    @property
    def memory_dir(self) -> Path:
        return self.data_dir / "memory"

    @property
    def knowledge_dir(self) -> Path:
        return self.data_dir / "knowledge"

    @property
    def vector_dir(self) -> Path:
        return self.data_dir / "vector"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.memory_dir, self.knowledge_dir, self.vector_dir):
            path.mkdir(parents=True, exist_ok=True)


_lock = threading.Lock()
_settings: Settings | None = None


def get_settings() -> Settings:
    """返回进程内单例配置（首次调用时加载）。"""
    global _settings
    with _lock:
        if _settings is None:
            _settings = Settings()
        return _settings


def reload_settings() -> Settings:
    """重新加载配置（.env 变更后调用）。"""
    global _settings
    with _lock:
        _settings = Settings()
        return _settings


def _read_dotenv() -> dict[str, str]:
    if not DOTENV_PATH.exists():
        return {}
    values: dict[str, str] = {}
    for raw in DOTENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_dotenv(values: dict[str, str]) -> None:
    DOTENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Author: 晨星", "# Stellar AI Workbench 本地配置（由 /api/v1/settings 写入）"]
    for key, value in values.items():
        lines.append(f"{key}={value}")
    DOTENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_settings(**patch: Any) -> Settings:
    """把指定字段写入 .env 与 os.environ，然后重载配置。

    仅接受 PERSISTED_KEYS 中声明的字段；值为 None 表示清空该项。
    """
    allowed = set(PERSISTED_KEYS.values())
    unknown = set(patch) - allowed
    if unknown:
        raise ValueError(f"不支持更新的配置项: {sorted(unknown)}")

    values = _read_dotenv()
    with _lock:
        for field_name, value in patch.items():
            env_key = next(k for k, v in PERSISTED_KEYS.items() if v == field_name)
            text = "" if value is None else str(value).strip()
            values[env_key] = text
            if text:
                os.environ[env_key] = text
            else:
                os.environ.pop(env_key, None)
        _write_dotenv(values)
        _settings = Settings()
        return _settings
