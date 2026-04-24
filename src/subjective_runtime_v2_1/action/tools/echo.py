from __future__ import annotations

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool


class EchoTool(Tool):
    spec = ToolSpec(
        name="echo",
        description="return the provided message",
        input_schema={"type": "object", "required": ["message"]},
        side_effect_level="none",
        allowed_in_idle=True,
        reversibility="full",
        observability="high",
        blast_radius="low",
    )

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        return ToolResult(ok=True, output={"message": call.arguments["message"]})
