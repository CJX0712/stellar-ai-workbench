# Author: 晨星
"""检索模块：向量存储抽象（VectorStore）+ 进程内实现 + Retrieval 门面。

Retrieval 只依赖 Embedder 与 VectorStore 两个协议，实现可整体替换。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, Sequence

import numpy as np

from app.core.logging import get_logger

logger = get_logger("stellar.retrieval")

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]")


def safe_kb_id(kb_id: str) -> str:
    """知识库 id -> 安全文件名。"""
    return _SAFE_ID.sub("_", kb_id or "").strip("_") or "default"


@dataclass(frozen=True)
class Hit:
    """检索命中条目。"""

    text: str
    score: float
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"text": self.text, "score": round(float(self.score), 6), "meta": dict(self.meta)}


class Embedder(Protocol):
    """向量化能力（InferenceProxy 满足此协议）。"""

    def embed(self, texts: Sequence[str], model: Optional[str] = None) -> list[list[float]]: ...


class VectorStore(Protocol):
    """向量存储协议：写入、检索、清空。"""

    name: str

    def add(
        self,
        kb_id: str,
        vectors: Sequence[Sequence[float]],
        texts: Sequence[str],
        metas: Optional[Sequence[dict]] = None,
    ) -> int: ...

    def search(self, kb_id: str, vec: Sequence[float], top_k: int = 4) -> list[Hit]: ...

    def drop(self, kb_id: str) -> None: ...

    def count(self, kb_id: str) -> int: ...


class NumpyVectorStore:
    """进程内向量存储：numpy 余弦相似度 + JSON 落盘（LanceDB 不可用时的默认实现）。"""

    name = "numpy-json"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[dict]] = {}

    def _path(self, kb_id: str) -> Path:
        return self.root / f"{safe_kb_id(kb_id)}.json"

    def _items(self, kb_id: str) -> list[dict]:
        if kb_id in self._cache:
            return self._cache[kb_id]
        path = self._path(kb_id)
        items: list[dict] = []
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items = list(payload.get("items", []))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("向量库 %s 读取失败，按空库处理：%s", kb_id, exc)
        self._cache[kb_id] = items
        return items

    def _flush(self, kb_id: str) -> None:
        path = self._path(kb_id)
        payload = {"kb_id": kb_id, "items": self._cache.get(kb_id, [])}
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def add(
        self,
        kb_id: str,
        vectors: Sequence[Sequence[float]],
        texts: Sequence[str],
        metas: Optional[Sequence[dict]] = None,
    ) -> int:
        items = self._items(kb_id)
        meta_list = list(metas or [{} for _ in texts])
        for index, text in enumerate(texts):
            items.append(
                {
                    "text": text,
                    "vector": [float(v) for v in vectors[index]],
                    "meta": dict(meta_list[index] if index < len(meta_list) else {}),
                }
            )
        self._cache[kb_id] = items
        self._flush(kb_id)
        return len(items)

    def search(self, kb_id: str, vec: Sequence[float], top_k: int = 4) -> list[Hit]:
        items = self._items(kb_id)
        if not items:
            return []
        matrix = np.asarray([item["vector"] for item in items], dtype="float32")
        query = np.asarray(vec, dtype="float32")
        norms = np.linalg.norm(matrix, axis=1) * (np.linalg.norm(query) or 1.0)
        denom = np.where(norms == 0, 1e-9, norms)
        scores = matrix.dot(query) / denom
        order = np.argsort(-scores)[: max(1, top_k)]
        return [
            Hit(text=str(items[i]["text"]), score=float(scores[i]), meta=dict(items[i].get("meta") or {}))
            for i in order
        ]

    def drop(self, kb_id: str) -> None:
        self._cache.pop(kb_id, None)
        path = self._path(kb_id)
        if path.exists():
            path.unlink()

    def count(self, kb_id: str) -> int:
        return len(self._items(kb_id))


class Retrieval:
    """检索门面：文本 -> 向量 -> 存储 -> Hit 列表。"""

    def __init__(self, embedder: Embedder, store: Optional[VectorStore] = None, root: Optional[Path] = None) -> None:
        self.embedder = embedder
        self.store = store or NumpyVectorStore(Path(root) if root else Path("data") / "vector")

    def add(self, kb_id: str, texts: Sequence[str], metas: Optional[Sequence[dict]] = None) -> int:
        """写入知识库，返回写入后的条目总数。"""
        texts = [text for text in texts if text and text.strip()]
        if not texts:
            return self.store.count(kb_id)
        vectors = self.embedder.embed(texts)
        return self.store.add(kb_id, vectors, texts, metas)

    def query(self, kb_id: str, vec: Sequence[float], top_k: int = 4) -> list[Hit]:
        """按向量检索 top_k 条命中。"""
        return self.store.search(kb_id, vec, top_k)

    def search_text(self, kb_id: str, text: str, top_k: int = 4) -> list[Hit]:
        """按文本检索：嵌入后调用 query。"""
        vector = self.embedder.embed([text])[0]
        return self.query(kb_id, vector, top_k)

    def drop(self, kb_id: str) -> None:
        self.store.drop(kb_id)

    def count(self, kb_id: str) -> int:
        return self.store.count(kb_id)

    @property
    def backend(self) -> str:
        return getattr(self.store, "name", "unknown")


def create_vector_store(root: Path, backend: Optional[str] = None) -> VectorStore:
    """按 backend 选择向量存储；lancedb 不可用时静默回退到进程内实现。

    backend 取值：auto（默认，优先 LanceDB）/ lancedb / numpy。可用环境变量
    VECTOR_BACKEND 覆盖，便于无 LanceDB wheel 的平台强制走纯 Python 实现。
    """
    backend = (backend or os.environ.get("VECTOR_BACKEND") or "auto").strip().lower()
    if backend in {"auto", "lancedb"}:
        try:
            from app.modules.lancedb_store import LanceVectorStore

            logger.info("使用 LanceDB 向量存储：%s", root)
            return LanceVectorStore(root)
        except Exception as exc:  # 缺 wheel / 初始化失败都回退
            if backend == "lancedb":
                raise
            logger.warning("LanceDB 不可用（%s），回退进程内 numpy 向量存储", exc)
    return NumpyVectorStore(root)
