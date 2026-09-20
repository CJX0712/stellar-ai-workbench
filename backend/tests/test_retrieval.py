# Author: 晨星
"""检索模块单测：使用离线哈希向量与进程内存储，验证写入、检索与清空。"""

from __future__ import annotations

from app.modules.providers import MockProvider
from app.modules.retrieval import Hit, NumpyVectorStore, Retrieval

KB = "demo"


def build(tmp_data):
    store = NumpyVectorStore(tmp_data / "vector")
    return Retrieval(embedder=MockProvider(), store=store)


def test_add_returns_total_count(tmp_data):
    retrieval = build(tmp_data)
    assert retrieval.add(KB, ["Stellar 是晨星打造的模块化 AI 工作台"]) == 1
    assert retrieval.add(KB, ["第二条内容"]) == 2
    assert retrieval.count(KB) == 2


def test_add_ignores_blank_text(tmp_data):
    retrieval = build(tmp_data)
    assert retrieval.add(KB, ["", "   "]) == 0


def test_search_text_ranks_related_chunk_first(tmp_data):
    retrieval = build(tmp_data)
    retrieval.add(
        KB,
        [
            "Stellar 是晨星打造的模块化 AI 工作台，支持推理与检索。",
            "今天天气晴朗，适合出门散步。",
        ],
    )
    hits = retrieval.search_text(KB, "Stellar 是什么", top_k=1)
    assert len(hits) == 1
    assert "Stellar" in hits[0].text
    assert isinstance(hits[0], Hit)


def test_query_accepts_precomputed_vector(tmp_data):
    retrieval = build(tmp_data)
    retrieval.add(KB, ["向量检索测试文本"])
    vector = MockProvider().embed(["向量检索测试文本"])[0]
    hits = retrieval.query(KB, vector, top_k=1)
    assert hits and hits[0].score > 0.99


def test_hit_meta_is_preserved(tmp_data):
    retrieval = build(tmp_data)
    retrieval.add(KB, ["带元数据的文本"], [{"source": "unit-test"}])
    hits = retrieval.search_text(KB, "带元数据")
    assert hits[0].meta["source"] == "unit-test"


def test_empty_knowledge_base_returns_no_hits(tmp_data):
    retrieval = build(tmp_data)
    assert retrieval.search_text(KB, "任意查询") == []


def test_drop_clears_knowledge_base(tmp_data):
    retrieval = build(tmp_data)
    retrieval.add(KB, ["临时内容"])
    retrieval.drop(KB)
    assert retrieval.count(KB) == 0


def test_hit_to_dict_rounds_score(tmp_data):
    hit = Hit(text="t", score=0.123456789, meta={"a": 1})
    payload = hit.to_dict()
    assert payload["score"] == 0.123457
    assert payload["meta"] == {"a": 1}


def test_backend_name_reports_store(tmp_data):
    retrieval = build(tmp_data)
    assert retrieval.backend == "numpy-json"
