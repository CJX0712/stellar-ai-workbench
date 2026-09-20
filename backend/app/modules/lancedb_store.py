# Author: 晨星
"""LanceDB 向量存储实现：进程内零运维，作为 NumpyVectorStore 的可替换对等实现。

仅在 lancedb + pyarrow 可用时由 create_vector_store 选中；任何初始化异常都会让
调用方回退到 NumpyVectorStore，因此本模块不在 import 期强制依赖 lancedb。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Sequence

import pyarrow as pa

from app.core.logging import get_logger
from app.modules.retrieval import Hit, safe_kb_id

logger = get_logger("stellar.retrieval.lancedb")


def _table_name(kb_id: str) -> str:
    """知识库 id -> LanceDB 表名（仅保留安全字符）。"""
    return "kb_" + safe_kb_id(kb_id).replace(".", "_").replace("-", "_")


class LanceVectorStore:
    """LanceDB 后端：向量列用 fixed_size_list(float32, dim) 存储，余弦检索。"""

    name = "lancedb"

    def __init__(self, root: Path, dim: Optional[int] = None) -> None:
        import lancedb  # 延迟导入：缺失时由工厂回退

        self._lancedb = lancedb
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.root))
        self._dim_file = self.root / "_dims.json"
        self._dims: dict[str, int] = self._load_dims()
        if dim:
            self._default_dim = int(dim)
        self._tables: dict[str, Any] = {}

    @property
    def _default_dim(self) -> int:
        return 64

    def _load_dims(self) -> dict[str, int]:
        if self._dim_file.exists():
            try:
                return {k: int(v) for k, v in json.loads(self._dim_file.read_text(encoding="utf-8")).items()}
            except (json.JSONDecodeError, OSError, ValueError):
                return {}
        return {}

    def _save_dims(self) -> None:
        self._dim_file.write_text(json.dumps(self._dims), encoding="utf-8")

    def _schema(self, dim: int) -> pa.Schema:
        return pa.schema(
            [
                pa.field("text", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dim)),
                pa.field("meta", pa.string()),
            ]
        )

    def _open(self, kb_id: str) -> Optional[Any]:
        name = _table_name(kb_id)
        names = set(self._db.table_names())
        if name not in names:
            return None
        if kb_id in self._tables:
            return self._tables[kb_id]
        table = self._db.open_table(name)
        self._tables[kb_id] = table
        return table

    def _create(self, kb_id: str, dim: int) -> Any:
        name = _table_name(kb_id)
        table = self._db.create_table(name, schema=self._schema(dim), exist_ok=True)
        self._tables[kb_id] = table
        self._dims[kb_id] = dim
        self._save_dims()
        return table

    def _table_for(self, kb_id: str, dim: int) -> Any:
        existing = self._open(kb_id)
        if existing is not None and self._dims.get(kb_id) == dim:
            return existing
        if existing is not None:
            # 向量维度变化（换了嵌入模型）：重建表，避免 schema 冲突
            logger.warning("知识库 %s 向量维度变化，重建表", kb_id)
            self.drop(kb_id)
        return self._create(kb_id, dim)

    def add(
        self,
        kb_id: str,
        vectors: Sequence[Sequence[float]],
        texts: Sequence[str],
        metas: Optional[Sequence[dict]] = None,
    ) -> int:
        if not texts:
            return self.count(kb_id)
        dim = len(vectors[0])
        table = self._table_for(kb_id, dim)
        meta_list = list(metas or [{} for _ in texts])
        rows = [
            {
                "text": str(texts[i]),
                "vector": [float(value) for value in vectors[i]],
                "meta": json.dumps(meta_list[i] if i < len(meta_list) else {}, ensure_ascii=False),
            }
            for i in range(len(texts))
        ]
        table.add(rows)
        return self.count(kb_id)

    def search(self, kb_id: str, vec: Sequence[float], top_k: int = 4) -> list[Hit]:
        table = self._open(kb_id)
        if table is None:
            return []
        rows = table.search([float(v) for v in vec]).metric("cosine").limit(max(1, top_k)).to_list()
        hits: list[Hit] = []
        for row in rows:
            distance = float(row.get("_distance", 0.0) or 0.0)
            try:
                meta = json.loads(row.get("meta") or "{}")
            except json.JSONDecodeError:
                meta = {}
            hits.append(Hit(text=str(row.get("text", "")), score=1.0 - distance, meta=meta))
        return hits

    def drop(self, kb_id: str) -> None:
        self._tables.pop(kb_id, None)
        self._dims.pop(kb_id, None)
        self._save_dims()
        name = _table_name(kb_id)
        try:
            self._db.drop_table(name)
        except Exception as exc:  # 表不存在时忽略
            logger.debug("删除表 %s 失败（可能不存在）：%s", name, exc)

    def count(self, kb_id: str) -> int:
        table = self._open(kb_id)
        if table is None:
            return 0
        return int(table.count_rows())
