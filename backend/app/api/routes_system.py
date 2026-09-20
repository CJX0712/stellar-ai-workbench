# Author: 晨星
"""系统路由：健康检查、模型清单、配置读写。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import (
    HealthResponse,
    ModelsResponse,
    SettingsResponse,
    SettingsUpdateRequest,
)
from .deps import get_container

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(request: Request) -> dict:
    container = get_container(request)
    return container.health()


@router.get("/models", response_model=ModelsResponse, tags=["models"])
async def list_models(request: Request) -> dict:
    container = get_container(request)
    return container.models()


@router.get("/settings", response_model=SettingsResponse, tags=["settings"])
async def get_settings(request: Request) -> dict:
    container = get_container(request)
    return container.settings_snapshot()


@router.post("/settings", tags=["settings"])
async def update_settings(payload: SettingsUpdateRequest, request: Request) -> dict:
    container = get_container(request)
    patch = payload.model_dump(exclude_none=True)
    snapshot = container.apply_settings(patch)
    return {"ok": True, **snapshot}
