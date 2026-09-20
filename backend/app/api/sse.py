# Author: 晨星
"""SSE 载荷封装：统一 data: 行格式与事件分隔。"""

from __future__ import annotations

import json
from typing import Any

from fastapi.responses import StreamingResponse

MEDIA_TYPE = "text/event-stream"
HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def sse_event(payload: Any) -> str:
    """把 dict 编成一条 SSE 事件。"""
    if isinstance(payload, dict):
        body = payload
    elif hasattr(payload, "to_dict"):
        body = payload.to_dict()
    else:
        body = {"data": payload}
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"


def sse_response(generator: Any) -> StreamingResponse:
    """构造 SSE 响应，禁用代理缓冲以便逐帧到达。"""
    return StreamingResponse(generator, media_type=MEDIA_TYPE, headers=HEADERS)
