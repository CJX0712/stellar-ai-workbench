# Author: 晨星
"""推理代理单测：Mock 模式、故障转移链、流式与向量化降级。"""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import MOCK_MODEL
from app.modules.inference import InferenceProxy
from app.modules.providers import MockProvider, ProviderError


class FakeProvider:
    """记录调用序列的 Provider 替身。"""

    name = "fake"

    def __init__(self, reply: str = "fake", embed_dim: int = 4, fail: bool = False) -> None:
        self.reply = reply
        self.embed_dim = embed_dim
        self.fail = fail
        self.calls: list[str] = []

    def chat(self, messages, model=None, **opts):
        self.calls.append(f"chat:{model}")
        if self.fail:
            raise ProviderError("上游 500", provider="fake", status=500)
        return self.reply

    async def astream(self, messages, model=None, **opts):
        self.calls.append(f"stream:{model}")
        if self.fail:
            raise ProviderError("上游 500", provider="fake", status=500)
        for part in ["你", "好", "世界"]:
            yield part

    def embed(self, texts, **opts):
        self.calls.append(f"embed:{opts.get('model')}")
        if self.fail:
            raise ProviderError("嵌入失败", provider="fake")
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def test_no_api_key_uses_mock(settings):
    proxy = InferenceProxy(settings=settings)
    assert proxy.active_provider == MOCK_MODEL
    assert proxy.active_model == MOCK_MODEL
    assert proxy.list_models()["active"] == MOCK_MODEL


def test_mock_chat_returns_readable_text(settings):
    proxy = InferenceProxy(settings=settings)
    text = proxy.chat([{"role": "user", "content": "你好"}])
    assert "你好" in text
    assert "mock" in text.lower()


def test_explicit_mock_model_skips_remote(settings):
    remote = FakeProvider(reply="remote")
    proxy = InferenceProxy(settings=settings, remote=remote, mock=MockProvider())
    assert proxy.chat([{"role": "user", "content": "hi"}], model=MOCK_MODEL)
    assert remote.calls == []


def test_failover_primary_then_fallback_then_mock(settings):
    settings.fallback_model = "fallback-model"
    remote = FakeProvider(fail=True)
    proxy = InferenceProxy(settings=settings, remote=remote, mock=MockProvider())
    text = proxy.chat([{"role": "user", "content": "继续"}])
    assert "mock" in text.lower()
    assert remote.calls == ["chat:gpt-4o-mini", "chat:fallback-model"]


def test_failover_uses_secondary_model_when_available(settings):
    settings.fallback_model = "fallback-model"

    class Selective(FakeProvider):
        def chat(self, messages, model=None, **opts):
            self.calls.append(f"chat:{model}")
            if model == "gpt-4o-mini":
                raise ProviderError("主模型 4xx", provider="fake", status=429)
            return "来自备用模型"

    proxy = InferenceProxy(settings=settings, remote=Selective(), mock=MockProvider())
    assert proxy.chat([{"role": "user", "content": "x"}]) == "来自备用模型"


def test_astream_yields_chunks(settings):
    proxy = InferenceProxy(settings=settings, remote=FakeProvider(), mock=MockProvider())

    async def collect():
        return [c async for c in proxy.astream([{"role": "user", "content": "hi"}])]

    chunks = asyncio.run(collect())
    assert "".join(chunks) == "你好世界"


def test_astream_falls_back_when_remote_fails_before_first_chunk(settings):
    proxy = InferenceProxy(settings=settings, remote=FakeProvider(fail=True), mock=MockProvider())

    async def collect():
        return [c async for c in proxy.astream([{"role": "user", "content": "hi"}])]

    text = "".join(asyncio.run(collect()))
    assert "Mock" in text


def test_embed_falls_back_to_mock(settings):
    remote = FakeProvider(fail=True)
    mock = FakeProvider()
    proxy = InferenceProxy(settings=settings, remote=remote, mock=mock)
    vectors = proxy.embed(["a", "b"])
    assert len(vectors) == 2
    assert vectors[0] == [1.0, 0.0, 0.0, 0.0]
    assert remote.calls == [f"embed:{settings.embedding_model}"]
    assert mock.calls == ["embed:mock"]


def test_list_models_includes_remote_and_mock(settings):
    settings.fallback_model = "fallback-model"
    proxy = InferenceProxy(settings=settings, remote=FakeProvider(), mock=MockProvider())
    payload = proxy.list_models()
    assert payload["active"] == "gpt-4o-mini"
    assert [m["id"] for m in payload["models"]] == ["gpt-4o-mini", "fallback-model", MOCK_MODEL]


def test_describe_reports_no_secret(settings):
    proxy = InferenceProxy(settings=settings)
    assert proxy.describe()["has_api_key"] is False


def test_chat_raises_when_every_provider_fails(settings):
    class Broken:
        name = "broken"

        def chat(self, messages, model=None, **opts):
            raise ProviderError("总是失败", provider="broken")

        async def astream(self, messages, model=None, **opts):
            raise ProviderError("总是失败", provider="broken")
            yield ""

        def embed(self, texts, **opts):
            raise ProviderError("总是失败", provider="broken")

    proxy = InferenceProxy(settings=settings, remote=Broken(), mock=Broken())
    with pytest.raises(ProviderError):
        proxy.chat([{"role": "user", "content": "hi"}])
