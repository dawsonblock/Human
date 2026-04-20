from __future__ import annotations

from subjective_runtime_v2_1.action.context import ExecutionContext
from subjective_runtime_v2_1.action.contracts import ToolCall, ToolResult, ToolSpec
from subjective_runtime_v2_1.action.tools.base import Tool


class MemoryWriteTool(Tool):
    spec = ToolSpec(
        name="memory_write",
        description="write a structured memory item",
        input_schema={"type": "object", "required": ["kind", "payload"]},
        side_effect_level="low",
        allowed_in_idle=True,
        reversibility="partial",
        observability="high",
        blast_radius="low",
    )

    def __init__(self, memory_sink: list[dict]) -> None:
        self.memory_sink = memory_sink

    def invoke(self, call: ToolCall, ctx: ExecutionContext) -> ToolResult:
        entry = {"kind": call.arguments["kind"], "payload": call.arguments["payload"]}
        self.memory_sink.append(entry)
        return ToolResult(ok=True, output={"written": True})
