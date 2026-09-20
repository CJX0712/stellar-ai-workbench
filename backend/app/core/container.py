# Author: 晨星
"""依赖装配根：按配置构建各模块实例，供路由层注入。此处不含业务逻辑。"""

from __future__ import annotations

from typing import Optional

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.settings_store import SettingsStore
from app.modules.agent import Agent
from app.modules.inference import InferenceProxy
from app.modules.memory import KnowledgeStore, MemoryStore
from app.modules.rag import RAGPipeline
from app.modules.retrieval import Retrieval, create_vector_store
from app.modules.tools import ToolRegistry, build_default_registry

logger = get_logger("stellar.container")


class Container:
    """模块容器：持有全部模块实例，并负责设置变更后的重建。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings_store = SettingsStore(settings)
        self.inference = InferenceProxy(settings)
        self.retrieval = Retrieval(
            embedder=self.inference,
            store=create_vector_store(settings.vector_dir),
        )
        self.memory = MemoryStore(settings.memory_dir)
        self.knowledge = KnowledgeStore(settings.knowledge_dir)
        self.tools: ToolRegistry = build_default_registry(self.retrieval)
        self.rag = RAGPipeline(self.inference, self.retrieval, self.memory)
        self.agent = Agent(self.inference, self.tools, self.memory)

    def rebuild_inference(self) -> None:
        """设置变更后重建推理代理及其下游依赖。"""
        self.inference = InferenceProxy(self.settings)
        self.rag = RAGPipeline(self.inference, self.retrieval, self.memory)
        self.agent = Agent(self.inference, self.tools, self.memory)
        logger.info("推理代理已重建：model=%s", self.settings.model)

    @property
    def modules(self) -> list[str]:
        return ["inference", "retrieval", "rag", "agent", "tools", "memory"]

    @classmethod
    def create(cls, settings: Optional[Settings] = None) -> "Container":
        return cls(settings or Settings())
