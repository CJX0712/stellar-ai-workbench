# Author: 晨星
"""工具注册与执行：内置 calculator（安全表达式求值）与 knowledge_search（走检索）。"""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.core.logging import get_logger

logger = get_logger("stellar.tools")

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Tuple,
)


class UnknownToolError(KeyError):
    """请求了未注册的工具。"""


def _exponent_too_large(node: ast.Pow) -> bool:
    """限制幂运算规模，避免 2**99999999 拖死进程。"""
    right = node.right
    if isinstance(right, ast.Constant) and isinstance(right.value, (int, float)):
        return abs(right.value) > 1024
    return False


def safe_eval(expression: str) -> float:
    """在白名单 AST 上求值，禁止函数调用/属性访问/变量引用。"""
    tree = ast.parse(str(expression), mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"表达式含不允许的语法：{type(node).__name__}")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("只允许数字常量")
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) and _exponent_too_large(node):
            raise ValueError("指数过大，拒绝计算")
    value = eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {})  # noqa: S307
    if isinstance(value, complex):
        raise ValueError("不支持复数结果")
    return float(value)


def calculator(expression: str) -> str:
    """计算数学表达式；失败时返回可读错误文本而不是抛异常。"""
    try:
        result = safe_eval(expression)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, TypeError) as exc:
        return f"计算失败：{exc}"
    if math.isnan(result) or math.isinf(result):
        return f"计算失败：结果不是有限数（{expression}）"
    if result.is_integer():
        return str(int(result))
    return f"{result:.6f}".rstrip("0").rstrip(".")


@dataclass
class ToolSpec:
    """工具描述与实现。"""

    name: str
    description: str
    func: Callable[..., str]
    args: dict = field(default_factory=dict)

    def invoke(self, arguments: Optional[dict] = None) -> str:
        return str(self.func(**(arguments or {})))


class ToolRegistry:
    """工具注册表：装饰器注册、按名执行、导出提示词。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def tool(self, name: Optional[str] = None, description: str = "", **args: str) -> Callable:
        """装饰器形式注册工具。"""

        def decorator(func: Callable[..., str]) -> Callable[..., str]:
            self.register(name or func.__name__, func, description or (func.__doc__ or "").strip(), **args)
            return func

        return decorator

    def register(
        self,
        name: str,
        func: Callable[..., str],
        description: str = "",
        **args: str,
    ) -> ToolSpec:
        if not name or not callable(func):
            raise ValueError("工具名与可调用对象均不能为空")
        spec = ToolSpec(name=name, description=description, func=func, args=dict(args))
        self._tools[name] = spec
        logger.info("注册工具：%s", name)
        return spec

    def has(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise UnknownToolError(name)
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> list[dict]:
        return [
            {"name": s.name, "description": s.description, "args": dict(s.args)}
            for s in (self._tools[n] for n in self.names())
        ]

    def execute(self, name: str, args: Optional[dict] = None) -> str:
        """按名执行；工具内部异常转成文本，未知工具抛 UnknownToolError。"""
        spec = self.get(name)
        try:
            return spec.invoke(args)
        except TypeError as exc:
            return f"工具 {name} 参数错误：{exc}"
        except Exception as exc:  # noqa: BLE001 - 观察结果必须可读，不能中断 Agent
            logger.warning("工具 %s 执行失败：%s", name, exc)
            return f"工具 {name} 执行失败：{exc}"

    def as_prompt(self) -> str:
        """导出给模型的工具清单（Agent 与 MockProvider 都按此格式解析）。"""
        lines = ["可用工具:"]
        for name in self.names():
            spec = self._tools[name]
            arg_list = ", ".join(spec.args) if spec.args else ""
            lines.append(f"- {name}({arg_list}) - {spec.description}")
        lines.append("输出格式：THOUGHT: 思考\nACTION: 工具名 {\"参数\": 值}")
        lines.append("或直接给出 FINAL: 最终答复")
        return "\n".join(lines)


def build_default_registry(retrieval: Any = None, default_kb: str = "default") -> ToolRegistry:
    """构造内置工具注册表（容器装配用的便捷入口）。"""
    return register_builtins(ToolRegistry(), retrieval=retrieval, default_kb=default_kb)


def register_builtins(registry: ToolRegistry, retrieval: Any = None, default_kb: str = "default") -> ToolRegistry:
    """注册内置工具：calculator 与 knowledge_search（后者依赖检索模块）。"""
    registry.register("calculator", calculator, "计算数学表达式，如 2 + 3 * 4", expression="数学表达式")

    if retrieval is not None:

        def knowledge_search(query: str, kb_id: str = default_kb, top_k: int = 4) -> str:
            hits = retrieval.search_text(kb_id or default_kb, query, top_k)
            if not hits:
                return f"知识库 {kb_id or default_kb} 中没有命中内容。"
            parts = []
            for index, hit in enumerate(hits, start=1):
                parts.append(f"[{index}] (score={hit.score:.3f}) {hit.text}")
            return "\n".join(parts)

        registry.register(
            "knowledge_search",
            knowledge_search,
            "检索本地知识库并返回相关片段",
            query="检索关键词",
            kb_id="知识库 id",
            top_k="返回条数",
        )
    return registry
