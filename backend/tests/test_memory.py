# Author: 晨星
"""记忆与知识库单测：落盘、回读、清空与文本切片。"""

from __future__ import annotations

import json

from app.modules.memory import KnowledgeStore, MemoryStore, Turn, safe_id


def test_store_and_recall(tmp_data):
    memory = MemoryStore(tmp_data / "memory")
    memory.store("s1", Turn(role="user", content="第一条"))
    memory.store("s1", Turn(role="assistant", content="第二条"))
    turns = memory.recall("s1")
    assert [t.content for t in turns] == ["第一条", "第二条"]
    assert memory.count("s1") == 2


def test_recall_limits_to_k(tmp_data):
    memory = MemoryStore(tmp_data / "memory")
    for i in range(5):
        memory.store("s1", Turn(role="user", content=f"第{i}条"))
    assert len(memory.recall("s1", k=2)) == 2
    assert memory.recall("s1", k=2)[-1].content == "第4条"


def test_memory_persists_to_disk(tmp_data):
    root = tmp_data / "memory"
    MemoryStore(root).store("s1", Turn(role="user", content="持久化"))
    payload = json.loads((root / "s1.json").read_text(encoding="utf-8"))
    assert payload["turns"][0]["content"] == "持久化"
    assert MemoryStore(root).recall("s1")[0].content == "持久化"


def test_clear_and_sessions(tmp_data):
    memory = MemoryStore(tmp_data / "memory")
    memory.store("a", Turn(role="user", content="x"))
    memory.store("b", Turn(role="user", content="y"))
    assert memory.sessions() == ["a", "b"]
    memory.clear("a")
    assert memory.count("a") == 0


def test_messages_shape_for_chat(tmp_data):
    memory = MemoryStore(tmp_data / "memory")
    memory.store("s1", Turn(role="user", content="问题"))
    assert memory.messages("s1") == [{"role": "user", "content": "问题"}]


def test_corrupted_memory_file_is_tolerated(tmp_data):
    root = tmp_data / "memory"
    root.mkdir(parents=True, exist_ok=True)
    (root / "bad.json").write_text("{not json", encoding="utf-8")
    assert MemoryStore(root).recall("bad") == []


def test_safe_id_sanitizes_names():
    assert safe_id("a/b c") == "a_b_c"
    assert safe_id("") == "default"


def test_knowledge_upsert_and_list(tmp_data):
    store = KnowledgeStore(tmp_data / "knowledge")
    store.upsert("demo", ["片段一"], [{"source": "unit"}])
    store.upsert("demo", ["片段二"], [{"source": "unit"}])
    assert store.get("demo")["chunk_count"] == 2
    assert {"kb_id": "demo", "chunk_count": 2} in store.list()


def test_knowledge_drop(tmp_data):
    store = KnowledgeStore(tmp_data / "knowledge")
    store.upsert("demo", ["片段"])
    store.drop("demo")
    assert store.get("demo") is None


def test_chunk_text_short_text_unchanged():
    assert KnowledgeStore.chunk_text("短文本") == ["短文本"]


def test_chunk_text_splits_with_overlap():
    text = "x" * 250
    chunks = KnowledgeStore.chunk_text(text, size=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)
    assert chunks[0][:20] and chunks[1][:20]


def test_chunk_text_empty_input():
    assert KnowledgeStore.chunk_text("   ") == []


def test_chunk_text_rejects_bad_size():
    try:
        KnowledgeStore.chunk_text("文本", size=0)
    except ValueError:
        return
    raise AssertionError("size=0 应当报错")
