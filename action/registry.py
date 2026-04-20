from __future__ import annotations

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult
from subjective_runtime_v2_1.action.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.spec.name in self._tools:
            raise ValueError(f"duplicate tool: {tool.spec.name}")
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def specs(self) -> list[dict]:
        return [tool.spec.__dict__ for tool in self._tools.values()]

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        return self.get(call.tool_name).invoke(call, ctx)
