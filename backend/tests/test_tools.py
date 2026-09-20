# Author: 晨星
"""工具模块单测：表达式安全求值、注册与执行、知识库检索工具。"""

from __future__ import annotations

import pytest

from app.modules.retrieval import Hit
from app.modules.tools import (
    ToolRegistry,
    UnknownToolError,
    calculator,
    register_builtins,
    safe_eval,
)


def test_calculator_basic_arithmetic():
    assert calculator("2 + 3 * 4") == "14"
    assert calculator("(1 + 2) ** 3") == "27"
    assert calculator("7 / 2") == "3.5"
    assert calculator("-5 + 1") == "-4"
    assert calculator("10 % 3") == "1"


def test_calculator_rejects_dangerous_syntax():
    for expression in ["__import__('os').system('dir')", "open('x')", "a + 1", "[1,2]"]:
        assert calculator(expression).startswith("计算失败")


def test_calculator_handles_division_by_zero():
    assert calculator("1 / 0").startswith("计算失败")


def test_calculator_rejects_huge_exponent():
    assert calculator("2 ** 999999").startswith("计算失败")


def test_safe_eval_returns_float():
    assert safe_eval("1.5 + 1.5") == 3.0


def test_registry_decorator_registers_tool():
    registry = ToolRegistry()

    @registry.tool(description="回声工具", text="输入文本")
    def echo(text: str = "") -> str:
        return f"echo:{text}"

    assert registry.has("echo")
    assert registry.execute("echo", {"text": "hi"}) == "echo:hi"


def test_execute_unknown_tool_raises():
    registry = ToolRegistry()
    with pytest.raises(UnknownToolError):
        registry.execute("nope", {})


def test_execute_returns_text_on_bad_arguments():
    registry = ToolRegistry()
    registry.register("calc", calculator, "计算", expression="表达式")
    assert registry.execute("calc", {"wrong": 1}).startswith("工具 calc 参数错误")


def test_execute_catches_tool_exception():
    registry = ToolRegistry()

    def boom() -> str:
        raise RuntimeError("炸了")

    registry.register("boom", boom, "会失败的工具")
    assert "执行失败" in registry.execute("boom", {})


def test_as_prompt_lists_tools_for_agent():
    registry = ToolRegistry()
    register_builtins(registry, retrieval=None)
    prompt = registry.as_prompt()
    assert "可用工具:" in prompt
    assert "- calculator(" in prompt


class FakeRetrieval:
    def search_text(self, kb_id, text, top_k=4):
        if kb_id == "empty":
            return []
        return [Hit(text="命中片段", score=0.9, meta={"source": "kb"})]


def test_knowledge_search_formats_hits():
    registry = ToolRegistry()
    register_builtins(registry, retrieval=FakeRetrieval(), default_kb="demo")
    assert registry.has("knowledge_search")
    out = registry.execute("knowledge_search", {"query": "任意", "kb_id": "demo"})
    assert "命中片段" in out and "score=0.900" in out


def test_knowledge_search_reports_miss():
    registry = ToolRegistry()
    register_builtins(registry, retrieval=FakeRetrieval(), default_kb="demo")
    out = registry.execute("knowledge_search", {"query": "任意", "kb_id": "empty"})
    assert "没有命中" in out


def test_describe_exposes_metadata():
    registry = ToolRegistry()
    register_builtins(registry, retrieval=FakeRetrieval())
    names = {item["name"] for item in registry.describe()}
    assert names == {"calculator", "knowledge_search"}
