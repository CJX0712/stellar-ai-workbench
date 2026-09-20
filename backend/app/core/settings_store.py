# Author: 晨星
"""运行期设置读写：GET 脱敏，POST 更新并持久化到 .env。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from pydantic import SecretStr

from app.core.config import Settings

_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=")


class SettingsStore:
    """持有可变 Settings，并把变更写回 .env（不写密钥到日志）。"""

    def __init__(self, settings: Settings, env_path: Optional[Path] = None) -> None:
        self._settings = settings
        self.env_path = Path(env_path) if env_path else settings.env_path

    @property
    def settings(self) -> Settings:
        return self._settings

    def snapshot(self) -> dict:
        """对外可见配置，api_key 只暴露 has_api_key。"""
        s = self._settings
        return {
            "base_url": s.base_url,
            "model": s.model,
            "fallback_model": s.fallback_model,
            "embedding_model": s.embedding_model,
            "has_api_key": s.has_api_key,
        }

    def update(
        self,
        *,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> Settings:
        """更新内存配置并落盘；None 表示不修改该字段。"""
        patch = {
            "base_url": base_url,
            "api_key": api_key,
            "model": model,
            "fallback_model": fallback_model,
            "embedding_model": embedding_model,
        }
        changed = {k: v for k, v in patch.items() if v is not None}
        if not changed:
            return self._settings

        if "api_key" in changed:
            self._settings.api_key = SecretStr(changed["api_key"]) if changed["api_key"] else None
        for field in ("base_url", "model", "fallback_model", "embedding_model"):
            if field in changed:
                setattr(self._settings, field, changed[field])

        self._persist(changed)
        return self._settings

    def _persist(self, changed: dict) -> None:
        """把变更键写回 .env，保留无关行。"""
        wanted = {k: (v if k != "api_key" else v) for k, v in changed.items()}
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if self.env_path.exists():
            lines = self.env_path.read_text(encoding="utf-8").splitlines()

        remaining = dict(wanted)
        out: list[str] = []
        for line in lines:
            match = _KEY_RE.match(line.strip())
            if match and match.group(1) in remaining:
                key = match.group(1)
                out.append(f"{key}={remaining.pop(key)}")
            else:
                out.append(line)
        for key, value in remaining.items():
            out.append(f"{key}={value}")
        self.env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
