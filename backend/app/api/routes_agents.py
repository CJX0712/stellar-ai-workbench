# Author: 晨星
"""智能体路由：SSE 逐步输出每一步的思考、行动与观察。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..core.logging import get_logger
from ..schemas import AgentRunRequest
from .deps import get_container
from .sse import sse_event, sse_response

logger = get_logger("stellar.api.agents")

router = APIRouter(tags=["agents"])


@router.post("/agents/run", tags=["agents"])
async def run_agent(payload: AgentRunRequest, request: Request):
    container = get_container(request)
    agent = container.agent_for(payload.tools)

    async def event_stream():
        try:
            async for step in agent.run(
                task=payload.task,
                session=payload.session,
                max_steps=payload.max_steps,
                model=payload.model,
            ):
                yield sse_event(step)
            yield sse_event({"type": "done"})
        except Exception as exc:  # noqa: BLE001 - 流式中途报错要下沉为事件
            logger.error("智能体执行失败：%s", exc)
            yield sse_event({"type": "error", "message": str(exc)})

    return sse_response(event_stream())
