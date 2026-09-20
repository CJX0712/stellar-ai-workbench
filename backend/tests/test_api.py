# Author: 晨星
"""HTTP 端点单测：用 TestClient 打通健康检查、对话、知识库、RAG、智能体与配置。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.container import Container
from app.core.config import MOCK_MODEL
from app.main import create_app


@pytest.fixture
def client(settings):
    app = create_app(container=Container(settings))
    with TestClient(app) as test_client:
        yield test_client


def _events(payload: str) -> list[dict]:
    return [json.loads(line[6:]) for line in payload.splitlines() if line.startswith("data: ")]


def test_health_returns_modules(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == MOCK_MODEL
    assert set(body["modules"]) == {"inference", "retrieval", "rag", "tools", "agent", "memory"}


def test_models_lists_mock(client):
    body = client.get("/api/v1/models").json()
    assert body["active"] == MOCK_MODEL
    assert any(m["id"] == MOCK_MODEL for m in body["models"])


def test_chat_streams_sse_deltas(client):
    response = client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "你好"}], "session": "s1"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response.text)
    assert [e["type"] for e in events][-1] == "done"
    # 分片边界可能切开中文词，因此断言拼接后的完整文本
    joined = "".join(e["text"] for e in events if e["type"] == "delta")
    assert joined
    assert "你好" in joined


def test_chat_non_stream_returns_json(client):
    response = client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "你好"}], "stream": False},
    )
    assert response.status_code == 200
    assert "answer" in response.json()


def test_chat_rejects_empty_messages(client):
    assert client.post("/api/v1/chat", json={"messages": []}).status_code == 422


def test_chat_persists_session_memory(client, settings):
    client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "记住我"}], "session": "mem"},
    )
    turns = [p.name for p in (settings.memory_dir).glob("*.json")]
    assert "mem.json" in turns


def test_knowledge_add_returns_chunk_count(client):
    response = client.post(
        "/api/v1/knowledge/add",
        json={"kb_id": "demo", "texts": ["Stellar 是晨星打造的模块化 AI 工作台"]},
    )
    assert response.status_code == 200
    assert response.json() == {"kb_id": "demo", "chunk_count": 1}


def test_knowledge_add_rejects_empty_texts(client):
    assert client.post("/api/v1/knowledge/add", json={"kb_id": "demo", "texts": []}).status_code == 422


def test_rag_query_returns_answer_and_sources(client):
    client.post(
        "/api/v1/knowledge/add",
        json={"kb_id": "demo", "texts": ["Stellar 是晨星打造的模块化 AI 工作台，内置检索与推理模块。"]},
    )
    response = client.post("/api/v1/rag/query", json={"query": "Stellar 是什么", "kb_id": "demo", "top_k": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["sources"]
    assert "Stellar" in body["sources"][0]["text"]
    assert set(body["sources"][0]) == {"text", "score", "meta"}


def test_rag_query_on_empty_kb_still_answers(client):
    response = client.post("/api/v1/rag/query", json={"query": "任意", "kb_id": "missing"})
    assert response.status_code == 200
    assert response.json()["sources"] == []


def test_agent_run_streams_steps(client):
    response = client.post("/api/v1/agents/run", json={"task": "计算 2 + 2", "max_steps": 4})
    assert response.status_code == 200
    events = _events(response.text)
    types = [e["type"] for e in events]
    assert "step" in types
    assert "final" in types
    assert types[-1] == "done"
    first_step = next(e for e in events if e["type"] == "step")
    assert first_step["action"].startswith("calculator")
    assert first_step["observation"] == "4"


def test_agent_run_respects_tool_filter(client):
    response = client.post(
        "/api/v1/agents/run",
        json={"task": "只用计算器", "tools": ["calculator"], "max_steps": 3},
    )
    events = _events(response.text)
    step = next(e for e in events if e["type"] == "step")
    assert step["action"].startswith("calculator")


def test_settings_get_masks_api_key(client):
    body = client.get("/api/v1/settings").json()
    assert body["has_api_key"] is False
    assert "api_key" not in body


def test_settings_post_updates_model(settings, monkeypatch, tmp_path):
    # 必须在装配容器之前改 DOTENV_PATH：SettingsStore 在构造时就固定了落盘路径
    env_file = tmp_path / ".env"
    monkeypatch.setattr("app.core.config.DOTENV_PATH", env_file)
    app = create_app(container=Container(settings))
    with TestClient(app) as client:
        response = client.post("/api/v1/settings", json={"model": "unit-model"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model"] == "unit-model"
    assert "unit-model" in env_file.read_text(encoding="utf-8")


def test_unknown_route_returns_404(client):
    assert client.get("/api/v1/nope").status_code == 404


def test_cors_preflight_allows_localhost(client):
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
