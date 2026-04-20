from __future__ import annotations

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool


class HttpGetTool(Tool):
    spec = ToolSpec(
        name="http_get",
        description="placeholder read-only network tool",
        input_schema={"type": "object", "required": ["url"]},
        side_effect_level="low",
        allowed_in_idle=False,
        reversibility="full",
        observability="high",
        blast_radius="medium",
    )

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        return ToolResult(ok=False, output={}, error="http_get scaffold not implemented")
