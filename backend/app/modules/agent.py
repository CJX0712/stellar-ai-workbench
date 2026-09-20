# Author: 晨星
"""智能体编排：原生循环（不引第三方 agent 框架），逐步产出 thought/action/observation。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from app.core.logging import get_logger
from app.modules.memory import Turn
from app.modules.tools import UnknownToolError

logger = get_logger("stellar.agent")

MAX_STEPS_LIMIT = 20
_FINAL_RE = re.compile(r"FINAL\s*[:：]\s*(.+)", re.DOTALL)
_ACTION_RE = re.compile(r"ACTION\s*[:：]\s*([A-Za-z_][A-Za-z0-9_]*)\s*(\{.*\})?", re.DOTALL)
_THOUGHT_RE = re.compile(r"THOUGHT\s*[:：]\s*(.+)")
_OBSERVATION_PREFIX = "OBSERVATION: "


@dataclass
class AgentStep:
    """智能体的一步；to_dict 直接作为 SSE 载荷。"""

    type: str
    index: int
    thought: str = ""
    action: str = ""
    observation: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        payload = {
            "type": self.type,
            "index": self.index,
            "thought": self.thought,
            "action": self.action,
            "observation": self.observation,
        }
        if self.meta:
            payload["meta"] = self.meta
        return payload


class Agent:
    """按「思考 -> 行动 -> 观察」循环执行任务，最多 max_steps 步。"""

    def __init__(self, inference: Any, tools: Any, memory: Any = None) -> None:
        self.inference = inference
        self.tools = tools
        self.memory = memory

    def system_prompt(self) -> str:
        return (
            "你是 Stellar AI Workbench 的智能体。用中文思考，优先调用工具获取事实。\n"
            f"{self.tools.as_prompt()}"
        )

    async def run(
        self,
        task: str,
        session: Optional[str] = None,
        max_steps: int = 6,
        model: Optional[str] = None,
    ) -> AsyncIterator[AgentStep]:
        """执行任务并逐步产出 AgentStep。"""
        steps = self._clamp_steps(max_steps)
        messages: list[dict] = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": task},
        ]
        final_text = ""
        for index in range(steps):
            raw = await self._think(messages, model)
            decision = parse_decision(raw)
            if decision["final"] is not None:
                final_text = decision["final"]
                yield AgentStep(type="final", index=index, thought=decision["thought"], observation=final_text)
                self._remember(session, task, final_text)
                return
            action, args = decision["action"], decision["args"]
            observation = self._act(action, args)
            yield AgentStep(
                type="step",
                index=index,
                thought=decision["thought"],
                action=f"{action} {json.dumps(args, ensure_ascii=False)}",
                observation=observation,
            )
            messages.append({"role": "user", "content": f"{_OBSERVATION_PREFIX}{observation}"})

        # 步数耗尽仍未收敛：显式给出收尾结论，避免静默截断
        fallback = final_text or f"已在 {steps} 步内未收敛，最后观察：{observation}"
        yield AgentStep(type="final", index=steps, thought="达到步数上限，强制收尾", observation=fallback)
        self._remember(session, task, fallback)

    @staticmethod
    def _clamp_steps(max_steps: int) -> int:
        try:
            value = int(max_steps)
        except (TypeError, ValueError):
            return 6
        return max(1, min(value, MAX_STEPS_LIMIT))

    async def _think(self, messages: list[dict], model: Optional[str]) -> str:
        """调用推理；同步 chat 放到线程池，避免阻塞事件循环。"""
        try:
            from starlette.concurrency import run_in_threadpool

            return await run_in_threadpool(self.inference.chat, messages, model)
        except ImportError:  # pragma: no cover - starlette 必装，仅防御
            return self.inference.chat(messages, model)

    def _act(self, action: str, args: dict) -> str:
        if not action:
            return "未解析出有效行动，请给出 ACTION 或 FINAL。"
        try:
            return self.tools.execute(action, args)
        except UnknownToolError:
            return f"未知工具 {action}，可用工具：{', '.join(self.tools.names())}"

    def _remember(self, session: Optional[str], task: str, answer: str) -> None:
        if self.memory is not None and session:
            self.memory.store(session, Turn(role="user", content=task))
            self.memory.store(session, Turn(role="assistant", content=answer))


def parse_decision(text: str) -> dict:
    """解析模型输出；解析不出行动时按文本特征降级，保证循环不会卡死。"""
    body = text or ""
    thought_match = _THOUGHT_RE.search(body)
    thought = thought_match.group(1).strip() if thought_match else ""
    final_match = _FINAL_RE.search(body)
    if final_match:
        return {"thought": thought, "final": final_match.group(1).strip(), "action": None, "args": {}}

    action_match = _ACTION_RE.search(body)
    if action_match:
        name = action_match.group(1)
        args = _parse_args(action_match.group(2))
        return {"thought": thought, "final": None, "action": name, "args": args}
    return {"thought": thought, "final": None, "action": None, "args": {}}


def _parse_args(raw: Optional[str]) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
