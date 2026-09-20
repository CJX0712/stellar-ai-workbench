# Author: 晨星
"""HTTP 层请求/响应模型，字段与 docs/openapi.yaml 一一对应。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1)
    model: Optional[str] = None
    session: Optional[str] = None
    stream: bool = True


class KnowledgeAddRequest(BaseModel):
    kb_id: str = Field(..., min_length=1)
    texts: list[str] = Field(..., min_length=1)
    metas: Optional[list[dict]] = None


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    kb_id: str = Field(..., min_length=1)
    top_k: int = Field(default=4, ge=1, le=50)
    model: Optional[str] = None


class AgentRunRequest(BaseModel):
    task: str = Field(..., min_length=1)
    session: Optional[str] = None
    max_steps: int = Field(default=6, ge=1, le=20)
    tools: Optional[list[str]] = None
    model: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    fallback_model: Optional[str] = None
    embedding_model: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    provider: str
    modules: list[str]


class ModelItem(BaseModel):
    id: str
    label: str
    kind: str


class ModelsResponse(BaseModel):
    active: str
    models: list[ModelItem]


class SourceItem(BaseModel):
    text: str
    score: float
    meta: dict = Field(default_factory=dict)


class RagResponse(BaseModel):
    answer: str
    sources: list[SourceItem]


class KnowledgeAddResponse(BaseModel):
    kb_id: str
    chunk_count: int


class SettingsResponse(BaseModel):
    base_url: str
    model: str
    has_api_key: bool
    fallback_model: Optional[str] = None
    embedding_model: Optional[str] = None


class OkResponse(BaseModel):
    ok: bool
