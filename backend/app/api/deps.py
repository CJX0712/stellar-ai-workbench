# Author: 晨星
"""路由层依赖：从 app.state 取容器，避免路由直连构造逻辑。"""

from __future__ import annotations

from fastapi import Request

from app.container import Container


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:
        raise RuntimeError("容器未初始化，应用装配有误")
    return container
