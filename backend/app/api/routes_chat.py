# Author: 晨星
"""对话路由：SSE 流式返回文本分片；stream=false 时返回完整 JSON。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from ..core.logging import get_logger
from ..modules.memory import Turn
from ..schemas import ChatRequest
from .deps import get_container
from .sse import sse_event, sse_response

logger = get_logger("stellar.api.chat")

router = APIRouter(tags=["chat"])


@router.post("/chat", tags=["chat"])
async def chat(payload: ChatRequest, request: Request):
    container = get_container(request)
    messages = [m.model_dump() for m in payload.messages]
    model = payload.model

    if not payload.stream:
        text = container.inference.chat(messages, model=model)
        _remember(container, payload.session, payload.messages[-1].content, text)
        return {"answer": text, "model": model or container.inference.active_model}

    async def event_stream():
        buffer: list[str] = []
        try:
            async for chunk in container.inference.astream(messages, model=model):
                buffer.append(chunk)
                yield sse_event({"type": "delta", "text": chunk})
            yield sse_event({"type": "done", "model": model or container.inference.active_model})
        except Exception as exc:  # noqa: BLE001 - SSE 中途报错也要给客户端可读事件
            logger.error("对话流失败：%s", exc)
            yield sse_event({"type": "error", "message": str(exc)})
        else:
            _remember(container, payload.session, payload.messages[-1].content, "".join(buffer))

    return sse_response(event_stream())


def _remember(container, session: str | None, question: str, answer: str) -> None:
    """把一轮对话写入会话记忆；无 session 时不落盘。"""
    if not session or not answer:
        return
    try:
        container.memory.store(session, Turn(role="user", content=question))
        container.memory.store(session, Turn(role="assistant", content=answer))
    except Exception as exc:  # noqa: BLE001 - 记忆失败不应影响对话结果
        logger.warning("写入会话记忆失败：%s", exc)
