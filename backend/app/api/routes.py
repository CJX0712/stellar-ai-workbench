# Author: 晨星
"""路由聚合：只做挂载，不写业务逻辑。"""

from __future__ import annotations

from fastapi import APIRouter

from .routes_agents import router as agents_router
from .routes_chat import router as chat_router
from .routes_knowledge import router as knowledge_router
from .routes_system import router as system_router

API_PREFIX = "/api/v1"

router = APIRouter(prefix=API_PREFIX)
router.include_router(system_router)
router.include_router(chat_router)
router.include_router(knowledge_router)
router.include_router(agents_router)
