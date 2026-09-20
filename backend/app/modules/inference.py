# Author: 晨星
"""推理代理：把多个 Provider 串成一条故障转移链（主模型 -> fallback -> Mock）。

本模块只负责编排与降级，具体 Provider 实现见 app.modules.providers。
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Iterable, Optional, Sequence

from app.core.config import MOCK_MODEL, Settings, get_settings
from app.core.logging import get_logger
from app.modules.providers import (
    MockProvider,
    OpenAICompatibleProvider,
    ProviderError,
)

logger = get_logger("stellar.inference")

Message = dict[str, str]
Vector = list[float]

MOCK_LABEL = "Mock Provider"


class InferenceProxy:
    """推理门面：同步 chat、异步流式 astream、同步 embed，全部带降级链。"""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        remote: Any = None,
        mock: Any = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._mock = mock or MockProvider()
        self._remote = remote if remote is not None else self._build_remote()
        self._last_error: Optional[str] = None

    # ---------- 装配 ----------

    def _build_remote(self) -> Any:
        """有 api_key 才构造远程 Provider；构造失败视为不可用。"""
        if not self._settings.has_api_key:
            return None
        try:
            return OpenAICompatibleProvider(
                base_url=self._settings.base_url,
                api_key=self._settings.api_key_value,
                timeout=self._settings.request_timeout,
                embedding_model=self._settings.embedding_model,
            )
        except ProviderError as exc:
            logger.warning("远程 Provider 初始化失败，回退 Mock：%s", exc)
            return None

    def rebuild(self) -> None:
        """配置热更新后重建远程 Provider。"""
        self._remote = self._build_remote()

    @property
    def settings(self) -> Settings:
        return self._settings

    # ---------- 降级链 ----------

    def _plan(self, model: Optional[str]) -> list[tuple[str, Any]]:
        requested = (model or self._settings.model or "").strip()
        if requested.lower() == MOCK_MODEL:
            return [(MOCK_MODEL, self._mock)]
        plan: list[tuple[str, Any]] = []
        if self._remote is not None:
            plan.append((requested or self._settings.model, self._remote))
            fallback = (self._settings.fallback_model or "").strip()
            if fallback and fallback != requested:
                plan.append((fallback, self._remote))
        plan.append((MOCK_MODEL, self._mock))
        return plan

    def _embed_plan(self) -> list[tuple[str, Any]]:
        plan: list[tuple[str, Any]] = []
        if self._remote is not None:
            plan.append((self._settings.embedding_model, self._remote))
        plan.append((MOCK_MODEL, self._mock))
        return plan

    # ---------- 对话 ----------

    def chat(self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any) -> str:
        """同步补全；逐级降级，链尾是 Mock，因此正常不会抛错。"""
        errors: list[str] = []
        for name, provider in self._plan(model):
            try:
                text = provider.chat(list(messages), model=name, **opts)
            except Exception as exc:  # noqa: BLE001 - 任何上游异常都要触发降级
                errors.append(f"{name}: {exc}")
                logger.warning("Provider %s 补全失败，准备故障转移：%s", name, exc)
                continue
            if not str(text).strip():
                errors.append(f"{name}: 空响应")
                continue
            self._last_error = None
            return str(text)
        self._last_error = " | ".join(errors)
        raise ProviderError(f"推理失败，已尝试全部候选：{self._last_error}", provider="chain")

    async def astream(
        self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any
    ) -> AsyncIterator[str]:
        """异步流式；首个分片之前失败才降级，避免已输出内容重复。"""
        for name, provider in self._plan(model):
            started = False
            try:
                async for chunk in provider.astream(list(messages), model=name, **opts):
                    if not chunk:
                        continue
                    started = True
                    yield chunk
            except Exception as exc:  # noqa: BLE001
                logger.warning("Provider %s 流式失败：%s", name, exc)
                if started:
                    logger.warning("流已开始输出，终止降级以避免内容重复")
                    return
                continue
            if started:
                self._last_error = None
                return
        self._last_error = "所有候选 Provider 均未产出内容"
        logger.error(self._last_error)

    # ---------- 向量化 ----------

    def embed(self, texts: Iterable[str], model: Optional[str] = None) -> list[Vector]:
        """同步向量化；远程失败时降级到 Mock 的确定性哈希向量。"""
        payload = [t for t in texts if isinstance(t, str)]
        errors: list[str] = []
        for name, provider in self._embed_plan():
            try:
                vectors = provider.embed(payload, model=model or name)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{name}: {exc}")
                logger.warning("Provider %s 向量化失败，准备降级：%s", name, exc)
                continue
            if vectors and len(vectors) == len(payload) and all(len(v) for v in vectors):
                return [list(v) for v in vectors]
            errors.append(f"{name}: 向量为空或长度不匹配")
        raise ProviderError(
            f"向量化失败，已尝试全部候选：{' | '.join(errors)}", provider="chain"
        )

    # ---------- 元信息 ----------

    @property
    def active_provider(self) -> str:
        return str(getattr(self._remote, "name", "")) if self._remote is not None else MOCK_MODEL

    @property
    def active_model(self) -> str:
        return self._settings.model if self._remote is not None else MOCK_MODEL

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def list_models(self) -> dict[str, Any]:
        items: list[dict[str, str]] = [{"id": MOCK_MODEL, "label": MOCK_LABEL, "kind": "mock"}]
        if self._remote is not None:
            items.insert(0, {"id": self._settings.model, "label": self._settings.model, "kind": "remote"})
            fallback = (self._settings.fallback_model or "").strip()
            if fallback:
                items.insert(1, {"id": fallback, "label": fallback, "kind": "remote"})
        seen: set[str] = set()
        unique = [m for m in items if not (m["id"] in seen or seen.add(m["id"]))]
        return {"active": self.active_model, "models": unique}

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.active_provider,
            "model": self.active_model,
            "has_api_key": self._settings.has_api_key,
            "base_url": self._settings.base_url,
            "fallback_model": self._settings.fallback_model,
        }


def build_inference(settings: Optional[Settings] = None) -> InferenceProxy:
    """按配置构造推理代理（容器装配用）。"""
    return InferenceProxy(settings=settings or get_settings())
