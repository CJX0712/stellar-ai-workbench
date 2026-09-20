# Author: 晨星
"""知识库与检索增强路由：导入文档切片、按查询返回答案与来源。"""

from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from fastapi import APIRouter, HTTPException, Request

from ..core.logging import get_logger
from ..modules.memory import KnowledgeStore
from ..schemas import (
    KnowledgeAddRequest,
    KnowledgeAddResponse,
    RagQueryRequest,
    RagResponse,
)
from .deps import get_container

logger = get_logger("stellar.api.knowledge")

router = APIRouter(tags=["knowledge"])


@router.post("/knowledge/add", response_model=KnowledgeAddResponse, tags=["knowledge"])
async def add_knowledge(payload: KnowledgeAddRequest, request: Request) -> dict:
    container = get_container(request)
    chunks: list[str] = []
    metas: list[dict] = []
    for index, text in enumerate(payload.texts):
        base = dict(payload.metas[index]) if payload.metas and index < len(payload.metas) else {}
        base.setdefault("source", f"text[{index}]")
        base.setdefault("kb_id", payload.kb_id)
        for offset, chunk in enumerate(KnowledgeStore.chunk_text(text)):
            chunks.append(chunk)
            meta = dict(base)
            meta["chunk"] = offset
            metas.append(meta)

    if not chunks:
        raise HTTPException(status_code=400, detail="待导入文本为空")

    container.retrieval.add(payload.kb_id, chunks, metas)
    container.knowledge.upsert(payload.kb_id, chunks, metas)
    logger.info("知识库 %s 新增 %d 个切片", payload.kb_id, len(chunks))
    return {"kb_id": payload.kb_id, "chunk_count": len(chunks)}


@router.post("/rag/query", response_model=RagResponse, tags=["rag"])
async def rag_query(payload: RagQueryRequest, request: Request) -> dict:
    container = get_container(request)
    try:
        result = await run_in_threadpool(
            container.rag.answer,
            payload.query,
            payload.kb_id,
            payload.top_k,
            payload.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - 上游异常统一转 502
        logger.error("RAG 查询失败：%s", exc)
        raise HTTPException(status_code=502, detail=f"检索增强问答失败：{exc}") from exc
    return result
