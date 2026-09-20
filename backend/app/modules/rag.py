# Author: 晨星
"""检索增强问答管线：检索 -> 组装上下文 -> 推理 -> 答案 + 来源。"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from app.core.logging import get_logger
from app.modules.memory import Turn
from app.modules.retrieval import Hit

logger = get_logger("stellar.rag")

SYSTEM_PROMPT = (
    "你是 Stellar AI Workbench 的检索增强助手。"
    "只依据给定上下文作答；上下文不足以回答时，明确说明依据不足，不要编造。"
    "回答使用与用户相同的语言。"
)
NO_CONTEXT_HINT = "（知识库中没有检索到相关片段，请依据常识作答并说明这一点。）"


class RAGPipeline:
    """把检索与推理编排成一次问答；两者均可注入替换。"""

    def __init__(self, inference: Any, retrieval: Any, memory: Any = None) -> None:
        self.inference = inference
        self.retrieval = retrieval
        self.memory = memory

    def build_context(self, hits: Sequence[Hit]) -> str:
        if not hits:
            return NO_CONTEXT_HINT
        blocks = []
        for index, hit in enumerate(hits, start=1):
            source = hit.meta.get("source") or hit.meta.get("kb_id") or "kb"
            blocks.append(f"[{index}] 来源 {source}\n{hit.text}")
        return "\n\n".join(blocks)

    def build_messages(self, query: str, hits: Sequence[Hit]) -> list[dict]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"上下文：\n{self.build_context(hits)}\n\n问题：{query}"},
        ]

    def answer(
        self,
        query: str,
        kb_id: str,
        top_k: int = 4,
        model: Optional[str] = None,
        session: Optional[str] = None,
    ) -> dict:
        """执行一次检索增强问答。"""
        if not query or not str(query).strip():
            raise ValueError("query 不能为空")
        hits = self.retrieval.search_text(kb_id, query, top_k)
        messages = self.build_messages(query, hits)
        text = self.inference.chat(messages, model=model)
        if self.memory is not None and session:
            self.memory.store(session, Turn(role="user", content=query))
            self.memory.store(session, Turn(role="assistant", content=text))
        logger.info("RAG 完成：kb=%s hits=%d", kb_id, len(hits))
        return {"answer": text, "sources": [hit.to_dict() for hit in hits]}
