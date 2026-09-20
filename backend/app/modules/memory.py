# Author: 晨星
"""记忆与知识库持久化：会话记忆按 <session>.json 落盘，知识库管元数据与切片。"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("stellar.memory")

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]")
MOCK_SESSION = "default"
DEFAULT_CHUNK_SIZE = 400
DEFAULT_CHUNK_OVERLAP = 60


def safe_id(value: str) -> str:
    """会话/知识库 id -> 安全文件名。"""
    return _SAFE_ID.sub("_", value or "").strip("_") or "default"


def _atomic_write(path: Path, payload: dict) -> None:
    """先写临时文件再替换，避免进程中断留下半截 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        os.close(fd)  # Windows 下句柄未关闭会导致 replace 报 PermissionError
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


class Turn(BaseModel):
    """一条会话记录。"""

    role: str = Field(..., description="system / user / assistant")
    content: str = ""
    meta: dict = Field(default_factory=dict)

    def to_message(self) -> dict:
        return {"role": self.role, "content": self.content}


class MemoryStore:
    """会话记忆：追加写入并落盘到 <root>/<session>.json。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, list[Turn]] = {}

    def _path(self, session: str) -> Path:
        return self.root / f"{safe_id(session)}.json"

    def _turns(self, session: str) -> list[Turn]:
        if session in self._cache:
            return self._cache[session]
        path = self._path(session)
        turns: list[Turn] = []
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                turns = [Turn(**item) for item in payload.get("turns", [])]
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning("会话 %s 读取失败，按空会话处理：%s", session, exc)
        self._cache[session] = turns
        return turns

    def store(self, session: str, turn: Turn) -> int:
        """写入一条记录，返回写入后的总条数。"""
        turns = self._turns(session)
        turns.append(turn)
        self._cache[session] = turns
        _atomic_write(self._path(session), {"session": session, "turns": [t.model_dump() for t in turns]})
        return len(turns)

    def store_many(self, session: str, turns: Iterable[Turn]) -> int:
        for turn in turns:
            self.store(session, turn)
        return len(self._turns(session))

    def recall(self, session: str, k: int = 10) -> list[Turn]:
        """取最近 k 条记录（按时间正序返回，便于直接拼 messages）。"""
        turns = self._turns(session)
        return turns[-max(1, k) :]

    def messages(self, session: str, k: int = 10) -> list[dict]:
        return [t.to_message() for t in self.recall(session, k)]

    def count(self, session: str) -> int:
        return len(self._turns(session))

    def clear(self, session: str) -> None:
        self._cache.pop(session, None)
        path = self._path(session)
        if path.exists():
            path.unlink()

    def sessions(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))


class KnowledgeStore:
    """知识库元数据与切片：记录 kb_id、切片文本与统计。"""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, kb_id: str) -> Path:
        return self.root / f"{safe_id(kb_id)}.json"

    def upsert(self, kb_id: str, chunks: Sequence[str], metas: Optional[Sequence[dict]] = None) -> dict:
        """写入/合并知识库切片，返回元数据。"""
        meta_list = list(metas or [{} for _ in chunks])
        existing = self.get(kb_id) or {"kb_id": kb_id, "chunks": []}
        items = list(existing.get("chunks", []))
        for index, chunk in enumerate(chunks):
            items.append({"text": chunk, "meta": dict(meta_list[index] if index < len(meta_list) else {})})
        payload = {"kb_id": kb_id, "chunk_count": len(items), "chunks": items}
        _atomic_write(self._path(kb_id), payload)
        return payload

    def get(self, kb_id: str) -> Optional[dict]:
        path = self._path(kb_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("知识库 %s 读取失败：%s", kb_id, exc)
            return None

    def list(self) -> list[dict]:
        result = []
        for path in sorted(self.root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            result.append(
                {
                    "kb_id": payload.get("kb_id", path.stem),
                    "chunk_count": int(payload.get("chunk_count", 0)),
                }
            )
        return result

    def drop(self, kb_id: str) -> None:
        path = self._path(kb_id)
        if path.exists():
            path.unlink()

    @staticmethod
    def chunk_text(
        text: str,
        size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> list[str]:
        """把长文本切成带重叠的片段；短文本原样返回。"""
        body = (text or "").strip()
        if not body:
            return []
        if size <= 0:
            raise ValueError("size 必须为正整数")
        if len(body) <= size:
            return [body]
        step = max(1, size - max(0, overlap))
        chunks = []
        start = 0
        while start < len(body):
            chunks.append(body[start : start + size].strip())
            if start + size >= len(body):
                break
            start += step
        return [c for c in chunks if c]
