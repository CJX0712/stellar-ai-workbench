# Author: 晨星
"""RAG 管线单测：注入假推理与离线检索，验证上下文注入、答案与来源。"""

from __future__ import annotations

import pytest

from app.modules.providers import MockProvider
from app.modules.rag import RAGPipeline
from app.modules.retrieval import NumpyVectorStore, Retrieval

KB = "demo"


class FakeInference:
    """记录收到的 messages 并返回固定答案。"""

    def __init__(self, reply: str = "基于上下文的回答") -> None:
        self.reply = reply
        self.messages: list[dict] = []

    def chat(self, messages, model=None, **opts):
        self.messages = list(messages)
        return self.reply


def build(tmp_data, reply="基于上下文的回答"):
    retrieval = Retrieval(embedder=MockProvider(), store=NumpyVectorStore(tmp_data / "vector"))
    inference = FakeInference(reply)
    return RAGPipeline(inference, retrieval), retrieval, inference


def test_answer_returns_answer_and_sources(tmp_data):
    pipeline, retrieval, _ = build(tmp_data)
    retrieval.add(KB, ["Stellar 是晨星打造的模块化 AI 工作台"])
    result = pipeline.answer("Stellar 是什么", KB)
    assert result["answer"] == "基于上下文的回答"
    assert len(result["sources"]) == 1
    assert "Stellar" in result["sources"][0]["text"]
    assert set(result["sources"][0]) == {"text", "score", "meta"}


def test_context_is_injected_into_prompt(tmp_data):
    pipeline, retrieval, inference = build(tmp_data)
    retrieval.add(KB, ["知识库专有名词：量子烤面包机"])
    pipeline.answer("量子烤面包机是什么", KB)
    joined = "\n".join(m["content"] for m in inference.messages)
    assert "量子烤面包机" in joined
    assert "问题：" in joined


def test_answer_without_hits_still_answers(tmp_data):
    pipeline, _, inference = build(tmp_data)
    result = pipeline.answer("空库查询", KB)
    assert result["sources"] == []
    assert result["answer"] == "基于上下文的回答"
    assert "没有检索到相关片段" in inference.messages[-1]["content"]


def test_top_k_limits_sources(tmp_data):
    pipeline, retrieval, _ = build(tmp_data)
    retrieval.add(KB, [f"第 {i} 条关于检索的资料" for i in range(5)])
    result = pipeline.answer("检索", KB, top_k=2)
    assert len(result["sources"]) == 2


def test_empty_query_rejected(tmp_data):
    pipeline, _, _ = build(tmp_data)
    with pytest.raises(ValueError):
        pipeline.answer("   ", KB)


def test_model_argument_is_forwarded(tmp_data):
    pipeline, retrieval, inference = build(tmp_data)
    retrieval.add(KB, ["内容"])

    class Recording(FakeInference):
        def chat(self, messages, model=None, **opts):
            self.seen_model = model
            return super().chat(messages, model)

    recorder = Recording()
    pipeline.inference = recorder
    pipeline.answer("内容", KB, model="unit-model")
    assert recorder.seen_model == "unit-model"
