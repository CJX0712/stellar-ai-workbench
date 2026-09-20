# Author: 晨星
"""容器装配：按配置拼装模块对象图。此处只做接线，不含业务规则。"""

from __future__ import annotations

from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.settings_store import SettingsStore
from app.modules.agent import Agent
from app.modules.inference import InferenceProxy
from app.modules.memory import KnowledgeStore, MemoryStore
from app.modules.rag import RAGPipeline
from app.modules.retrieval import Retrieval, create_vector_store
from app.modules.tools import ToolRegistry, register_builtins

logger = get_logger("stellar.container")

MODULE_NAMES = ["inference", "retrieval", "rag", "tools", "agent", "memory"]


class Container:
    """持有全部模块实例，供路由层通过依赖注入取用。"""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings: Settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.settings_store = SettingsStore(self.settings)
        self.inference = InferenceProxy(settings=self.settings)
        self.memory = MemoryStore(self.settings.memory_dir)
        self.knowledge = KnowledgeStore(self.settings.knowledge_dir)
        self.retrieval = Retrieval(
            embedder=self.inference,
            store=create_vector_store(self.settings.vector_dir),
        )
        self.tools = register_builtins(ToolRegistry(), self.retrieval)
        self.rag = RAGPipeline(self.inference, self.retrieval, self.memory)
        self.agent = Agent(self.inference, self.tools, self.memory)
        logger.info(
            "容器就绪：provider=%s vector_store=%s modules=%s",
            self.inference.active_provider,
            self.retrieval.backend,
            ",".join(MODULE_NAMES),
        )

    def health(self) -> dict:
        return {
            "status": "ok",
            "provider": self.inference.active_provider,
            "modules": list(MODULE_NAMES),
        }

    def models(self) -> dict:
        return self.inference.list_models()

    def describe(self) -> dict:
        return {
            "provider": self.inference.active_provider,
            "model": self.inference.active_model,
            "vector_store": self.retrieval.backend,
            "tools": self.tools.names(),
        }

    def agent_for(self, tool_names: Optional[list[str]] = None) -> Agent:
        """按工具名子集构造 Agent；为空则用全量工具。"""
        if not tool_names:
            return self.agent
        subset = ToolRegistry()
        for name in tool_names:
            if not self.tools.has(name):
                logger.warning("忽略未注册的工具：%s", name)
                continue
            spec = self.tools.get(name)
            subset.register(spec.name, spec.func, spec.description, **spec.args)
        return Agent(self.inference, subset, self.memory)

    def settings_snapshot(self) -> dict:
        return self.settings_store.snapshot()

    def apply_settings(self, patch: dict) -> dict:
        """更新配置并重建受影响的模块（推理 Provider）。"""
        cleaned = {k: v for k, v in patch.items() if v is not None}
        if cleaned:
            self.settings_store.update(**cleaned)
            self.inference.rebuild()
            logger.info("配置已更新：%s", sorted(cleaned))
        return self.settings_snapshot()


def build_container(settings: Optional[Settings] = None) -> Container:
    return Container(settings=settings)


def resolve(container: Any) -> Container:
    """类型收窄用的小工具，便于路由层标注返回类型。"""
    return container
