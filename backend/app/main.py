# Author: 晨星
"""应用入口：只做装配（中间件 + 路由 + 容器），不承载业务逻辑。"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.container import Container, build_container
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

logger = get_logger("stellar.main")


def create_app(container: Optional[Container] = None) -> FastAPI:
    """构建应用实例；container 可注入以便测试替换模块。"""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="模块化桌面 AI 工作台后端（作者：晨星）",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        max_age=86400,
    )
    app.state.container = container or build_container(settings)
    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常：%s", exc)
        return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

    logger.info(
        "%s %s 就绪：provider=%s",
        settings.app_name,
        settings.app_version,
        app.state.container.inference.active_provider,
    )
    return app


app = create_app()
