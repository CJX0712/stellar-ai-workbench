# Author: 晨星
"""智能体编排单测：注入假推理与假工具，验证逐步产出与收敛行为。"""

from __future__ import annotations

import asyncio

from app.modules.agent import Agent, parse_decision
from app.modules.tools import ToolRegistry


class ScriptedInference:
    """按脚本返回模型输出，记录每次收到的消息。"""

    def __init__(self, script: list[str]) -> None:
        self.script = list(script)
        self.messages: list[list[dict]] = []

    def chat(self, messages, model=None, **opts):
        self.messages.append(list(messages))
        return self.script.pop(0) if self.script else "FINAL: 兜底完成"


def build_agent(script):
    inference = ScriptedInference(script)
    registry = ToolRegistry()
    registry.register("echo", lambda text="": f"echo:{text}", "回声工具", text="文本")
    return Agent(inference, registry), inference


def collect(agent, **kwargs):
    async def run():
        return [step async for step in agent.run(**kwargs)]

    return asyncio.run(run())


def test_agent_runs_tool_then_finalizes():
    agent, inference = build_agent(
        [
            "THOUGHT: 需要先取信息。\nACTION: echo {\"text\": \"hello\"}",
            "THOUGHT: 拿到结果。\nFINAL: 任务完成",
        ]
    )
    steps = collect(agent, task="打招呼")
    assert [s.type for s in steps] == ["step", "final"]
    assert steps[0].observation == "echo:hello"
    assert steps[0].action == 'echo {"text": "hello"}'
    assert steps[1].observation == "任务完成"


def test_agent_feeds_observation_back_to_model():
    agent, inference = build_agent(
        [
            "THOUGHT: 取信息。\nACTION: echo {\"text\": \"x\"}",
            "FINAL: 完成",
        ]
    )
    collect(agent, task="任务")
    last_round = inference.messages[-1]
    assert any(m["content"].startswith("OBSERVATION: echo:x") for m in last_round)


def test_agent_finalizes_immediately_when_model_gives_final():
    agent, _ = build_agent(["FINAL: 直接回答"])
    steps = collect(agent, task="一句话任务")
    assert len(steps) == 1 and steps[0].type == "final"


def test_agent_stops_at_max_steps_with_explicit_tail():
    agent, _ = build_agent(["THOUGHT: 继续。\nACTION: echo {\"text\": \"loop\"}"] * 5)
    steps = collect(agent, task="循环任务", max_steps=3)
    assert [s.type for s in steps] == ["step", "step", "step", "final"]
    assert "步数上限" in steps[-1].thought
    assert "未收敛" in steps[-1].observation


def test_agent_reports_unknown_tool_as_observation():
    agent, _ = build_agent(
        [
            "ACTION: ghost {\"a\": 1}",
            "FINAL: 结束",
        ]
    )
    steps = collect(agent, task="调用不存在的工具")
    assert "未知工具 ghost" in steps[0].observation
    assert steps[1].type == "final"


def test_agent_handles_unparsable_model_output():
    agent, _ = build_agent(["我无法理解格式", "FINAL: 结束"])
    steps = collect(agent, task="格式异常")
    assert "未解析出有效行动" in steps[0].observation


def test_agent_clamps_step_limits():
    agent, _ = build_agent(["FINAL: ok"])
    assert agent._clamp_steps(0) == 1
    assert agent._clamp_steps(999) == 20
    assert agent._clamp_steps("bad") == 6


def test_parse_decision_extracts_fields():
    parsed = parse_decision("THOUGHT: 思考\nACTION: calculator {\"expression\": \"1+1\"}")
    assert parsed["thought"] == "思考"
    assert parsed["action"] == "calculator"
    assert parsed["args"] == {"expression": "1+1"}
    assert parsed["final"] is None


def test_parse_decision_supports_fullwidth_colon():
    parsed = parse_decision("FINAL：完成啦")
    assert parsed["final"] == "完成啦"


def test_parse_decision_tolerates_malformed_json():
    parsed = parse_decision("ACTION: calculator {not json}")
    assert parsed["action"] == "calculator"
    assert parsed["args"] == {}
