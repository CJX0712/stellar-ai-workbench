# Author: 晨星
"""推理 Provider 实现：MockProvider（离线可读）与 OpenAICompatibleProvider（联网）。

两个实现遵循同一 Provider 协议，InferenceProxy 只依赖协议，不依赖具体 SDK。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, AsyncIterator, Iterable, Optional, Protocol, Sequence

Message = dict[str, str]

TOOL_HEADER = "可用工具:"
_TOOL_LINE = re.compile(r"^- ([A-Za-z_][A-Za-z0-9_]*)\(", re.MULTILINE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class ProviderError(RuntimeError):
    """Provider 调用失败；status 为上游 HTTP 状态码（若有）。"""

    def __init__(self, message: str, *, provider: str = "", status: Optional[int] = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status = status


class Provider(Protocol):
    """Provider 协议：同步补全、异步流式、向量化。"""

    name: str

    def chat(self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any) -> str: ...

    def astream(
        self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any
    ) -> AsyncIterator[str]: ...

    def embed(self, texts: Sequence[str], **opts: Any) -> list[list[float]]: ...


def hash_embedding(text: str, dim: int = 64) -> list[float]:
    """确定性哈希向量：词 + 汉字 uni/bi-gram 投影，L2 归一化。

    离线、无随机数、可复现，保证 Mock 模式下检索结果稳定。
    """
    vec = [0.0] * dim
    lowered = (text or "").lower()
    tokens: list[str] = re.findall(r"[a-z0-9]+", lowered)
    cjk = _CJK_RE.findall(lowered)
    tokens.extend(cjk)
    tokens.extend(cjk[i] + cjk[i + 1] for i in range(len(cjk) - 1))
    if not tokens:
        tokens = [lowered or " "]
    for token in tokens:
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        for offset in (0, 4, 8):
            vec[int.from_bytes(digest[offset : offset + 4], "big") % dim] += 1.0
    norm = math.sqrt(sum(value * value for value in vec)) or 1.0
    return [value / norm for value in vec]


class MockProvider:
    """离线 Provider：无密钥、无网络时端到端跑通。"""

    name = "mock"

    def __init__(self, dim: int = 64, chunk_size: int = 6) -> None:
        self.dim = dim
        self.chunk_size = chunk_size

    def chat(self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any) -> str:
        return self.compose(messages, model)

    async def astream(
        self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any
    ) -> AsyncIterator[str]:
        text = self.compose(messages, model)
        for start in range(0, len(text), self.chunk_size):
            yield text[start : start + self.chunk_size]

    def embed(self, texts: Sequence[str], **opts: Any) -> list[list[float]]:
        return [hash_embedding(text, self.dim) for text in texts]

    def compose(self, messages: Sequence[Message], model: Optional[str] = None) -> str:
        """根据消息内容生成确定性可读回复。"""
        system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        users = [m.get("content", "") for m in messages if m.get("role") == "user"]
        last_user = users[-1] if users else ""
        if TOOL_HEADER in system:
            return self._compose_agent(system, last_user, messages)
        label = model or self.name
        return (
            f"[{label}] 已收到：{last_user or '（空消息）'}。"
            f"这是离线 Mock 响应，未配置 api_key 时用于端到端跑通。"
        )

    def _compose_agent(self, system: str, last_user: str, messages: Sequence[Message]) -> str:
        """智能体场景：首步调用第一个工具，拿到观察后收敛为 FINAL。"""
        observations = sum(
            1 for m in messages if m.get("role") == "user" and m.get("content", "").startswith("OBSERVATION:")
        )
        tools = _TOOL_LINE.findall(system)
        if observations == 0 and tools:
            name = tools[0]
            args = {"query": last_user} if name == "knowledge_search" else {"expression": "2 + 2"}
            return f"THOUGHT: 先用 {name} 收集信息。\nACTION: {name} {json.dumps(args, ensure_ascii=False)}"
        task = next(
            (
                m.get("content", "")
                for m in messages
                if m.get("role") == "user" and not m.get("content", "").startswith("OBSERVATION:")
            ),
            last_user,
        )
        return f"THOUGHT: 已获得观察结果，可以作答。\nFINAL: 已完成任务「{task[:40]}」（Mock 模式）。"


class OpenAICompatibleProvider:
    """OpenAI 兼容端点 Provider；client 可注入以便离线单测。"""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        client: Any = None,
        async_client: Any = None,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.embedding_model = embedding_model
        self._status_error: Any = None
        if client is None or async_client is None:
            sdk = self._import_sdk()
            kwargs = {
                "base_url": base_url,
                "api_key": api_key or "empty",
                "timeout": timeout,
                "max_retries": 0,
            }
            client = client or sdk["OpenAI"](**kwargs)
            async_client = async_client or sdk["AsyncOpenAI"](**kwargs)
            self._status_error = sdk["APIStatusError"]
        self._client = client
        self._async_client = async_client

    @staticmethod
    def _import_sdk() -> dict:
        try:
            from openai import APIStatusError, AsyncOpenAI, OpenAI
        except ImportError as exc:  # pragma: no cover - 依赖缺失时显式报错
            raise ProviderError("openai SDK 未安装，无法使用 OpenAI 兼容 Provider", provider="openai-compatible") from exc
        return {"OpenAI": OpenAI, "AsyncOpenAI": AsyncOpenAI, "APIStatusError": APIStatusError}

    def chat(self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any) -> str:
        self._require_model(model)
        try:
            response = self._client.chat.completions.create(model=model, messages=list(messages), **opts)
        except Exception as exc:
            raise self._to_error(exc) from exc
        return (response.choices[0].message.content or "") if response.choices else ""

    async def astream(
        self, messages: Sequence[Message], model: Optional[str] = None, **opts: Any
    ) -> AsyncIterator[str]:
        self._require_model(model)
        try:
            stream = await self._async_client.chat.completions.create(
                model=model, messages=list(messages), stream=True, **opts
            )
        except Exception as exc:
            raise self._to_error(exc) from exc
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            delta = getattr(choices[0], "delta", None) if choices else None
            text = getattr(delta, "content", None) if delta else None
            if text:
                yield text

    def embed(self, texts: Sequence[str], **opts: Any) -> list[list[float]]:
        model = opts.pop("model", None) or self.embedding_model
        try:
            response = self._client.embeddings.create(model=model, input=list(texts))
        except Exception as exc:
            raise self._to_error(exc) from exc
        return [list(item.embedding) for item in response.data]

    @staticmethod
    def _require_model(model: Optional[str]) -> None:
        if not model:
            raise ProviderError("未指定模型", provider="openai-compatible", status=400)

    def _to_error(self, exc: Exception) -> ProviderError:
        status = getattr(exc, "status_code", None)
        if self._status_error and isinstance(exc, self._status_error):
            status = exc.status_code
        return ProviderError(f"{type(exc).__name__}: {exc}", provider=self.name, status=status)


def iter_texts(texts: Iterable[str]) -> list[str]:
    """归一化输入文本列表（过滤 None）。"""
    return [text for text in texts if isinstance(text, str)]
